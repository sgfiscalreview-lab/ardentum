"""Sharpe ratio confidence interval and the test of equal Sharpe ratios.

References: the moment formula for the Sharpe ratio's variance (Lo 2002 for independent
normal returns; Mertens 2002 with skewness and kurtosis), the Jobson-Korkie test with
Memmel's (2003) correction, and simulation for coverage and size.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from ardentum.quant.errors import InvalidInputError, UndefinedMetricError
from ardentum.quant.metrics import (
    newey_west_lags,
    performance_summary,
    sharpe_difference_test,
    sharpe_ratio,
    sharpe_ratio_interval,
)

Z95 = 1.959963984540054


def _mertens_se(x: np.ndarray, periods_per_year: int) -> float:
    """sqrt((1 + SR^2/2 - skew SR + (kurt - 3)/4 SR^2) / T), population moments, annualised."""
    mu = x.mean()
    d = x - mu
    m2, m3, m4 = (d**2).mean(), (d**3).mean(), (d**4).mean()
    sr = mu / math.sqrt(m2)
    skew, kurt = m3 / m2**1.5, m4 / m2**2
    var = (1 + sr**2 / 2 - skew * sr + (kurt - 3) / 4 * sr**2) / len(x)
    return math.sqrt(var * periods_per_year)


def _jkm_p_value(a: np.ndarray, b: np.ndarray) -> float:
    """Jobson-Korkie test of equal Sharpe ratios with Memmel's correction (normal, i.i.d.)."""
    t = len(a)
    mu_a, mu_b = a.mean(), b.mean()
    s_a, s_b = a.std(ddof=1), b.std(ddof=1)
    s_ab = float(np.cov(a, b, ddof=1)[0, 1])
    theta = (
        2 * s_a**2 * s_b**2
        - 2 * s_a * s_b * s_ab
        + 0.5 * mu_a**2 * s_b**2
        + 0.5 * mu_b**2 * s_a**2
        - (mu_a * mu_b / (s_a * s_b)) * s_ab**2
    ) / t
    z = (s_b * mu_a - s_a * mu_b) / math.sqrt(theta)
    return float(2 * stats.norm.sf(abs(z)))


def _ar1(shocks: np.ndarray, phi: float) -> np.ndarray:
    x = np.empty_like(shocks)
    x[0] = shocks[0]
    for i in range(1, len(shocks)):
        x[i] = phi * x[i - 1] + shocks[i]
    return x


def test_without_lags_the_standard_error_is_the_moment_formula() -> None:
    # Skewed returns, so the skewness and kurtosis terms matter.
    rng = np.random.default_rng(4)
    x = rng.lognormal(0.0, 0.5, 300) * 0.02 - 0.015
    iv = sharpe_ratio_interval(x, 12, lags=0)
    assert iv.standard_error == pytest.approx(_mertens_se(x, 12), rel=1e-10)
    assert iv.sharpe == pytest.approx(sharpe_ratio(x, 12))
    assert iv.low == pytest.approx(iv.sharpe - Z95 * iv.standard_error)
    assert iv.high == pytest.approx(iv.sharpe + Z95 * iv.standard_error)


def test_known_answer_zero_mean_symmetric_returns() -> None:
    # SR = 0, no skew, kurtosis 1: variance (1 + 0 - 0 + 0) / T, so SE = sqrt(12 / 120).
    x = np.array([0.01, -0.01] * 60)
    assert sharpe_ratio_interval(x, 12, lags=0).standard_error == pytest.approx(math.sqrt(12 / 120))


def test_normal_returns_give_lo_formula() -> None:
    rng = np.random.default_rng(8)
    x = rng.normal(0.0004, 0.01, 20_000)
    sr_period = x.mean() / x.std()
    lo = math.sqrt((1 + sr_period**2 / 2) / len(x)) * math.sqrt(252)
    assert sharpe_ratio_interval(x, 252).standard_error == pytest.approx(lo, rel=0.05)


def test_the_interval_covers_the_true_sharpe_ratio_about_95_percent_of_the_time() -> None:
    rng = np.random.default_rng(11)
    true_sr = 0.1 * math.sqrt(12)
    hits = sum(
        iv.low <= true_sr <= iv.high
        for iv in (sharpe_ratio_interval(rng.normal(0.004, 0.04, 240), 12) for _ in range(1500))
    )
    assert 0.93 < hits / 1500 < 0.97


