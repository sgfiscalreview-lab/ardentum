"""Statistics used by the studies (all on periodic excess returns unless stated)."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def sharpe(excess: np.ndarray, periods_per_year: int = 12) -> float:
    return float(excess.mean() / excess.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe_standard_error(excess: np.ndarray, periods_per_year: int = 12) -> float:
    """Standard error of the annualised Sharpe ratio for independent returns (Lo, 2002).

    SE of the per-period ratio is sqrt((1 + SR^2 / 2) / T); annualising multiplies by
    sqrt(periods_per_year), like the ratio itself.
    """
    sr = excess.mean() / excess.std(ddof=1)
    return float(math.sqrt((1 + 0.5 * sr**2) / len(excess)) * math.sqrt(periods_per_year))


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


def newey_west_lags(t: int) -> int:
    """Newey and West (1994) rule of thumb for the number of autocovariance lags."""
    return int(4 * (t / 100) ** (2 / 9))


def robust_sharpe_test(
    a: np.ndarray, b: np.ndarray, lags: int | None = None, periods_per_year: int = 12
) -> tuple[float, float, float]:
    """Difference of Sharpe ratios with a heteroskedasticity- and autocorrelation-robust
    (HAC) standard error, following Ledoit and Wolf (2008, section 3.1).

    The Jobson-Korkie-Memmel test assumes independent, normal returns; this one does not.
    The difference is a function of the first and second moments of the two series; its
    variance comes from the delta method with a Newey-West (Bartlett kernel) estimate of the
    long-run covariance of those moments. Ledoit and Wolf use a quadratic-spectral kernel
    with prewhitening or a bootstrap; the Bartlett kernel is a simpler, standard choice.

    Returns (annualised difference a minus b, its standard error, two-sided p-value).
    """
    t = len(a)
    lags = newey_west_lags(t) if lags is None else lags
    mu_a, mu_b = a.mean(), b.mean()
    g_a, g_b = (a**2).mean(), (b**2).mean()
    var_a, var_b = g_a - mu_a**2, g_b - mu_b**2
    diff = mu_a / math.sqrt(var_a) - mu_b / math.sqrt(var_b)
    grad = np.array(
        [
            g_a / var_a**1.5,
            -g_b / var_b**1.5,
            -0.5 * mu_a / var_a**1.5,
            0.5 * mu_b / var_b**1.5,
        ]
    )
    y = np.column_stack([a - mu_a, b - mu_b, a**2 - g_a, b**2 - g_b])
    psi = y.T @ y / t
    for j in range(1, lags + 1):
        gamma = y[j:].T @ y[:-j] / t
        psi += (1 - j / (lags + 1)) * (gamma + gamma.T)
    se = math.sqrt(max(float(grad @ psi @ grad), 0.0) / t)
    scale = math.sqrt(periods_per_year)
    if se == 0.0:
        return float(diff * scale), 0.0, 1.0
    p = 2 * (1 - stats.norm.cdf(abs(diff / se)))
    return float(diff * scale), float(se * scale), float(p)


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
