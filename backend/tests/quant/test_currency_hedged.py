"""Currency-hedged conversion: closed forms, carry, no look-ahead and coverage checks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ardentum.quant.currency import convert_prices, convert_prices_hedged, hedged_returns
from ardentum.quant.errors import InsufficientDataError, InvalidInputError


def _days(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _const(value: float, idx: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(value, index=idx)


def test_constant_price_earns_exactly_the_carry_whatever_the_fx_path() -> None:
    idx = _days(60)
    rng = np.random.default_rng(1)
    prices = _const(100.0, idx)
    fx = pd.Series(1.1 * np.exp(np.cumsum(rng.normal(0, 0.01, 60))), idx)
    i_b, i_l = 0.05, 0.01
    out = convert_prices_hedged(prices, fx, _const(i_b, idx), _const(i_l, idx))
    r = out.pct_change().dropna()
    carry = (1 + i_b / 365) / (1 + i_l / 365) - 1
    assert r.to_numpy() == pytest.approx(np.full(59, carry), abs=1e-15)
    assert out.iloc[0] == pytest.approx(100.0 * fx.iloc[0])


def test_equal_rates_and_flat_fx_give_the_local_returns() -> None:
    idx = _days(30)
    rng = np.random.default_rng(2)
    prices = pd.Series(50 * np.exp(np.cumsum(rng.normal(0, 0.02, 30))), idx)
    out = convert_prices_hedged(prices, _const(0.9, idx), _const(0.03, idx), _const(0.03, idx))
    assert out.pct_change().dropna().to_numpy() == pytest.approx(
        prices.pct_change().dropna().to_numpy(), rel=1e-12
    )


def test_two_period_closed_form() -> None:
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-08", "2024-01-15"])  # 7-day periods
    prices = pd.Series([100.0, 110.0, 99.0], idx)
    fx = pd.Series([1.0, 1.2, 0.9], idx)
    i_b = pd.Series([0.0365, 0.073, 0.0], idx)
    i_l = pd.Series([0.0, 0.0365, 0.0], idx)
    out = convert_prices_hedged(prices, fx, i_b, i_l)
    d = 7 / 365
    r1 = 0.10 * (1 + 0.2) + (1 + 0.0365 * d) / (1 + 0.0 * d) - 1
    r2 = -0.10 * (1 + (0.9 / 1.2 - 1)) + (1 + 0.073 * d) / (1 + 0.0365 * d) - 1
    assert out.to_numpy() == pytest.approx([100.0, 100 * (1 + r1), 100 * (1 + r1) * (1 + r2)])


def test_hedging_removes_most_currency_volatility() -> None:
    idx = _days(2000)
    rng = np.random.default_rng(3)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.005, 2000))), idx)
    fx = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, 2000))), idx)
    unhedged = convert_prices(prices, fx).pct_change().dropna()
    hedged = convert_prices_hedged(prices, fx, _const(0.02, idx), _const(0.02, idx))
    hedged_r = hedged.pct_change().dropna()
    local_r = prices.pct_change().dropna()
    assert hedged_r.std() < 0.6 * unhedged.std()
    assert hedged_r.std() == pytest.approx(local_r.std(), rel=0.02)


def test_no_look_ahead_in_rates() -> None:
    idx = _days(40)
    rng = np.random.default_rng(4)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 40))), idx)
    fx = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, 40))), idx)
    i_b = pd.Series(rng.uniform(0, 0.05, 40), idx)
    i_l = pd.Series(rng.uniform(0, 0.05, 40), idx)
    base = convert_prices_hedged(prices, fx, i_b, i_l)
    k = 25
    bumped = i_b.copy()
    bumped.iloc[k] += 0.5
    moved = convert_prices_hedged(prices, fx, bumped, i_l)
    # The rate at k prices the hedge for (k, k+1]: nothing up to k changes.
    assert moved.iloc[: k + 1].to_numpy() == pytest.approx(base.iloc[: k + 1].to_numpy(), rel=0)
    assert moved.iloc[k + 1] > base.iloc[k + 1]


def test_negative_rates_and_sparse_rate_series() -> None:
    idx = pd.bdate_range("2024-01-01", periods=30)
    prices = _const(10.0, idx)
    rate_idx = idx[::3]  # published every third business day
    out = convert_prices_hedged(
        prices, _const(1.0, idx), _const(-0.005, rate_idx), _const(0.01, rate_idx)
    )
    assert (out.pct_change().dropna() < 0).all()  # paying away the higher local rate


def test_coverage_and_input_checks() -> None:
    idx = _days(20)
    late = _days(10, "2024-01-15")
    with pytest.raises(InsufficientDataError, match="interest rate"):
        convert_prices_hedged(
            _const(1.0, idx), _const(1.0, idx), _const(0.01, late), _const(0.0, idx)
        )
    with pytest.raises(InvalidInputError, match="above -100%"):
        convert_prices_hedged(
            _const(1.0, idx), _const(1.0, idx), _const(-2.0, idx), _const(0.0, idx)
        )
    r = pd.Series([0.01, 0.02], index=_days(2))
    with pytest.raises(InvalidInputError, match="same dates"):
        hedged_returns(r, r.iloc[:1], r, r)