def test_with_autocorrelation_the_robust_interval_covers_better_than_lo() -> None:
    # Positively autocorrelated returns: the i.i.d. formula is too narrow.
    rng = np.random.default_rng(12)
    phi, t, trials = 0.4, 480, 600
    true_sr = 0.003 / (0.03 / math.sqrt(1 - phi**2)) * math.sqrt(12)
    robust = iid = 0
    for _ in range(trials):
        x = 0.003 + _ar1(rng.normal(0.0, 0.03, t), phi)
        iv = sharpe_ratio_interval(x, 12)
        robust += iv.low <= true_sr <= iv.high
        se_lo = math.sqrt((1 + (iv.sharpe**2 / 12) / 2) / t) * math.sqrt(12)
        iid += abs(iv.sharpe - true_sr) <= Z95 * se_lo
    assert robust / trials > iid / trials + 0.05
    assert robust / trials > 0.88


def test_identical_series_are_not_different() -> None:
    x = np.random.default_rng(2).normal(0.005, 0.04, 240)
    d = sharpe_difference_test(x, x, 12)
    assert (d.difference, d.standard_error, d.p_value) == (0.0, 0.0, 1.0)


def test_difference_test_agrees_with_jobson_korkie_memmel_for_normal_returns() -> None:
    # With no autocorrelation allowed and normal data both estimate the same variance.
    rng = np.random.default_rng(21)
    cov = np.array([[0.0016, 0.0010], [0.0010, 0.0025]])
    a, b = rng.multivariate_normal([0.008, 0.004], cov, 20_000).T
    d = sharpe_difference_test(a, b, 12, lags=0)
    assert d.difference == pytest.approx(sharpe_ratio(a, 12) - sharpe_ratio(b, 12))
    assert d.z == pytest.approx(d.difference / d.standard_error)
    assert d.p_value == pytest.approx(_jkm_p_value(a, b), abs=0.02)


def test_difference_test_size_with_fat_tails_and_autocorrelation() -> None:
    # Equal true Sharpe ratios, Student-t shocks, correlated series and AR(1) dependence:
    # rejections at 5% stay near 5% (loose bounds for 800 trials).
    rng = np.random.default_rng(9)
    rejections, trials, t = 0, 800, 480
    for _ in range(trials):
        shocks = rng.standard_t(5, size=(t, 2)) * 0.03
        shocks[:, 1] = 0.6 * shocks[:, 0] + 0.8 * shocks[:, 1]
        x = _ar1(shocks, 0.2)
        rejections += sharpe_difference_test(0.005 + x[:, 0], 0.005 + x[:, 1], 12).p_value < 0.05
    assert 0.02 < rejections / trials < 0.09


def test_difference_test_detects_a_large_difference() -> None:
    rng = np.random.default_rng(5)
    a = rng.normal(0.02, 0.04, 600)
    b = rng.normal(0.0, 0.04, 600)
    d = sharpe_difference_test(a, b, 12)
    assert d.difference > 1.0
    assert d.p_value < 1e-6


def test_risk_free_rate_is_subtracted_before_inference() -> None:
    rng = np.random.default_rng(6)
    x = rng.normal(0.006, 0.03, 300)
    iv = sharpe_ratio_interval(x, 12, risk_free_rate=0.03)
    assert iv.sharpe == pytest.approx(sharpe_ratio(x, 12, 0.03))
    assert iv.sharpe < sharpe_ratio_interval(x, 12).sharpe


def test_refusals() -> None:
    with pytest.raises(UndefinedMetricError, match="at least 24 returns"):
        sharpe_ratio_interval(np.linspace(-0.01, 0.01, 23), 12)
    with pytest.raises(UndefinedMetricError, match="zero volatility"):
        sharpe_ratio_interval(np.full(60, 0.01), 12)
    with pytest.raises(InvalidInputError, match="same dates"):
        sharpe_difference_test(np.linspace(-0.01, 0.02, 60), np.linspace(-0.01, 0.02, 61), 12)
    with pytest.raises(InvalidInputError, match="Confidence"):
        sharpe_ratio_interval(np.linspace(-0.01, 0.02, 60), 12, confidence=1.2)


def test_performance_summary_carries_the_interval_or_why_not() -> None:
    rng = np.random.default_rng(1)
    summary = performance_summary(rng.normal(0.0005, 0.01, 500), 252)
    assert summary.sharpe_interval is not None
    assert summary.sharpe_interval.low < summary.sharpe_interval.high
    assert summary.sharpe_interval.confidence == 0.95
    short = performance_summary(rng.normal(0.0005, 0.01, 10), 252)
    assert short.sharpe_interval is None
    assert short.sharpe_interval_reason is not None
    assert "at least 24 returns" in short.sharpe_interval_reason


def test_newey_west_lags() -> None:
    assert newey_west_lags(100) == 4
    assert newey_west_lags(680) == 6
