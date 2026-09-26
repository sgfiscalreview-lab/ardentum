"""Risk-free rate estimates from free public sources (orchestration only).

* ``fred_dgs3mo`` — FRED series DGS3MO (3-month Treasury bill, investment yield);
  the window's daily yields are converted to effective annual rates and averaged.
  Needs a free FRED API key.
* ``kenfrench_rf`` — the Fama-French daily risk-free return (1-month T-bill) from the
  Kenneth French Data Library; the window's realised returns are compounded and
  annualised geometrically. No key.

The result is an effective annual rate the user can adopt for Sharpe ratios and
optimisation; the chosen source is echoed in every result that uses it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from ardentum.data.errors import DataNotConfiguredError
from ardentum.data.providers import fred, kenfrench
from ardentum.quant.errors import InsufficientDataError
from ardentum.quant.returns import annualise_periodic_rates, bill_yield_to_effective
from ardentum.services.market_data import MarketDataService

RiskFreeSource = Literal["fred_dgs3mo", "kenfrench_rf"]
FRED_MAX_AGE = dt.timedelta(hours=20)
DEFAULT_YEARS = 5
MIN_OBS = 20


@dataclass(frozen=True)
class SourceInfo:
    id: RiskFreeSource
    name: str
    description: str
    citation: str


SOURCES: dict[RiskFreeSource, SourceInfo] = {
    "fred_dgs3mo": SourceInfo(
        "fred_dgs3mo",
        "3-month T-bill (FRED DGS3MO)",
        "Average of daily 3-month T-bill yields over the window, each converted from the "
        "investment (bond-equivalent) basis to an effective annual rate.",
        "Board of Governors of the Federal Reserve System, Market Yield on U.S. Treasury "
        "Securities at 3-Month Constant Maturity (DGS3MO), retrieved from FRED, Federal "
        "Reserve Bank of St. Louis.",
    ),
    "kenfrench_rf": SourceInfo(
        "kenfrench_rf",
        "1-month T-bill (Fama-French RF)",
        "Realised daily risk-free returns over the window, compounded and annualised.",
        "Kenneth R. French Data Library, Fama/French 3 Factors (daily), RF column.",
    ),
}


@dataclass(frozen=True)
class RiskFreeEstimate:
    source: SourceInfo
    rate: float
    start: dt.date
    end: dt.date
    observations: int
    retrieved_at: dt.datetime
    stale: bool

    @property
    def label(self) -> str:
        return (
            f"{self.source.name}, {self.start.isoformat()} to {self.end.isoformat()} "
            f"({self.observations} observations)"
        )


def available(market: MarketDataService) -> dict[RiskFreeSource, bool]:
    return {"fred_dgs3mo": bool(market.settings.fred_api_key), "kenfrench_rf": True}


def _window(series: pd.Series, start: dt.date | None, end: dt.date | None) -> pd.Series:
    series = series.dropna().sort_index()
    if series.empty:
        raise InsufficientDataError("The risk-free source returned no observations.")
    stop = pd.Timestamp(end) if end else series.index[-1]
    begin = pd.Timestamp(start) if start else stop - pd.DateOffset(years=DEFAULT_YEARS)
    out = series.loc[begin:stop]
    if len(out) < MIN_OBS:
        first, last = series.index[0].date(), series.index[-1].date()
        raise InsufficientDataError(
            f"Only {len(out)} risk-free observations between {begin.date()} and {stop.date()}; "
            f"the source covers {first} to {last}. Choose a longer or earlier window."
        )
    return out


def estimate(
    market: MarketDataService,
    source: RiskFreeSource,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> RiskFreeEstimate:
    info = SOURCES[source]
    if source == "fred_dgs3mo":
        key = market.settings.fred_api_key
        if not key:
            raise DataNotConfiguredError(
                "FRED is not configured on this server; use the Kenneth French source instead."
            )
        client = fred.FredClient(key)
        got = market.cache.get_or_fetch(
            "fred",
            fred.DEFAULT_SERIES,
            FRED_MAX_AGE,
            lambda: client.series_payload(fred.DEFAULT_SERIES),
        )
        window = _window(fred.parse_observations(got.payload, fred.DEFAULT_SERIES), start, end)
        rate = float(np.mean(bill_yield_to_effective(window.to_numpy())))
    else:
        got = market.kf_file(kenfrench.FACTORS_DAILY)
        rf = kenfrench.factor_returns(kenfrench.unzip_text(got.payload))["RF"]
        window = _window(rf, start, end)
        rate = annualise_periodic_rates(window.to_numpy(), 252)
    return RiskFreeEstimate(
        source=info,
        rate=rate,
        start=window.index[0].date(),
        end=window.index[-1].date(),
        observations=len(window),
        retrieved_at=got.fetched_at,
        stale=got.stale,
    )
