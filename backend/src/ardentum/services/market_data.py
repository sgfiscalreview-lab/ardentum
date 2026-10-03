"""Resolution of datasets and loading of aligned return windows.

Dataset identifiers:
* ``demo``    — built-in synthetic universe (always available, clearly labelled);
* ``kf12``, ``kf49`` — real US industry portfolios from the Kenneth French Data Library
  (free, no key; downloaded on demand and cached in PostgreSQL);
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
from dataclasses import dataclass, replace

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
from ardentum.data.providers import bis, demo, fx, kenfrench
from ardentum.data.providers.tiingo import TiingoProvider, parse_history
from ardentum.data.providers.tiingo import provenance as tiingo_provenance
from ardentum.data.validation import QualityReport, align_prices
from ardentum.db.models import Dataset
from ardentum.quant.currency import convert_prices, convert_prices_hedged
from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.frequency import Frequency
from ardentum.quant.optimisation import AssetMetadata
from ardentum.quant.returns import simple_returns
from ardentum.services.provider_cache import CachedPayload, ProviderCache

TIINGO_ID = "tiingo"
MIN_OBSERVATIONS = 30
KF_MAX_AGE = dt.timedelta(days=7)  # the library updates monthly
TIINGO_MAX_AGE = dt.timedelta(hours=20)  # end-of-day data
FX_MAX_AGE = dt.timedelta(hours=20)  # ECB publishes once per business day
RATES_MAX_AGE = dt.timedelta(hours=20)  # BIS policy rates, updated daily


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
    currency: str = "USD"  # currency every price series is expressed in

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
_PARSED_CACHE = _LRU(16)


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
        currency=str(d.get("currency") or "USD"),
        esg=esg,
        isin=str(d["isin"]) if d.get("isin") else None,
        market_cap=float(d["market_cap"]) if d.get("market_cap") is not None else None,  # type: ignore[arg-type]
    )


def asset_to_json(a: AssetInfo) -> dict[str, object]:
    return {
        "ticker": a.ticker,
        "name": a.name,
        "asset_class": a.asset_class.value,
        "sector": a.sector,
        "currency": a.currency,
        "isin": a.isin,
        "market_cap": a.market_cap,
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


def kf_info(spec: kenfrench.KFDatasetSpec) -> DatasetInfo:
    return DatasetInfo(
        id=spec.id,
        name=spec.name,
        kind=DatasetKind.PROVIDER,
        description=(
            f"Real daily returns of {len(spec.industries)} value-weighted US industry portfolios "
            "(all NYSE, AMEX and NASDAQ stocks grouped by SIC code) plus the US market, from the "
            "Kenneth R. French Data Library. Free; history from 1926."
        ),
        provenance=kenfrench.provenance(None),
        assets=kenfrench.assets(spec),
    )


class MarketDataService:
    def __init__(self, settings: Settings, session: Session | None, principal: Principal | None):
        self.settings = settings
        self.session = session
        self.principal = principal

    # ------------------------------------------------------------------ datasets

    def list_datasets(self) -> list[tuple[DatasetInfo, bool]]:
        out: list[tuple[DatasetInfo, bool]] = [(demo.dataset_info(), False)]
        out.extend((kf_info(spec), False) for spec in kenfrench.DATASETS.values())
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
        if dataset_id in kenfrench.DATASETS:
            return kf_info(kenfrench.DATASETS[dataset_id]), False
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
        if dataset_id in kenfrench.DATASETS:
            return self._kf_prices(kenfrench.DATASETS[dataset_id], tickers, start, end)
        if dataset_id == TIINGO_ID:
            return self._tiingo_prices(tickers, start, end)
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

    # ------------------------------------------------------------------ providers

    @property
    def cache(self) -> ProviderCache:
        return ProviderCache(self.session)

    def kf_file(self, name: str) -> CachedPayload:
        return self.cache.get_or_fetch(
            "kenfrench",
            name,
            KF_MAX_AGE,
            lambda: kenfrench.download(name, base_url=self.settings.kenfrench_base_url),
        )

    def _kf_returns(
        self, spec: kenfrench.KFDatasetSpec
    ) -> tuple[pd.DataFrame, CachedPayload, CachedPayload]:
        ind = self.kf_file(spec.daily_file)
        fac = self.kf_file(kenfrench.FACTORS_DAILY)
        key = ("kf", spec.id, ind.fetched_at, fac.fetched_at)
        cached = _PARSED_CACHE.get(key)
        if cached is None:
            industries = kenfrench.industry_returns(kenfrench.unzip_text(ind.payload))
            factors = kenfrench.factor_returns(kenfrench.unzip_text(fac.payload))
            cached = industries.join(factors[[kenfrench.MARKET_TICKER]], how="left")
            _PARSED_CACHE.put(key, cached)
        return cached, ind, fac  # type: ignore[return-value]

    def fama_french_factors(self) -> tuple[pd.DataFrame, CachedPayload]:
        """Daily Fama-French three factors and risk-free rate (decimals), cached."""
        fac = self.kf_file(kenfrench.FACTORS_DAILY)
        key = ("ff3", fac.fetched_at)
        cached = _PARSED_CACHE.get(key)
        if cached is None:
            cached = kenfrench.three_factors(kenfrench.unzip_text(fac.payload))
            _PARSED_CACHE.put(key, cached)
        return cached, fac  # type: ignore[return-value]

    def _kf_prices(
        self,
        spec: kenfrench.KFDatasetSpec,
        tickers: list[str],
        start: dt.date | None,
        end: dt.date | None,
    ) -> tuple[pd.DataFrame, DataProvenance, DatasetInfo]:
        returns, ind, fac = self._kf_returns(spec)
        missing = [t for t in tickers if t not in returns.columns]
        if missing:
            raise InvalidInputError(
                f"Unknown industry codes for {spec.name}: {', '.join(missing)}."
            )
        window = returns.loc[
            (pd.Timestamp(start) if start else returns.index[0]) : (
                pd.Timestamp(end) if end else returns.index[-1]
            ),
            tickers,
        ]
        prices = kenfrench.returns_to_prices(window)
        prov = kenfrench.provenance(min(ind.fetched_at, fac.fetched_at))
        if ind.stale or fac.stale:
            prov = _with_note(
                prov, "The Data Library could not be reached; showing the last cached copy."
            )
        return prices, prov, kf_info(spec)

    def market_caps(self, dataset_id: str) -> dict[str, float] | None:
        """Market capitalisation weights' inputs for Black-Litterman, when the source has them."""
        if dataset_id in kenfrench.DATASETS:
            spec = kenfrench.DATASETS[dataset_id]
            monthly = self.kf_file(spec.monthly_file)
            return kenfrench.market_caps(kenfrench.unzip_text(monthly.payload))
        return None

    def _tiingo_prices(
        self, tickers: list[str], start: dt.date | None, end: dt.date | None
    ) -> tuple[pd.DataFrame, DataProvenance, DatasetInfo]:
        info, _ = self.get_dataset(TIINGO_ID)
        provider = TiingoProvider(self.settings.tiingo_api_key)
        series: dict[str, pd.Series] = {}
        oldest: dt.datetime | None = None
        stale = False
        for t in tickers:
            got = self.cache.get_or_fetch(
                "tiingo",
                t.upper(),
                TIINGO_MAX_AGE,
                lambda t=t: provider.history_payload(t),  # type: ignore[misc]
            )
            series[t] = parse_history(got.payload, t)
            oldest = got.fetched_at if oldest is None else min(oldest, got.fetched_at)
            stale = stale or got.stale
        prices = pd.DataFrame(series).sort_index()
        prices = prices.loc[
            (pd.Timestamp(start) if start else prices.index[0]) : (
                pd.Timestamp(end) if end else prices.index[-1]
            )
        ]
        prov = tiingo_provenance(oldest)
        if stale:
            prov = _with_note(prov, "Tiingo could not be reached; showing the last cached prices.")
        return prices, prov, info

    # ------------------------------------------------------------------ currency

    def fx_rates(self, local: str, base: str) -> tuple[pd.Series, CachedPayload]:
        """Daily units of ``base`` per unit of ``local`` (ECB reference rates, cached)."""
        local, base = fx.check_currency(local), fx.check_currency(base)
        got = self.cache.get_or_fetch(
            "frankfurter",
            f"{local}->{base}",
            FX_MAX_AGE,
            lambda: fx.timeseries_payload(local, base),
        )
        key = ("fx", local, base, got.fetched_at)
        rates = _PARSED_CACHE.get(key)
        if rates is None:
            rates = fx.parse_timeseries(got.payload, base)
            _PARSED_CACHE.put(key, rates)
        return rates, got  # type: ignore[return-value]

    def policy_rates(self, currency: str) -> tuple[pd.Series, CachedPayload]:
        """Daily central-bank policy rates (annual decimals) for a currency (BIS, cached)."""
        cur = currency.upper()
        bis.area_for(cur)  # clear error before any network call
        got = self.cache.get_or_fetch(
            "bis", f"policy-rate:{cur}", RATES_MAX_AGE, lambda: bis.rates_payload(cur)
        )
        key = ("bis", cur, got.fetched_at)
        rates = _PARSED_CACHE.get(key)
        if rates is None:
            rates = bis.parse_rates(got.payload, cur)
            _PARSED_CACHE.put(key, rates)
        return rates, got  # type: ignore[return-value]

    def _to_base_currency(
        self,
        raw: pd.DataFrame,
        provenance: DataProvenance,
        info: DatasetInfo,
        tickers: list[str],
        base: str | None,
        hedged: bool = False,
    ) -> tuple[pd.DataFrame, DataProvenance, str]:
        currency = {t: (a.currency if (a := info.asset(t)) else "USD").upper() for t in tickers}
        if base is None:
            distinct = sorted(set(currency.values()))
            if len(distinct) > 1:
                raise InvalidInputError(
                    f"The selected assets are priced in {', '.join(distinct)}; choose a base "
                    "currency so their returns are comparable."
                )
            if hedged:
                raise InvalidInputError(
                    "Currency hedging needs a base currency; choose one, or use unhedged returns."
                )
            return raw, provenance, distinct[0]
        base = base.upper()
        by_local: dict[str, list[str]] = {}
        for t in tickers:
            if currency[t] != base:
                by_local.setdefault(currency[t], []).append(t)
        if not by_local:
            if hedged:
                provenance = _with_note(
                    provenance,
                    f"All selected assets are priced in {base}; there is no currency to hedge.",
                )
            return raw, provenance, base
        out = raw.copy()
        stale = False
        oldest: dt.datetime | None = None
        base_rates: pd.Series | None = None
        if hedged:
            base_rates, got_b = self.policy_rates(base)
            stale = stale or got_b.stale
        for local, members in by_local.items():
            rates, got = self.fx_rates(local, base)
            stale = stale or got.stale
            oldest = got.fetched_at if oldest is None else min(oldest, got.fetched_at)
            local_rates: pd.Series | None = None
            if hedged:
                local_rates, got_l = self.policy_rates(local)
                stale = stale or got_l.stale
            for t in members:
                if base_rates is not None and local_rates is not None:
                    out[t] = convert_prices_hedged(raw[t], rates, base_rates, local_rates)
                else:
                    out[t] = convert_prices(raw[t], rates)
        assert oldest is not None
        converted = (
            f"Prices quoted in {', '.join(sorted(by_local))} were converted to {base} at "
            f"{fx.SOURCE}, retrieved {oldest.date().isoformat()}. "
        )
        if hedged:
            note = converted + (
                "Returns are currency-hedged: each period the position's value is sold forward "
                "at a rate implied by the two currencies' short interest rates (covered "
                f"interest parity), using {bis.SOURCE}. The interest-rate difference is the "
                "cost or income of hedging; only each period's gain stays exposed to the "
                "exchange rate. Transaction costs and the spread between policy and "
                "money-market rates are ignored."
            )
        else:
            note = converted + "Returns are unhedged: they include exchange-rate moves."
        prov = _with_note(provenance, note)
        if stale:
            prov = _with_note(prov, "A rate source could not be reached; using cached rates.")
        return out, prov, base

    # ------------------------------------------------------------------ load

    def load(
        self,
        dataset_id: str,
        tickers: list[str],
        start: dt.date | None = None,
        end: dt.date | None = None,
        frequency: str = "daily",
        base_currency: str | None = None,
        currency_hedged: bool = False,
    ) -> LoadedData:
        raw, provenance, info = self._raw_prices(dataset_id, list(tickers), start, end)
        if raw.empty:
            raise InsufficientDataError("No prices in the selected date range.")
        raw, provenance, currency = self._to_base_currency(
            raw, provenance, info, list(tickers), base_currency, currency_hedged
        )
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
            currency=currency,
        )


def _with_note(p: DataProvenance, note: str) -> DataProvenance:
    return replace(p, notes=(*p.notes, note))
