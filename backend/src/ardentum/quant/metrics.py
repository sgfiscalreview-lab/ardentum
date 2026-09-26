"""Risk and performance metrics.

All metrics take a series of *simple* per-period returns and an explicit
``periods_per_year`` so that annualisation is never implicit. Rates such as the
risk-free rate are effective annual rates and are converted to per-period rates
geometrically (``(1 + R)^(1/P) - 1``).

Definitions (``P`` = periods per year, ``n`` = number of observations):

* Annualised volatility: ``std(r, ddof=1) * sqrt(P)`` (square-root-of-time rule,
  which assumes serially uncorrelated returns).
* Sharpe ratio (Sharpe 1994, ex-post): ``mean(r - rf) / std(r - rf) * sqrt(P)``.
* Sortino ratio (Sortino & Price 1994): ``(mean(r) - m) / DD * sqrt(P)`` with target
  downside deviation ``DD = sqrt(mean(min(r - m, 0)^2))`` over *all* observations.
* Maximum drawdown: ``min_t (W_t / max_{s<=t} W_s - 1)`` on the wealth index with the
  initial value included.
* Beta: ``cov(r_a, r_m) / var(r_m)``.
* Tracking error: ``std(r_p - r_b, ddof=1) * sqrt(P)``.
* Historical VaR / CVaR at level ``c``: the loss not exceeded with probability ``c``
  and the mean loss beyond it, reported as positive fractions of value.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy import stats

from ardentum.quant.errors import InvalidInputError, UndefinedMetricError
from ardentum.quant.returns import (
    annual_rate_to_periodic,
    annualised_return,
    validate_returns,
    wealth_index,
)

ArrayLike1D = pd.Series | np.ndarray

# Standard deviations below this are treated as zero (constant series).
_ZERO_VOL_TOL = 1e-14


def _as_array(returns: ArrayLike1D, *, min_obs: int = 2, name: str = "returns") -> np.ndarray:
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1:
        raise InvalidInputError(f"{name} must be one-dimensional.")
    validate_returns(r, min_obs=min_obs, name=name)
    return r


def annualised_volatility(returns: ArrayLike1D, periods_per_year: int) -> float:
    """Sample standard deviation (ddof=1) scaled by ``sqrt(P)``."""
    r = _as_array(returns)
    return float(r.std(ddof=1) * np.sqrt(periods_per_year))


def covariance_matrix(returns: pd.DataFrame, periods_per_year: int) -> pd.DataFrame:
    """Annualised sample covariance matrix (ddof=1)."""
    arr = returns.to_numpy(dtype=float)
    validate_returns(arr, min_obs=2)
    cov = np.cov(arr, rowvar=False, ddof=1) * periods_per_year
    cov = np.atleast_2d(cov)
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix. Raises if any asset has zero variance."""
    arr = returns.to_numpy(dtype=float)
    validate_returns(arr, min_obs=2)
    std = arr.std(axis=0, ddof=1)
    constant = [str(c) for c, s in zip(returns.columns, std, strict=True) if s < _ZERO_VOL_TOL]
    if constant:
        raise UndefinedMetricError(
            f"Correlation is undefined for assets with constant returns: {', '.join(constant)}."
        )
    corr = np.atleast_2d(np.corrcoef(arr, rowvar=False))
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=returns.columns, columns=returns.columns)


def beta(asset_returns: ArrayLike1D, market_returns: ArrayLike1D) -> float:
    """OLS beta of an asset against a market/benchmark return series."""
    a = _as_array(asset_returns, name="asset returns")
    m = _as_array(market_returns, name="market returns")
    if a.shape != m.shape:
        raise InvalidInputError("Asset and market returns must have the same length and dates.")
    var_m = m.var(ddof=1)
    if var_m < _ZERO_VOL_TOL**2:
        raise UndefinedMetricError("Beta is undefined: the market return series has zero variance.")
    return float(np.cov(a, m, ddof=1)[0, 1] / var_m)


