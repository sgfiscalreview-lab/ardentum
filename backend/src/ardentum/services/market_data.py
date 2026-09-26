"""Resolution of datasets and loading of aligned return windows.

Dataset identifiers:
* ``demo``    — built-in synthetic universe (always available, clearly labelled);
* ``tiingo``  — live Tiingo prices (only when ``ARDENTUM_TIINGO_API_KEY`` is set);
* ``<uuid>``  — a dataset uploaded by the signed-in user.
"""

from __future__ import annotations

import datetime as dt
import gzip
import io
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ardentum.api.auth import Principal
from ardentum.config import Settings
from ardentum.data.errors import DataNotConfiguredError
from ardentum.data.models import (
    AssetClass,
    AssetInfo,
    DataProvenance,
    DatasetInfo,
    DatasetKind,
    EsgRecord,
)
from ardentum.data.providers import demo
from ardentum.data.providers.tiingo import TiingoProvider
from ardentum.data.validation import QualityReport, align_prices
from ardentum.db.models import Dataset
from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.frequency import Frequency
from ardentum.quant.optimisation import AssetMetadata
from ardentum.quant.returns import simple_returns

TIINGO_ID = "tiingo"
MIN_OBSERVATIONS = 30


class NotFoundError(Exception):
    """A dataset or resource does not exist or is not visible to the caller."""


@dataclass(frozen=True)
class LoadedData:
    dataset: DatasetInfo
    tickers: tuple[str, ...]
    prices: pd.DataFrame
    returns: pd.DataFrame
    frequency: Frequency
    report: QualityReport
    provenance: DataProvenance

    @property
    def periods_per_year(self) -> int:
        return self.frequency.periods_per_year

    def asset(self, ticker: str) -> AssetInfo:
        return self.dataset.asset(ticker) or AssetInfo(ticker=ticker, name=ticker)

    def metadata(self) -> AssetMetadata:
        return AssetMetadata(
            sectors={t: a.sector for t in self.tickers if (a := self.asset(t)).sector},
            esg_scores={
                t: (a.esg.score if (a := self.asset(t)).esg else None) for t in self.tickers
            },
        )


class _LRU:
    def __init__(self, size: int) -> None:
        self._data: OrderedDict[object, object] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def get(self, key: object) -> object | None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            return None

    def put(self, key: object, value: object) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._size:
                self._data.popitem(last=False)


_UPLOAD_CACHE = _LRU(16)
_TIINGO_CACHE = _LRU(256)


