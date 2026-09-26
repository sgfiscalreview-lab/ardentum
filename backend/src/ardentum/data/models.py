"""Data-layer domain models with explicit provenance."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd


class AssetClass(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    INDEX = "index"
    OTHER = "other"


class DatasetKind(StrEnum):
    DEMO = "demo"  # built-in synthetic data, clearly labelled
    UPLOAD = "upload"  # user-supplied CSV
    PROVIDER = "provider"  # licensed market-data provider (e.g. Tiingo)


@dataclass(frozen=True)
class EsgRecord:
    """An ESG score with provenance. Scores are opinions of the stated source."""

    score: float  # 0-100, higher is better
    source: str
    as_of: dt.date | None = None
    is_synthetic: bool = False


@dataclass(frozen=True)
class AssetInfo:
    ticker: str
    name: str
    asset_class: AssetClass = AssetClass.EQUITY
    sector: str | None = None
    currency: str = "USD"
    esg: EsgRecord | None = None
    is_benchmark: bool = False
    description: str | None = None


@dataclass(frozen=True)
class DataProvenance:
    source: str
    is_synthetic: bool
    adjustment: str  # e.g. "total return (split and dividend adjusted)"
    retrieved_at: dt.datetime | None = None
    license_note: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriceData:
    """Aligned adjusted close prices (dates x tickers) plus provenance."""

    prices: pd.DataFrame
    provenance: DataProvenance
    quality_notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DatasetInfo:
    id: str
    name: str
    kind: DatasetKind
    description: str
    provenance: DataProvenance
    assets: tuple[AssetInfo, ...]
    start: dt.date | None = None
    end: dt.date | None = None
    frequency: str = "daily"

    def asset(self, ticker: str) -> AssetInfo | None:
        return next((a for a in self.assets if a.ticker == ticker), None)
