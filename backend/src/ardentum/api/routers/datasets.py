from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import func, select

from ardentum.api import schemas as s
from ardentum.api.deps import DbDep, MarketService, RequiredPrincipal, SettingsDep
from ardentum.data.models import AssetInfo, DatasetInfo
from ardentum.data.providers.csv_upload import parse_metadata_csv, parse_price_csv
from ardentum.db.models import Dataset
from ardentum.quant.errors import InvalidInputError
from ardentum.services.analysis import provenance_out
from ardentum.services.market_data import (
    MIN_OBSERVATIONS,
    NotFoundError,
    asset_to_json,
    encode_prices,
    upload_info,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])
MAX_DATASETS_PER_USER = 20


def _asset_out(a: AssetInfo) -> s.AssetOut:
    return s.AssetOut(
        ticker=a.ticker,
        name=a.name,
        asset_class=a.asset_class.value,
        sector=a.sector,
        currency=a.currency,
        esg_score=a.esg.score if a.esg else None,
        esg_source=a.esg.source if a.esg else None,
        esg_as_of=a.esg.as_of if a.esg else None,
        esg_is_synthetic=bool(a.esg and a.esg.is_synthetic),
        is_benchmark=a.is_benchmark,
    )


def dataset_out(info: DatasetInfo, owned: bool) -> s.DatasetOut:
    return s.DatasetOut(
        id=info.id,
        name=info.name,
        kind=info.kind.value,
        description=info.description,
        is_synthetic=info.provenance.is_synthetic,
        provenance=provenance_out(info.provenance),
        start=info.start,
        end=info.end,
        assets=[_asset_out(a) for a in info.assets],
        sectors=sorted({a.sector for a in info.assets if a.sector}),
        owned=owned,
    )


@router.get("", response_model=list[s.DatasetSummaryOut])
def list_datasets(service: MarketService) -> list[s.DatasetSummaryOut]:
    return [
        s.DatasetSummaryOut(
            id=i.id,
            name=i.name,
            kind=i.kind.value,
            description=i.description,
            is_synthetic=i.provenance.is_synthetic,
            n_assets=len(i.assets),
            start=i.start,
            end=i.end,
            owned=owned,
        )
        for i, owned in service.list_datasets()
    ]


@router.get("/{dataset_id}", response_model=s.DatasetOut)
def get_dataset(dataset_id: str, service: MarketService) -> s.DatasetOut:
    info, owned = service.get_dataset(dataset_id)
    return dataset_out(info, owned)


async def _read_limited(f: UploadFile, limit: int) -> bytes:
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise InvalidInputError(
            f"{f.filename or 'File'} exceeds the {limit // (1024 * 1024)} MB limit."
        )
    return data


@router.post("", response_model=s.DatasetOut, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    principal: RequiredPrincipal,
    db: DbDep,
    settings: SettingsDep,
    name: Annotated[str, Form(min_length=1, max_length=120)],
    prices: Annotated[UploadFile, File(description="CSV of adjusted close prices")],
    description: Annotated[str | None, Form(max_length=2000)] = None,
    metadata: Annotated[UploadFile | None, File(description="Optional asset metadata CSV")] = None,
) -> s.DatasetOut:
    count = db.scalar(
        select(func.count()).select_from(Dataset).where(Dataset.owner_id == principal.user_id)
    )
    if (count or 0) >= MAX_DATASETS_PER_USER:
        raise InvalidInputError(
            f"You can store at most {MAX_DATASETS_PER_USER} datasets; delete one first."
        )
    panel = parse_price_csv(await _read_limited(prices, settings.max_upload_bytes))
    short = [str(c) for c in panel.columns if panel[c].notna().sum() < MIN_OBSERVATIONS + 1]
    if short:
        raise InvalidInputError(
            f"Each ticker needs at least {MIN_OBSERVATIONS + 1} prices; too few for: {', '.join(short[:10])}."
        )
    meta_by_ticker: dict[str, AssetInfo] = {}
    if metadata is not None and metadata.filename:
        for a in parse_metadata_csv(await _read_limited(metadata, settings.max_upload_bytes)):
            if a.ticker not in panel.columns:
                raise InvalidInputError(
                    f"Metadata ticker {a.ticker} does not appear in the price file."
                )
            meta_by_ticker[a.ticker] = a
    assets = [
        meta_by_ticker.get(str(t), AssetInfo(ticker=str(t), name=str(t))) for t in panel.columns
    ]
    row = Dataset(
        owner_id=principal.user_id,
        name=name.strip(),
        description=description,
        source_filename=(prices.filename or "upload.csv")[:255],
        prices_csv_gz=encode_prices(panel),
        assets=[asset_to_json(a) for a in assets],
        start_date=panel.index[0].date(),
        end_date=panel.index[-1].date(),
    )
    db.add(row)
    db.commit()
    return dataset_out(upload_info(row), True)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: str, principal: RequiredPrincipal, db: DbDep) -> None:
    try:
        uid = uuid.UUID(dataset_id)
    except ValueError as exc:
        raise NotFoundError("Dataset not found.") from exc
    row = db.get(Dataset, uid)
    if row is None or row.owner_id != principal.user_id:
        raise NotFoundError("Dataset not found.")
    db.delete(row)
    db.commit()
