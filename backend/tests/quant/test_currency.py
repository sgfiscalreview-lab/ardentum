"""Currency conversion and rate-annualisation identities."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ardentum.quant.currency import align_rates, convert_prices
from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.returns import annualise_periodic_rates, bill_yield_to_effective


def test_base_returns_compound_local_and_currency_returns() -> None:
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2024-01-01", periods=250)
    local = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 250)), idx)
    fx = pd.Series(1.1 * np.cumprod(1 + rng.normal(0, 0.005, 250)), idx)
    base = convert_prices(local, fx)
    r_b = base.pct_change().dropna()
    r_l = local.pct_change().dropna()
    r_x = fx.pct_change().dropna()
    np.testing.assert_allclose(1 + r_b, (1 + r_l) * (1 + r_x), rtol=1e-12)


def test_holidays_carry_last_rate_forward() -> None:
    rates = pd.Series([1.0, 2.0], pd.to_datetime(["2024-01-02", "2024-01-05"]))
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    )
    np.testing.assert_array_equal(align_rates(rates, dates).to_numpy(), [1.0, 1.0, 1.0, 2.0])


def test_prices_before_first_rate_fail_loudly() -> None:
    rates = pd.Series([1.0], pd.to_datetime(["2024-01-05"]))
    prices = pd.Series([10.0, 11.0], pd.to_datetime(["2024-01-02", "2024-01-05"]))
    with pytest.raises(InsufficientDataError, match="2024-01-02"):
        convert_prices(prices, rates)


def test_long_gap_fails_loudly() -> None:
    rates = pd.Series([1.0, 1.0], pd.to_datetime(["2024-01-01", "2024-03-01"]))
    dates = pd.DatetimeIndex(pd.bdate_range("2024-01-01", "2024-03-01"))
    with pytest.raises(InsufficientDataError, match="within 5 days"):
        align_rates(rates, dates)


def test_missing_prices_stay_missing_and_rates_must_be_positive() -> None:
    idx = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.Series([np.nan, 10.0, 11.0], idx)
    out = convert_prices(prices, pd.Series([2.0, 2.0, 2.0], idx))
    assert np.isnan(out.iloc[0])
    assert out.iloc[2] == 22.0
    with pytest.raises(InvalidInputError):
        convert_prices(prices, pd.Series([2.0, 0.0, 2.0], idx))


def test_annualise_periodic_rates_closed_form() -> None:
    assert annualise_periodic_rates(np.full(252, 0.0001), 252) == pytest.approx(1.0001**252 - 1)
    # Half a year of data annualises by squaring the half-year growth.
    r = np.full(126, 0.0002)
    assert annualise_periodic_rates(r, 252) == pytest.approx(1.0002**252 - 1)
    monthly = np.array([0.01, -0.005, 0.002] * 4)
    assert annualise_periodic_rates(monthly, 12) == pytest.approx(np.prod(1 + monthly) - 1)


def test_bill_yield_to_effective() -> None:
    # A 91-day bill at 4.010989% earns exactly 1% per roll.
    y = 0.01 * 365 / 91
    assert bill_yield_to_effective(y) == pytest.approx(1.01 ** (365 / 91) - 1)
    # Effective annual exceeds the simple yield, and they agree at zero.
    assert bill_yield_to_effective(0.05) > 0.05
    assert bill_yield_to_effective(0.0) == 0.0
    np.testing.assert_allclose(
        bill_yield_to_effective(np.array([0.02, 0.05])),
        [bill_yield_to_effective(0.02), bill_yield_to_effective(0.05)],
    )
    with pytest.raises(InvalidInputError):
        bill_yield_to_effective(0.05, days=0)
