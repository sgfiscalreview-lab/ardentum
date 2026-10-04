"""Factor exposure: the Fama-French three-factor regression.

For a return series ``r_t`` with risk-free rate ``rf_t`` the model (Fama and French 1993) is

    r_t - rf_t = alpha + b_M (Mkt_t - rf_t) + b_S SMB_t + b_H HML_t + e_t

estimated by ordinary least squares. ``Mkt - rf`` is the US market's return above the
risk-free rate, ``SMB`` (small minus big) the return of small companies' shares above large
ones', and ``HML`` (high minus low) the return of cheap shares (high book-to-market) above
expensive ones. A loading ``b`` says how much the series moved with each factor; ``alpha``
is the average return the factors do not explain.

Standard errors are Newey-West (1987) heteroskedasticity- and autocorrelation-consistent
(Bartlett kernel), with ``L = floor(4 (T/100)^(2/9))`` lags (Newey and West 1994) and the
small-sample factor ``T / (T - k)``; p-values are two-sided from Student's t with
``T - k`` degrees of freedom (``k`` coefficients including alpha).

Because the residuals of a regression with an intercept average zero, the average excess
return splits exactly into ``alpha + sum_j b_j mean(f_j)``; annualised arithmetically
(times periods per year) this is the decomposition reported.

Factor data are daily. For weekly or monthly returns each period's factor returns are
compounded from the days inside it: ``rf`` and the market (``Mkt - rf + rf``) as returns,
``Mkt - rf`` as their difference, and ``SMB`` and ``HML`` as the return of holding each
long-short position through the period.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from ardentum.quant.errors import InsufficientDataError, InvalidInputError

FACTORS = ("MKT_RF", "SMB", "HML")
MIN_OBSERVATIONS = 30


@dataclass(frozen=True)
class PeriodFactors:
    """Factor and risk-free returns over each period of a return series."""

    frame: pd.DataFrame  # columns FACTORS + ("RF",), indexed by period end
    dropped_before: int  # periods starting before the factor data
    dropped_after: int  # periods ending after the factor data
    dropped_empty: int  # periods with no factor day inside


def period_factors(daily: pd.DataFrame, period_ends: pd.DatetimeIndex) -> PeriodFactors:
    """Compound daily factors over ``(period_ends[k-1], period_ends[k]]`` for ``k >= 1``.

    ``daily`` has columns ``MKT_RF``, ``SMB``, ``HML`` and ``RF`` as decimal daily returns.
    Periods not fully covered by the factor data are dropped and counted.
    """
    missing = [c for c in (*FACTORS, "RF") if c not in daily.columns]
    if missing:
        raise InvalidInputError(f"Factor data lacks columns: {', '.join(missing)}.")
    if len(period_ends) < 2:
        raise InsufficientDataError("At least two dates are needed to form a period.")
    d = daily.sort_index()
    ends = pd.DatetimeIndex(period_ends)
    first, last = d.index[0], d.index[-1]

    k = ends.searchsorted(pd.DatetimeIndex(d.index), side="left")  # first end >= day
    inside = (k >= 1) & (k < len(ends))
    groups = pd.Series(k[inside], index=d.index[inside])
    vals = d.loc[inside]
    growth = pd.DataFrame(
        {
            "MKT": (1.0 + vals["MKT_RF"] + vals["RF"]).groupby(groups.to_numpy()).prod(),
            "RF": (1.0 + vals["RF"]).groupby(groups.to_numpy()).prod(),
            "SMB": (1.0 + vals["SMB"]).groupby(groups.to_numpy()).prod(),
            "HML": (1.0 + vals["HML"]).groupby(groups.to_numpy()).prod(),
        }
    )
    out = pd.DataFrame(
        {
            "MKT_RF": growth["MKT"] - growth["RF"],
            "SMB": growth["SMB"] - 1.0,
            "HML": growth["HML"] - 1.0,
            "RF": growth["RF"] - 1.0,
        }
    )
    positions = np.arange(1, len(ends))
    before = ends[positions - 1] < first  # the period starts before the factor data
    after = ends[positions] > last  # the period ends after the factor data
    covered = positions[~before & ~after]
    present = np.intersect1d(covered, out.index.to_numpy())
    frame = out.loc[present]
    frame.index = ends[present]
    return PeriodFactors(
        frame=frame[[*FACTORS, "RF"]],
        dropped_before=int(before.sum()),
        dropped_after=int(after.sum()),
        dropped_empty=int(len(covered) - len(present)),
    )


@dataclass(frozen=True)
class FactorRegression:
    names: tuple[str, ...]
    coefficients: np.ndarray  # alpha first, then one loading per factor (per period)
    std_errors: np.ndarray
    t_stats: np.ndarray
    p_values: np.ndarray
    r_squared: float
    adj_r_squared: float
    residual_volatility: float  # annualised
    observations: int
    lags: int
    mean_excess_return: float  # annualised (arithmetic)
    factor_means: np.ndarray  # annualised mean of each factor
    periods_per_year: int

    @property
    def alpha(self) -> float:
        """Annualised alpha (per-period alpha times periods per year)."""
        return float(self.coefficients[0] * self.periods_per_year)

    @property
    def loadings(self) -> np.ndarray:
        return self.coefficients[1:]

    @property
    def contributions(self) -> np.ndarray:
        """Each factor's part of the annualised mean excess return: ``b_j mean(f_j)``."""
        return np.asarray(self.loadings * self.factor_means)


