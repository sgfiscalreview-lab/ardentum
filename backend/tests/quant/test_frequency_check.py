"""The return frequency asked for must be one the prices can support (no wrong scaling)."""

import pandas as pd
import pytest

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.frequency import Frequency, check_frequency


def test_monthly_prices_cannot_give_daily_or_weekly_returns() -> None:
    # Annualising monthly prices as daily scaled volatility by sqrt(252/12), about 4.6 times.
    month_ends = pd.DatetimeIndex(pd.date_range("2015-01-31", periods=120, freq="ME"))
    with pytest.raises(InvalidInputError, match=r"about once a month.*Choose Monthly"):
        check_frequency(month_ends, Frequency.DAILY)
    with pytest.raises(InvalidInputError, match=r"252 a year|52 a year"):
        check_frequency(month_ends, Frequency.WEEKLY)
    check_frequency(month_ends, Frequency.MONTHLY)


def test_weekly_prices_allow_weekly_and_monthly() -> None:
    fridays = pd.DatetimeIndex(pd.date_range("2020-01-03", periods=200, freq="W-FRI"))
    with pytest.raises(InvalidInputError, match="Choose Weekly"):
        check_frequency(fridays, Frequency.DAILY)
    check_frequency(fridays, Frequency.WEEKLY)
    check_frequency(fridays, Frequency.MONTHLY)


def test_calendar_days_are_refused_for_daily_statistics() -> None:
    calendar = pd.DatetimeIndex(pd.date_range("2023-01-02", periods=120, freq="D"))
    with pytest.raises(InvalidInputError, match=r"weekend.*252 trading days"):
        check_frequency(calendar, Frequency.DAILY)
    check_frequency(calendar, Frequency.WEEKLY)  # resampled to weeks, which is correct


def test_trading_days_pass() -> None:
    check_frequency(pd.DatetimeIndex(pd.bdate_range("2023-01-02", periods=300)), Frequency.DAILY)


def test_quarterly_prices_are_too_coarse() -> None:
    quarters = pd.DatetimeIndex(pd.date_range("2000-03-31", periods=60, freq="QE"))
    with pytest.raises(InvalidInputError, match="At least monthly prices"):
        check_frequency(quarters, Frequency.MONTHLY)
