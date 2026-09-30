"""Known-answer and simulation checks for the study statistics and the hedging set-up."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from research import stats
from research.studies.currency_hedging import investor_returns, min_variance_hedge_ratio


def test_sharpe_known_answer() -> None:
    x = np.array([0.01, 0.03, -0.01, 0.01])
    assert stats.sharpe(x) == pytest.approx(0.01 / x.std(ddof=1) * math.sqrt(12))


def test_max_drawdown_known_answer() -> None:
    # Wealth 1.1, 0.55, 0.66: worst fall is 1.1 to 0.55, i.e. -50%.
    assert stats.max_drawdown(np.array([0.1, -0.5, 0.2])) == pytest.approx(-0.5)
    assert stats.max_drawdown(np.array([0.01, 0.02])) == 0.0


def test_certainty_equivalent_known_answer() -> None:
    x = np.array([0.02, 0.0, 0.01])
    expected = 12 * (0.01 - 0.5 * 3 * x.var(ddof=1))
    assert stats.certainty_equivalent(x, gamma=3) == pytest.approx(expected)


def test_jkm_identical_series_is_not_significant() -> None:
    x = np.random.default_rng(1).normal(0.005, 0.04, 240)
    assert stats.jkm_test(x, x) == (0.0, 1.0)


def test_jkm_size_under_the_null() -> None:
    # Two correlated series with equal true Sharpe ratios: about 5% of tests reject at 5%.
    rng = np.random.default_rng(7)
    cov = np.array([[0.0016, 0.0012], [0.0012, 0.0025]])
    mu = np.array([0.004, 0.005])  # Sharpe 0.1 per month for both
    rejections = 0
    trials = 2000
    for _ in range(trials):
        a, b = rng.multivariate_normal(mu, cov, 240).T
        rejections += stats.jkm_test(a, b)[1] < 0.05
    assert 0.03 < rejections / trials < 0.07


def test_jkm_detects_a_large_difference() -> None:
    rng = np.random.default_rng(3)
    a = rng.normal(0.02, 0.03, 600)
    b = rng.normal(0.0, 0.03, 600)
    z, p = stats.jkm_test(a, b)
    assert z > 0
    assert p < 1e-6


def test_investor_returns_hand_computed() -> None:
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    us = pd.Series([0.0, 0.05, -0.02], idx)
    fx = pd.Series([0.90, 0.99, 0.891], idx)  # euro per dollar: +10%, then -10%
    eur = pd.Series(0.01, idx)
    usd = pd.Series(0.03, idx)
    out = investor_returns(us, fx, eur, usd)
    assert list(out.index) == list(idx[1:])  # first month has no start rate: dropped
    assert not out.isna().any().any()
    assert out["unhedged"].iloc[0] == pytest.approx(1.05 * 1.10 - 1)
    d = (idx[1] - idx[0]).days / 365.0
    carry = (1 + 0.01 * d) / (1 + 0.03 * d) - 1
    assert out["hedged"].iloc[0] == pytest.approx(0.05 * 1.10 + carry)


def test_min_variance_hedge_ratio_brute_force() -> None:
    rng = np.random.default_rng(11)
    idx = pd.date_range("2000-01-31", periods=300, freq="ME")
    frame = pd.DataFrame({"unhedged": rng.normal(0.006, 0.045, 300)}, idx)
    frame["hedged"] = 0.6 * frame["unhedged"] + rng.normal(0.0, 0.02, 300)
    h = min_variance_hedge_ratio(frame)
    grid = np.linspace(-1, 2, 30001)
    var = [np.var(g * frame["hedged"] + (1 - g) * frame["unhedged"], ddof=1) for g in grid]
    assert h == pytest.approx(grid[int(np.argmin(var))], abs=2e-4)