def newey_west_lags(n: int) -> int:
    """Newey and West (1994) rule of thumb: ``floor(4 (n/100)^(2/9))``."""
    return math.floor(4.0 * math.pow(n / 100.0, 2.0 / 9.0))


def ols_hac(y: np.ndarray, x: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OLS coefficients, their Newey-West covariance and the residuals.

    ``x`` includes the constant column. The covariance is
    ``T/(T-k) (X'X)^-1 S (X'X)^-1`` with Bartlett weights ``1 - l/(L+1)`` in ``S``.
    """
    n, k = x.shape
    xtx = x.T @ x
    try:
        xtx_inv = np.linalg.inv(xtx)
    except np.linalg.LinAlgError as exc:
        raise InvalidInputError("The factors are collinear in this window.") from exc
    if np.linalg.cond(xtx) > 1e12:
        raise InvalidInputError("The factors are collinear in this window.")
    beta = xtx_inv @ (x.T @ y)
    u = y - x @ beta
    xu = x * u[:, None]
    s = xu.T @ xu
    for lag in range(1, lags + 1):
        g = xu[lag:].T @ xu[:-lag]
        s += (1.0 - lag / (lags + 1.0)) * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv * (n / (n - k))
    return beta, cov, u


def factor_regression(
    excess_returns: np.ndarray,
    factors: np.ndarray,
    periods_per_year: int,
    names: tuple[str, ...] = FACTORS,
    lags: int | None = None,
) -> FactorRegression:
    """Regress per-period excess returns on per-period factor returns (with alpha)."""
    y = np.asarray(excess_returns, dtype=float)
    f = np.asarray(factors, dtype=float)
    if f.ndim != 2 or f.shape[0] != y.shape[0] or f.shape[1] != len(names):
        raise InvalidInputError(
            "Factor returns must have one column per factor and one row per return."
        )
    if not (np.isfinite(y).all() and np.isfinite(f).all()):
        raise InvalidInputError("Returns or factors contain missing or non-finite values.")
    n = y.shape[0]
    k = f.shape[1] + 1
    if n < MIN_OBSERVATIONS:
        raise InsufficientDataError(
            f"Only {n} periods overlap the factor data; at least {MIN_OBSERVATIONS} are needed."
        )
    if np.ptp(y) == 0.0:
        raise InvalidInputError("The returns do not vary, so factor loadings are undefined.")
    nlags = newey_west_lags(n) if lags is None else int(lags)
    if nlags < 0 or nlags >= n:
        raise InvalidInputError("The number of Newey-West lags must be between 0 and T - 1.")
    x = np.column_stack([np.ones(n), f])
    beta, cov, u = ols_hac(y, x, nlags)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2.0 * stats.t.sf(np.abs(t), df=n - k)
    ssr = float(u @ u)
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ssr / sst
    adj = 1.0 - (1.0 - r2) * (n - 1) / (n - k)
    return FactorRegression(
        names=tuple(names),
        coefficients=beta,
        std_errors=se,
        t_stats=t,
        p_values=p,
        r_squared=r2,
        adj_r_squared=adj,
        residual_volatility=math.sqrt(ssr / (n - k)) * math.sqrt(periods_per_year),
        observations=n,
        lags=nlags,
        mean_excess_return=float(y.mean() * periods_per_year),
        factor_means=f.mean(axis=0) * periods_per_year,
        periods_per_year=periods_per_year,
    )
