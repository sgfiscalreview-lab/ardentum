"""Statistics used by the studies (all on periodic excess returns unless stated)."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def sharpe(excess: np.ndarray, periods_per_year: int = 12) -> float:
    return float(excess.mean() / excess.std(ddof=1) * math.sqrt(periods_per_year))


def jkm_test(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Jobson-Korkie test of equal Sharpe ratios with Memmel's (2003) correction.

    ``a`` and ``b`` are periodic excess returns over the same dates. Returns (z, two-sided p).
    This is the test DeMiguel, Garlappi and Uppal (2009) report.
    """
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
    if theta <= 1e-18:  # identical series (e.g. a strategy compared with itself)
        return 0.0, 1.0
    z = (s_b * mu_a - s_a * mu_b) / math.sqrt(theta)
    return float(z), float(2 * (1 - stats.norm.cdf(abs(z))))


def certainty_equivalent(
    excess: np.ndarray, gamma: float = 1.0, periods_per_year: int = 12
) -> float:
    """Annualised certainty-equivalent excess return mu - gamma/2 * sigma^2 (DeMiguel et al.)."""
    per = excess.mean() - gamma / 2 * excess.var(ddof=1)
    return float(per * periods_per_year)


def max_drawdown(returns: np.ndarray) -> float:
    wealth = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return float((wealth / peak - 1).min())