def sharpe_ratio(returns: ArrayLike1D, periods_per_year: int, risk_free_rate: float = 0.0) -> float:
    """Annualised ex-post Sharpe ratio using an effective annual risk-free rate."""
    r = _as_array(returns)
    excess = r - annual_rate_to_periodic(risk_free_rate, periods_per_year)
    sd = excess.std(ddof=1)
    if sd < _ZERO_VOL_TOL:
        raise UndefinedMetricError("Sharpe ratio is undefined: returns have zero volatility.")
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def downside_deviation(
    returns: ArrayLike1D, periods_per_year: int, minimum_acceptable_return: float = 0.0
) -> float:
    """Annualised target downside deviation below an annual minimum acceptable return."""
    r = _as_array(returns)
    mar = annual_rate_to_periodic(minimum_acceptable_return, periods_per_year)
    shortfall = np.minimum(r - mar, 0.0)
    return float(np.sqrt(np.mean(shortfall**2)) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: ArrayLike1D, periods_per_year: int, minimum_acceptable_return: float = 0.0
) -> float:
    """Annualised Sortino ratio relative to an annual minimum acceptable return (MAR)."""
    r = _as_array(returns)
    mar = annual_rate_to_periodic(minimum_acceptable_return, periods_per_year)
    dd = float(np.sqrt(np.mean(np.minimum(r - mar, 0.0) ** 2)))
    if dd < _ZERO_VOL_TOL:
        raise UndefinedMetricError(
            "Sortino ratio is undefined: no returns fell below the minimum acceptable return."
        )
    return float((r.mean() - mar) / dd * np.sqrt(periods_per_year))


@dataclass(frozen=True)
class Drawdown:
    """Maximum drawdown and its timing (positions refer to the wealth index)."""

    max_drawdown: float  # negative fraction, e.g. -0.35 for a 35% peak-to-trough loss
    peak_position: int  # index into the wealth index (0 = initial value)
    trough_position: int
    recovery_position: int | None  # first position at/above the prior peak; None if unrecovered


def drawdown_series(returns: ArrayLike1D) -> np.ndarray:
    """Drawdown at each point of the wealth index (length ``n + 1``, starts at 0)."""
    w = wealth_index(returns)
    return w / np.maximum.accumulate(w) - 1.0


def max_drawdown(returns: ArrayLike1D) -> Drawdown:
    """Largest peak-to-trough decline of the wealth index, including the initial value."""
    w = wealth_index(returns)
    running_max = np.maximum.accumulate(w)
    dd = w / running_max - 1.0
    trough = int(np.argmin(dd))
    if dd[trough] == 0.0:
        return Drawdown(0.0, 0, 0, 0)
    peak = int(np.argmax(w[: trough + 1]))
    recovered = np.nonzero(w[trough:] >= w[peak])[0]
    recovery = int(trough + recovered[0]) if recovered.size else None
    return Drawdown(float(dd[trough]), peak, trough, recovery)


def calmar_ratio(returns: ArrayLike1D, periods_per_year: int) -> float:
    """CAGR divided by the absolute maximum drawdown."""
    mdd = max_drawdown(returns).max_drawdown
    if mdd == 0.0:
        raise UndefinedMetricError("Calmar ratio is undefined: there was no drawdown.")
    return annualised_return(returns, periods_per_year) / abs(mdd)


def value_at_risk(
    returns: ArrayLike1D, confidence: float = 0.95, *, method: str = "historical"
) -> float:
    """One-period Value at Risk as a positive loss fraction.

    ``historical`` uses the empirical quantile (linear interpolation); ``gaussian``
    uses ``-(mean + z_{1-c} * std)`` which assumes normally distributed returns.
    """
    r = _as_array(returns)
    _check_confidence(confidence)
    if method == "historical":
        return float(-np.quantile(r, 1.0 - confidence))
    if method == "gaussian":
        z = stats.norm.ppf(1.0 - confidence)
        return float(-(r.mean() + z * r.std(ddof=1)))
    raise InvalidInputError(f"Unknown VaR method {method!r}.")


def conditional_value_at_risk(returns: ArrayLike1D, confidence: float = 0.95) -> float:
    """Historical expected shortfall: mean loss in the worst ``1 - c`` tail (positive)."""
    r = _as_array(returns)
    _check_confidence(confidence)
    threshold = np.quantile(r, 1.0 - confidence)
    tail = r[r <= threshold]
    return float(-tail.mean())


def tracking_error(
    portfolio_returns: ArrayLike1D, benchmark_returns: ArrayLike1D, periods_per_year: int
) -> float:
    """Annualised standard deviation of active returns."""
    p = _as_array(portfolio_returns, name="portfolio returns")
    b = _as_array(benchmark_returns, name="benchmark returns")
    if p.shape != b.shape:
        raise InvalidInputError("Portfolio and benchmark returns must be aligned.")
    return float((p - b).std(ddof=1) * np.sqrt(periods_per_year))