def encode_prices(prices: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    prices.to_csv(buf, index_label="date", float_format="%.10g")
    return gzip.compress(buf.getvalue().encode("utf-8"))


def decode_prices(blob: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(gzip.decompress(blob)), index_col="date", parse_dates=["date"])
    df.index = pd.DatetimeIndex(df.index)
    return df.astype(float)


def asset_from_json(d: dict[str, object]) -> AssetInfo:
    esg = None
    if d.get("esg_score") is not None:
        as_of = d.get("esg_as_of")
        esg = EsgRecord(
            score=float(d["esg_score"]),  # type: ignore[arg-type]
            source=str(d.get("esg_source") or "User supplied"),
            as_of=dt.date.fromisoformat(str(as_of)) if as_of else None,
        )
    return AssetInfo(
        ticker=str(d["ticker"]),
        name=str(d.get("name") or d["ticker"]),
        asset_class=AssetClass(str(d.get("asset_class") or "equity")),
        sector=str(d["sector"]) if d.get("sector") else None,
        esg=esg,
    )


def asset_to_json(a: AssetInfo) -> dict[str, object]:
    return {
        "ticker": a.ticker,
        "name": a.name,
        "asset_class": a.asset_class.value,
        "sector": a.sector,
        "esg_score": a.esg.score if a.esg else None,
        "esg_source": a.esg.source if a.esg else None,
        "esg_as_of": a.esg.as_of.isoformat() if a.esg and a.esg.as_of else None,
    }


def _upload_provenance(row: Dataset) -> DataProvenance:
    return DataProvenance(
        source=f"User upload: {row.source_filename or row.name}",
        is_synthetic=False,
        adjustment="As supplied by the user (expected: total-return adjusted closes).",
        license_note="The uploader is responsible for the right to use this data.",
        notes=("Ardentum has not verified this data; results are only as reliable as the input.",),
    )


def upload_info(row: Dataset) -> DatasetInfo:
    return DatasetInfo(
        id=str(row.id),
        name=row.name,
        kind=DatasetKind.UPLOAD,
        description=row.description or "User-uploaded price data.",
        provenance=_upload_provenance(row),
        assets=tuple(asset_from_json(a) for a in row.assets),
        start=row.start_date,
        end=row.end_date,
    )


def tiingo_info() -> DatasetInfo:
    return DatasetInfo(
        id=TIINGO_ID,
        name="Live market data (Tiingo)",
        kind=DatasetKind.PROVIDER,
        description=(
            "Daily split- and dividend-adjusted closes from Tiingo for any supported US ticker. "
            "Sector and ESG data are not provided by this source."
        ),
        provenance=DataProvenance(
            source="Tiingo End-of-Day API",
            is_synthetic=False,
            adjustment="Split- and dividend-adjusted close (total return).",
            license_note="Subject to the Tiingo plan licensed by this deployment.",
        ),
        assets=(),
    )


class MarketDataService:
    def __init__(self, settings: Settings, session: Session | None, principal: Principal | None):
        self.settings = settings
        self.session = session
        self.principal = principal

    # ------------------------------------------------------------------ datasets

    def list_datasets(self) -> list[tuple[DatasetInfo, bool]]:
        out: list[tuple[DatasetInfo, bool]] = [(demo.dataset_info(), False)]
        if self.settings.tiingo_api_key:
            out.append((tiingo_info(), False))
        if self.principal and self.session is not None:
            rows = self.session.scalars(
                select(Dataset)
                .where(Dataset.owner_id == self.principal.user_id)
                .order_by(Dataset.created_at.desc())
            ).all()
            out.extend((upload_info(r), True) for r in rows)
        return out

    def _upload_row(self, dataset_id: str) -> Dataset:
        try:
            uid = uuid.UUID(dataset_id)
        except ValueError as exc:
            raise NotFoundError(f"Dataset {dataset_id!r} not found.") from exc
        if self.principal is None or self.session is None:
            raise NotFoundError("Sign in to use uploaded datasets.")
        row = self.session.get(Dataset, uid)
        if row is None or row.owner_id != self.principal.user_id:
            raise NotFoundError(f"Dataset {dataset_id!r} not found.")
        return row

    def get_dataset(self, dataset_id: str) -> tuple[DatasetInfo, bool]:
        if dataset_id == demo.DATASET_ID:
            return demo.dataset_info(), False
        if dataset_id == TIINGO_ID:
            if not self.settings.tiingo_api_key:
                raise DataNotConfiguredError("Live market data is not configured on this server.")
            return tiingo_info(), False
        return upload_info(self._upload_row(dataset_id)), True

    # ------------------------------------------------------------------ prices

    def _raw_prices(
        self, dataset_id: str, tickers: list[str], start: dt.date | None, end: dt.date | None
    ) -> tuple[pd.DataFrame, DataProvenance, DatasetInfo]:
        if dataset_id == demo.DATASET_ID:
            data = demo.load_prices(tickers, start, end)
            return data.prices, data.provenance, demo.dataset_info()
        if dataset_id == TIINGO_ID:
            info, _ = self.get_dataset(TIINGO_ID)
            s = start or dt.date(2000, 1, 1)
            e = end or dt.date.today()
            key = (tuple(tickers), s, e)
            cached = _TIINGO_CACHE.get(key)
            if cached is None:
                cached = TiingoProvider(self.settings.tiingo_api_key).fetch_prices(tickers, s, e)
                _TIINGO_CACHE.put(key, cached)
            prices = cached.prices  # type: ignore[attr-defined]
            return prices, cached.provenance, info  # type: ignore[attr-defined]
        row = self._upload_row(dataset_id)
        cached_df = _UPLOAD_CACHE.get(row.id)
        if cached_df is None:
            cached_df = decode_prices(row.prices_csv_gz)
            _UPLOAD_CACHE.put(row.id, cached_df)
        df: pd.DataFrame = cached_df  # type: ignore[assignment]
        missing = [t for t in tickers if t not in df.columns]
        if missing:
            raise InvalidInputError(f"Tickers not in dataset {row.name!r}: {', '.join(missing)}.")
        sliced = df.loc[
            (pd.Timestamp(start) if start else df.index[0]) : (
                pd.Timestamp(end) if end else df.index[-1]
            ),
            tickers,
        ]
        return sliced, _upload_provenance(row), upload_info(row)

    def load(
        self,
        dataset_id: str,
        tickers: list[str],
        start: dt.date | None = None,
        end: dt.date | None = None,
        frequency: str = "daily",
    ) -> LoadedData:
        raw, provenance, info = self._raw_prices(dataset_id, list(tickers), start, end)
        if raw.empty:
            raise InsufficientDataError("No prices in the selected date range.")
        aligned, report = align_prices(raw)
        freq = Frequency(frequency)
        if freq is Frequency.WEEKLY:
            aligned = aligned.resample("W-FRI").last().dropna()
        elif freq is Frequency.MONTHLY:
            aligned = aligned.resample("ME").last().dropna()
        elif freq is not Frequency.DAILY:
            raise InvalidInputError(f"Unsupported frequency {frequency!r}.")
        if len(aligned) < MIN_OBSERVATIONS + 1:
            raise InsufficientDataError(
                f"Only {len(aligned) - 1} {freq.value} returns in the selected window; "
                f"at least {MIN_OBSERVATIONS} are required."
            )
        returns = simple_returns(aligned)
        return LoadedData(
            dataset=info,
            tickers=tuple(tickers),
            prices=aligned,
            returns=returns,
            frequency=freq,
            report=report,
            provenance=provenance,
        )
