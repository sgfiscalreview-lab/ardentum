"""Sampling frequency of return series and annualisation factors."""

from __future__ import annotations

from enum import StrEnum

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

    @property
    def periods_per_year(self) -> int:
        return _PERIODS_PER_YEAR[self]


# Trading-day convention: 252 trading days per year (the standard convention for
# US equity markets; see DECISIONS.md D-006).
_PERIODS_PER_YEAR: dict[Frequency, int] = {
    Frequency.DAILY: 252,
    Frequency.WEEKLY: 52,
    Frequency.MONTHLY: 12,
    Frequency.QUARTERLY: 4,
    Frequency.ANNUAL: 1,
}


def infer_frequency(index: pd.DatetimeIndex) -> Frequency:
    """Infer the sampling frequency from the median spacing between observations.

    Uses the median calendar-day gap so that weekends and holidays in daily data
    (gaps of 3-4 days) do not distort the result.
    """
    if len(index) < 3:
        raise InsufficientDataError("At least 3 dates are required to infer the data frequency.")
    gaps = np.diff(index.values).astype("timedelta64[D]").astype(float)
    median_gap = float(np.median(gaps))
    if median_gap <= 4:
        return Frequency.DAILY
    if median_gap <= 10:
        return Frequency.WEEKLY
    if median_gap <= 45:
        return Frequency.MONTHLY
    if median_gap <= 135:
        return Frequency.QUARTERLY
    return Frequency.ANNUAL