def information_ratio(
    portfolio_returns: ArrayLike1D, benchmark_returns: ArrayLike1D, periods_per_year: int
) -> float:
    """Annualised mean active return divided by tracking error."""
    p = _as_array(portfolio_returns, name="portfolio returns")
    b = _as_array(benchmark_returns, name="benchmark returns")
    if p.shape != b.shape:
        raise InvalidInputError("Portfolio and benchmark returns must be aligned.")
    active = p - b
    sd = active.std(ddof=1)
    if sd < _ZERO_VOL_TOL:
        raise UndefinedMetricError("Information ratio is undefined: tracking error is zero.")
    return float(active.mean() / sd * np.sqrt(periods_per_year))


def _check_confidence(confidence: float) -> None:
    if not 0.5 <= confidence < 1.0:
        raise InvalidInputError("Confidence level must be in [0.5, 1).")


@dataclass(frozen=True)
class MetricValue:
    """A metric that may be undefined; ``reason`` explains why when ``value`` is None."""

    value: float | None
    reason: str | None = None


@dataclass(frozen=True)
class PerformanceSummary:
    observations: int
    periods_per_year: int
    total_return: float
    cagr: float
    arithmetic_annual_return: float
    annualised_volatility: float
    sharpe_ratio: MetricValue
    sortino_ratio: MetricValue
    max_drawdown: float
    calmar_ratio: MetricValue
    var_95: float
    cvar_95: float
    skewness: MetricValue
    excess_kurtosis: MetricValue
    best_period: float
    worst_period: float
    positive_periods_fraction: float
    beta: MetricValue | None = None
    tracking_error: float | None = None
    information_ratio: MetricValue | None = None


def _safe(fn: object, *args: object, **kwargs: object) -> MetricValue:
    try:
        return MetricValue(float(fn(*args, **kwargs)))  # type: ignore[operator]
    except UndefinedMetricError as exc:
        return MetricValue(None, str(exc))


def performance_summary(
    returns: ArrayLike1D,
    periods_per_year: int,
    risk_free_rate: float = 0.0,
    benchmark_returns: ArrayLike1D | None = None,
) -> PerformanceSummary:
    """Compute the standard metric set; undefined metrics carry an explanation."""
    r = _as_array(returns)
    moments_defined = r.std(ddof=1) >= _ZERO_VOL_TOL and r.shape[0] >= 4
    summary = PerformanceSummary(
        observations=int(r.shape[0]),
        periods_per_year=periods_per_year,
        total_return=float(np.prod(1.0 + r) - 1.0),
        cagr=annualised_return(r, periods_per_year),
        arithmetic_annual_return=annualised_return(r, periods_per_year, method="arithmetic"),
        annualised_volatility=annualised_volatility(r, periods_per_year),
        sharpe_ratio=_safe(sharpe_ratio, r, periods_per_year, risk_free_rate),
        sortino_ratio=_safe(sortino_ratio, r, periods_per_year, risk_free_rate),
        max_drawdown=max_drawdown(r).max_drawdown,
        calmar_ratio=_safe(calmar_ratio, r, periods_per_year),
        var_95=value_at_risk(r, 0.95),
        cvar_95=conditional_value_at_risk(r, 0.95),
        skewness=(
            MetricValue(float(stats.skew(r, bias=False)))
            if moments_defined
            else MetricValue(None, "Skewness needs at least 4 non-constant observations.")
        ),
        excess_kurtosis=(
            MetricValue(float(stats.kurtosis(r, fisher=True, bias=False)))
            if moments_defined
            else MetricValue(None, "Kurtosis needs at least 4 non-constant observations.")
        ),
        best_period=float(r.max()),
        worst_period=float(r.min()),
        positive_periods_fraction=float(np.mean(r > 0.0)),
    )
    if benchmark_returns is None:
        return summary
    b = _as_array(benchmark_returns, name="benchmark returns")
    return replace(
        summary,
        beta=_safe(beta, r, b),
        tracking_error=tracking_error(r, b, periods_per_year),
        information_ratio=_safe(information_ratio, r, b, periods_per_year),
    )
