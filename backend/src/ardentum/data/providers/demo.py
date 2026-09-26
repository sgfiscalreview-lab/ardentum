"""Built-in SYNTHETIC demo universe.

This module generates *fictional* price histories so the product can be used and
tested without a licensed market-data feed. Nothing here is market data:

* every issuer is fictional and every ticker carries a ``.SYN`` suffix;
* prices come from a documented statistical model with a fixed seed;
* ESG scores are illustrative values chosen by hand, not ratings from any provider.

The model is designed to exhibit the stylised facts that matter for testing
portfolio tools (Cont 2001, "Empirical properties of asset returns: stylized
facts and statistical issues", Quantitative Finance 1(2)):

* a market factor with GARCH(1,1) volatility clustering and Student-t(6) shocks;
* sector factors, so within-sector correlation exceeds cross-sector correlation;
* fat-tailed (Student-t(5)) idiosyncratic noise;
* two generic stress episodes at arbitrary dates (they do not replicate any
  historical crisis);
* defensive assets (a government-bond index with negative market beta).

The generator is deterministic: ``GENERATOR_VERSION`` and ``SEED`` pin the output.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from ardentum.data.models import (
    AssetClass,
    AssetInfo,
    DataProvenance,
    DatasetInfo,
    DatasetKind,
    EsgRecord,
    PriceData,
)
from ardentum.quant.errors import InvalidInputError

DATASET_ID = "demo"
GENERATOR_VERSION = "1.0.0"
SEED = 20_240_917
START = "2011-01-03"
END = "2025-12-31"
TRADING_DAYS = 252
ESG_SOURCE = "Synthetic illustrative score (not from any ESG rating provider)"


@dataclass(frozen=True)
class _Spec:
    ticker: str
    name: str
    sector: str
    asset_class: AssetClass
    alpha: float  # annual
    beta: float
    idio_vol: float  # annual
    esg: float | None
    start_price: float


_SPECS: tuple[_Spec, ...] = (
    _Spec(
        "NWS.SYN",
        "Northwind Semiconductors",
        "Information Technology",
        AssetClass.EQUITY,
        0.040,
        1.35,
        0.28,
        62,
        48.0,
    ),
    _Spec(
        "CLDR.SYN",
        "Cloudrise Software",
        "Information Technology",
        AssetClass.EQUITY,
        0.030,
        1.25,
        0.26,
        71,
        85.0,
    ),
    _Spec(
        "HLX.SYN",
        "Helix Biotherapeutics",
        "Health Care",
        AssetClass.EQUITY,
        0.020,
        0.90,
        0.32,
        66,
        32.0,
    ),
    _Spec(
        "MDC.SYN",
        "Meridian Medical Devices",
        "Health Care",
        AssetClass.EQUITY,
        0.015,
        0.80,
        0.18,
        74,
        120.0,
    ),
    _Spec(
        "ARB.SYN",
        "Arbor Regional Bank",
        "Financials",
        AssetClass.EQUITY,
        -0.010,
        1.15,
        0.20,
        55,
        40.0,
    ),
    _Spec(
        "CSP.SYN",
        "Cornerstone Insurance",
        "Financials",
        AssetClass.EQUITY,
        0.000,
        0.85,
        0.16,
        60,
        66.0,
    ),
    _Spec("PTR.SYN", "Petra Energy", "Energy", AssetClass.EQUITY, 0.000, 1.05, 0.28, 24, 58.0),
    _Spec(
        "SOL.SYN", "Solace Renewables", "Utilities", AssetClass.EQUITY, 0.010, 0.90, 0.30, 82, 22.0
    ),
    _Spec(
        "GRD.SYN", "Gridline Utilities", "Utilities", AssetClass.EQUITY, 0.000, 0.45, 0.12, 58, 44.0
    ),
    _Spec(
        "FRG.SYN", "Forge Industrial", "Industrials", AssetClass.EQUITY, 0.005, 1.10, 0.18, 49, 75.0
    ),
    _Spec(
        "AVN.SYN", "Avion Aerospace", "Industrials", AssetClass.EQUITY, -0.005, 1.20, 0.24, 41, 95.0
    ),
    _Spec(
        "HRV.SYN",
        "Harvest Consumer Staples",
        "Consumer Staples",
        AssetClass.EQUITY,
        0.010,
        0.55,
        0.12,
        68,
        52.0,
    ),
    _Spec(
        "LUX.SYN",
        "Lumen Retail",
        "Consumer Discretionary",
        AssetClass.EQUITY,
        0.000,
        1.15,
        0.24,
        52,
        36.0,
    ),
    _Spec(
        "MNR.SYN",
        "Mineral Ridge Mining",
        "Materials",
        AssetClass.EQUITY,
        -0.010,
        1.20,
        0.30,
        31,
        27.0,
    ),
    _Spec(
        "TWR.SYN",
        "Towerpoint Real Estate",
        "Real Estate",
        AssetClass.EQUITY,
        -0.005,
        0.80,
        0.20,
        57,
        61.0,
    ),
    _Spec(
        "SIG.SYN",
        "Signal Communications",
        "Communication Services",
        AssetClass.EQUITY,
        0.000,
        0.95,
        0.20,
        63,
        29.0,
    ),
    _Spec(
        "GOVB.SYN",
        "Synthetic Government Bond Index",
        "Government Bonds",
        AssetClass.FIXED_INCOME,
        0.030,
        -0.08,
        0.05,
        70,
        100.0,
    ),
    _Spec(
        "CORP.SYN",
        "Synthetic Corporate Bond Index",
        "Corporate Bonds",
        AssetClass.FIXED_INCOME,
        0.040,
        0.15,
        0.06,
        61,
        100.0,
    ),
    _Spec(
        "GOLD.SYN",
        "Synthetic Gold",
        "Commodities",
        AssetClass.COMMODITY,
        0.040,
        0.05,
        0.15,
        None,
        100.0,
    ),
)

MARKET = _Spec(
    "MKT.SYN", "Synthetic Market Index", "Index", AssetClass.INDEX, 0.0, 1.0, 0.0, None, 1000.0
)

# Market factor: arithmetic drift and unconditional volatility (annual).
_MKT_DRIFT = 0.08
_MKT_VOL = 0.16
_GARCH_ALPHA = 0.08
_GARCH_BETA = 0.90
_SECTOR_VOL = 0.10
_IDIO_SCALE = 0.8  # calibrates single-stock volatility to a typical 20-35% range
# Generic stress episodes (start date, length in days, daily drift, vol multiplier).
_STRESS = (("2014-05-12", 12, -0.006, 2.0), ("2019-10-07", 22, -0.012, 3.0))


def _student_t(rng: np.random.Generator, dof: float, size: tuple[int, ...] | int) -> np.ndarray:
    """Student-t draws rescaled to unit variance."""
    return np.asarray(rng.standard_t(dof, size=size) / np.sqrt(dof / (dof - 2.0)))


@lru_cache(maxsize=1)
def _generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    index = pd.bdate_range(START, END)
    t_len = len(index)

    # Market factor with GARCH(1,1) variance.
    var_u = _MKT_VOL**2 / TRADING_DAYS
    omega = var_u * (1.0 - _GARCH_ALPHA - _GARCH_BETA)
    mu_d = _MKT_DRIFT / TRADING_DAYS
    z = _student_t(rng, 6.0, t_len)
    drift = np.full(t_len, mu_d)
    vol_mult = np.ones(t_len)
    for start, length, d, m in _STRESS:
        i0 = int(index.searchsorted(pd.Timestamp(start)))
        drift[i0 : i0 + length] = d
        vol_mult[i0 : i0 + length] = m
    mkt = np.empty(t_len)
    var = var_u
    prev_shock = 0.0
    for t in range(t_len):
        var = omega + _GARCH_ALPHA * prev_shock**2 + _GARCH_BETA * var
        prev_shock = np.sqrt(var) * z[t]
        # Stress scaling is applied outside the GARCH recursion so that it cannot make
        # the variance process explosive (alpha * m^2 + beta must stay below one).
        mkt[t] = drift[t] + prev_shock * vol_mult[t]

    sectors = sorted({s.sector for s in _SPECS})
    sector_f = {
        s: _student_t(rng, 6.0, t_len) * _SECTOR_VOL / np.sqrt(TRADING_DAYS) for s in sectors
    }
    cols: dict[str, np.ndarray] = {}
    for spec in _SPECS:
        idio = _student_t(rng, 5.0, t_len) * _IDIO_SCALE * spec.idio_vol / np.sqrt(TRADING_DAYS)
        sector_load = 1.0 if spec.asset_class is AssetClass.EQUITY else 0.3
        r = spec.alpha / TRADING_DAYS + spec.beta * mkt + sector_load * sector_f[spec.sector] + idio
        cols[spec.ticker] = spec.start_price * np.cumprod(1.0 + np.clip(r, -0.9, None))
    cols[MARKET.ticker] = MARKET.start_price * np.cumprod(1.0 + np.clip(mkt, -0.9, None))
    df = pd.DataFrame(cols, index=index)
    df.index.name = "date"
    return df


def _asset(spec: _Spec, *, benchmark: bool = False) -> AssetInfo:
    return AssetInfo(
        ticker=spec.ticker,
        name=f"{spec.name} (synthetic)",
        asset_class=spec.asset_class,
        sector=spec.sector,
        esg=None
        if spec.esg is None
        else EsgRecord(score=float(spec.esg), source=ESG_SOURCE, is_synthetic=True),
        is_benchmark=benchmark,
        description="Fictional issuer generated by the Ardentum demo-data model.",
    )


PROVENANCE = DataProvenance(
    source=f"Ardentum synthetic demo-data generator v{GENERATOR_VERSION} (seed {SEED})",
    is_synthetic=True,
    adjustment="Total-return index (no dividends or splits are modelled separately).",
    license_note="Generated data, not market data. Free to use for demonstration and testing.",
    notes=(
        "SYNTHETIC DEMO DATA: all issuers, prices and ESG scores are fictional.",
        "Results computed on this dataset say nothing about real securities.",
    ),
)


def dataset_info() -> DatasetInfo:
    prices = _generate()
    return DatasetInfo(
        id=DATASET_ID,
        name="Synthetic demo universe",
        kind=DatasetKind.DEMO,
        description=(
            "19 fictional assets across 14 sectors (16 equities, 2 bond indices, gold) plus a "
            "synthetic market index, 2011-2025, generated by a documented factor model with "
            "volatility clustering and fat tails. For demonstration only."
        ),
        provenance=PROVENANCE,
        assets=(*(_asset(s) for s in _SPECS), _asset(MARKET, benchmark=True)),
        start=prices.index[0].date(),
        end=prices.index[-1].date(),
    )


def load_prices(
    tickers: list[str], start: dt.date | None = None, end: dt.date | None = None
) -> PriceData:
    df = _generate()
    unknown = [t for t in tickers if t not in df.columns]
    if unknown:
        raise InvalidInputError(f"Unknown demo tickers: {', '.join(unknown)}.")
    out = df.loc[
        (pd.Timestamp(start) if start else df.index[0]) : (
            pd.Timestamp(end) if end else df.index[-1]
        ),
        tickers,
    ].copy()
    return PriceData(prices=out, provenance=PROVENANCE)
