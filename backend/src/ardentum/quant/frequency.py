"""Sampling frequency of return series and annualisation factors."""

from __future__ import annotations

from enum import StrEnum

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError


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


_ORDER = (
    Frequency.DAILY,
    Frequency.WEEKLY,
    Frequency.MONTHLY,
    Frequency.QUARTERLY,
    Frequency.ANNUAL,
)
_DESCRIBE = {
    Frequency.DAILY: "every trading day",
    Frequency.WEEKLY: "about once a week",
    Frequency.MONTHLY: "about once a month",
    Frequency.QUARTERLY: "about once a quarter",
    Frequency.ANNUAL: "about once a year",
}


def check_frequency(index: pd.DatetimeIndex, requested: Frequency) -> None:
    """Refuses a return frequency the prices cannot support, instead of annualising wrongly.

    Returns are annualised with 252, 52 or 12 periods a year (D-006). Asking for daily
    returns from monthly prices would scale volatility by sqrt(252) instead of sqrt(12),
    about 4.6 times too large; daily prices that include weekends (calendar days) would be
    annualised as if a year had 252 of them, understating volatility by about a sixth.
    """
    if len(index) < 3:
        return  # too short to tell; the observation minimum reports it
    native = infer_frequency(index)
    if _ORDER.index(native) > _ORDER.index(requested):
        gaps = np.diff(index.values).astype("timedelta64[D]").astype(float)
        choice = (
            native.value.capitalize() if native in (Frequency.WEEKLY, Frequency.MONTHLY) else None
        )
        fix = (
            f"Choose {choice} as the return frequency."
            if choice
            else "At least monthly prices are needed."
        )
        raise InvalidInputError(
            f"These prices come {_DESCRIBE[native]} (a median of {np.median(gaps):.0f} days "
            f"apart), so {requested.value} returns cannot be computed from them: they would be "
            f"annualised as if there were {requested.periods_per_year} a year. {fix}"
        )
    if requested is Frequency.DAILY:
        weekend = float(np.mean(index.dayofweek >= 5))
        if weekend > 0.1:
            raise InvalidInputError(
                f"{weekend:.0%} of the price dates fall on a weekend, so these look like calendar "
                "days. Daily statistics assume 252 trading days a year; choose Weekly or Monthly "
                "as the return frequency, or upload trading days only."
            )


# The return frequencies a user can choose, finest first.
RETURN_FREQUENCIES = (Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY)


def supported_frequencies(index: pd.DatetimeIndex) -> tuple[list[Frequency], list[str]]:
    """The return frequencies these prices support, finest first, and why each frequency
    finer than the finest supported one is refused (the :func:`check_frequency` message)."""
    supported: list[Frequency] = []
    refused: list[str] = []
    for f in RETURN_FREQUENCIES:
        try:
            check_frequency(index, f)
        except InvalidInputError as exc:
            if not supported:
                refused.append(str(exc))
            continue
        supported.append(f)
    return supported, refused


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
