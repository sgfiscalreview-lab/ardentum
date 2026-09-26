"""Estimation of expected returns and covariance matrices from historical returns.

Every estimate produced here is exactly that: a *statistical estimate* from a
finite historical sample, not an observed or guaranteed quantity. Expected-return
estimates in particular carry large sampling error (the standard error of an
annualised mean is roughly ``sigma / sqrt(years)``), which is why shrinkage
estimators are offered and why the optimiser's outputs are reported with
explicit assumptions.

Annualisation
-------------
Inputs are per-period *simple* returns. Estimates are annualised linearly:
``mu_annual = P * mean(r)`` and ``Sigma_annual = P * Cov(r)``. Under this
convention the ex-ante Sharpe ratio of a constant-mix portfolio computed from
the annualised inputs equals its ex-post annualised Sharpe ratio on the same
sample, provided the risk-free rate is converted the same way
(:func:`risk_free_arithmetic`).

Estimators
----------
* ``historical`` mean: sample arithmetic mean.
* ``bayes_stein`` mean: Jorion (1986), "Bayes-Stein Estimation for Portfolio
  Analysis", JFQA 21(3). Shrinks sample means toward the mean of the global
  minimum-variance portfolio with a data-determined intensity.
* ``sample`` covariance: unbiased sample covariance (ddof = 1).
* ``ledoit_wolf`` covariance: Ledoit & Wolf (2004), "A well-conditioned estimator
  for large-dimensional covariance matrices", JMVA 88(2). Target: scaled identity.
* ``ledoit_wolf_constant_correlation``: Ledoit & Wolf (2004), "Honey, I Shrunk the
  Sample Covariance Matrix", JPM 30(4). Target: constant-correlation matrix.
  Both Ledoit-Wolf estimators use the 1/T (maximum-likelihood) normalisation of
  the original papers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.returns import annual_rate_to_periodic, validate_returns

MIN_ESTIMATION_OBSERVATIONS = 24


class MeanEstimator(StrEnum):
    HISTORICAL = "historical"
    BAYES_STEIN = "bayes_stein"


class CovarianceEstimator(StrEnum):
    SAMPLE = "sample"
    LEDOIT_WOLF = "ledoit_wolf"
    LEDOIT_WOLF_CONSTANT_CORRELATION = "ledoit_wolf_constant_correlation"


@dataclass(frozen=True)
class MarketEstimates:
    """Annualised inputs for portfolio construction, with their provenance."""

    tickers: tuple[str, ...]
    expected_returns: np.ndarray  # annualised arithmetic expected returns
    covariance: np.ndarray  # annualised covariance
    periods_per_year: int
    observations: int
    start: date | None
    end: date | None
    mean_estimator: MeanEstimator
    covariance_estimator: CovarianceEstimator
    mean_shrinkage: float | None = None  # Bayes-Stein intensity phi in [0, 1]
    covariance_shrinkage: float | None = None  # Ledoit-Wolf intensity delta in [0, 1]

    @property
    def n_assets(self) -> int:
        return len(self.tickers)

    @property
    def volatilities(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.covariance), 0.0, None))

    def risk_free_arithmetic(self, risk_free_rate: float) -> float:
        return risk_free_arithmetic(risk_free_rate, self.periods_per_year)

    def subset(self, tickers: list[str]) -> MarketEstimates:
        idx = [self.tickers.index(t) for t in tickers]
        return MarketEstimates(
            tickers=tuple(tickers),
            expected_returns=self.expected_returns[idx],
            covariance=self.covariance[np.ix_(idx, idx)],
            periods_per_year=self.periods_per_year,
            observations=self.observations,
            start=self.start,
            end=self.end,
            mean_estimator=self.mean_estimator,
            covariance_estimator=self.covariance_estimator,
            mean_shrinkage=self.mean_shrinkage,
            covariance_shrinkage=self.covariance_shrinkage,
        )


def risk_free_arithmetic(risk_free_rate: float, periods_per_year: int) -> float:
    """Annual effective risk-free rate expressed on the linear-annualisation scale.

    ``P * ((1 + rf)^(1/P) - 1)``: the per-period compounded rate times ``P``. This
    makes ex-ante excess returns ``mu - rf`` consistent with ``mu = P * mean(r)``.
    """
    return periods_per_year * annual_rate_to_periodic(risk_free_rate, periods_per_year)


def _returns_array(returns: pd.DataFrame, min_obs: int) -> np.ndarray:
    if not isinstance(returns, pd.DataFrame):
        raise InvalidInputError("Returns must be a DataFrame with one column per asset.")
    if returns.shape[1] == 0:
        raise InvalidInputError("At least one asset is required.")
    x = returns.to_numpy(dtype=float)
    validate_returns(x, min_obs=min_obs)
    return x


def historical_mean(returns: pd.DataFrame, periods_per_year: int) -> np.ndarray:
    """Annualised arithmetic sample mean of simple returns."""
    x = _returns_array(returns, 2)
    return np.asarray(x.mean(axis=0) * periods_per_year)


def bayes_stein_mean(returns: pd.DataFrame, periods_per_year: int) -> tuple[np.ndarray, float]:
    """Jorion (1986) Bayes-Stein shrinkage of the mean. Returns (annual means, phi)."""
    x = _returns_array(returns, 2)
    t, n = x.shape
    if t <= n + 2:
        raise InsufficientDataError(
            f"Bayes-Stein estimation needs more observations ({t}) than assets + 2 ({n + 2})."
        )
    mu = x.mean(axis=0)
    s = np.atleast_2d(np.cov(x, rowvar=False, ddof=1)) * (t - 1) / (t - n - 2)
    s_inv = np.linalg.pinv(s)
    ones = np.ones(n)
    mu0 = float(ones @ s_inv @ mu / (ones @ s_inv @ ones))
    d = mu - mu0
    phi = float((n + 2) / ((n + 2) + t * d @ s_inv @ d))
    shrunk = (1.0 - phi) * mu + phi * mu0
    return shrunk * periods_per_year, phi


def sample_covariance(returns: pd.DataFrame, periods_per_year: int) -> np.ndarray:
    """Annualised unbiased sample covariance."""
    x = _returns_array(returns, 2)
    return np.atleast_2d(np.cov(x, rowvar=False, ddof=1)) * periods_per_year


def ledoit_wolf_covariance(
    returns: pd.DataFrame, periods_per_year: int
) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage toward a scaled identity. Returns (cov, delta)."""
    x = _returns_array(returns, 2)
    t, n = x.shape
    y = x - x.mean(axis=0)
    s = y.T @ y / t
    mu = float(np.trace(s) / n)
    target = mu * np.eye(n)
    # d^2 = ||S - mu I||_F^2 / n ; b^2 = (1/T^2) sum_t ||y_t y_t' - S||_F^2 / n, capped at d^2
    d2 = float(np.sum((s - target) ** 2) / n)
    y2 = y**2
    b2_bar = float((np.sum(y2.T @ y2) / t - np.sum(s**2)) / (t * n))
    b2 = min(b2_bar, d2)
    delta = 0.0 if d2 == 0.0 else b2 / d2
    shrunk = delta * target + (1.0 - delta) * s
    return shrunk * periods_per_year, delta


def ledoit_wolf_constant_correlation(
    returns: pd.DataFrame, periods_per_year: int
) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage toward constant correlation. Returns (cov, delta).

    Implements the estimator of "Honey, I Shrunk the Sample Covariance Matrix"
    (appendix formulas for pi-hat, rho-hat and gamma-hat).
    """
    x = _returns_array(returns, 2)
    t, n = x.shape
    if n < 2:
        cov = sample_covariance(returns, periods_per_year) * (t - 1) / t
        return cov, 0.0
    y = x - x.mean(axis=0)
    s = y.T @ y / t
    var = np.diag(s)
    if (var <= 0).any():
        raise InvalidInputError("Constant-correlation shrinkage requires non-constant returns.")
    sd = np.sqrt(var)
    corr = s / np.outer(sd, sd)
    r_bar = float((corr.sum() - n) / (n * (n - 1)))
    prior = r_bar * np.outer(sd, sd)
    np.fill_diagonal(prior, var)

    y2 = y**2
    pi_mat = y2.T @ y2 / t - s**2
    pi_hat = float(pi_mat.sum())

    theta = (y**3).T @ y / t - var[:, None] * s
    np.fill_diagonal(theta, 0.0)
    rho_hat = float(np.trace(pi_mat) + r_bar * np.sum(np.outer(1.0 / sd, sd) * theta))

    gamma_hat = float(np.sum((s - prior) ** 2))
    if gamma_hat == 0.0:
        return s * periods_per_year, 0.0
    kappa = (pi_hat - rho_hat) / gamma_hat
    delta = float(max(0.0, min(1.0, kappa / t)))
    shrunk = delta * prior + (1.0 - delta) * s
    return shrunk * periods_per_year, delta


def estimate(
    returns: pd.DataFrame,
    periods_per_year: int,
    *,
    mean_estimator: MeanEstimator = MeanEstimator.HISTORICAL,
    covariance_estimator: CovarianceEstimator = CovarianceEstimator.LEDOIT_WOLF,
    min_observations: int = MIN_ESTIMATION_OBSERVATIONS,
) -> MarketEstimates:
    """Estimate annualised expected returns and covariance from a returns window."""
    x = _returns_array(returns, min_observations)
    t, n = x.shape
    if covariance_estimator is CovarianceEstimator.SAMPLE and t <= n:
        raise InsufficientDataError(
            f"The sample covariance of {n} assets is singular with only {t} observations. "
            "Use a Ledoit-Wolf shrinkage estimator or a longer estimation window."
        )

    mean_shrinkage: float | None = None
    if mean_estimator is MeanEstimator.HISTORICAL:
        mu = historical_mean(returns, periods_per_year)
    elif mean_estimator is MeanEstimator.BAYES_STEIN:
        mu, mean_shrinkage = bayes_stein_mean(returns, periods_per_year)
    else:  # pragma: no cover - exhaustive enum
        raise InvalidInputError(f"Unknown mean estimator {mean_estimator!r}.")

    cov_shrinkage: float | None = None
    if covariance_estimator is CovarianceEstimator.SAMPLE:
        cov = sample_covariance(returns, periods_per_year)
    elif covariance_estimator is CovarianceEstimator.LEDOIT_WOLF:
        cov, cov_shrinkage = ledoit_wolf_covariance(returns, periods_per_year)
    elif covariance_estimator is CovarianceEstimator.LEDOIT_WOLF_CONSTANT_CORRELATION:
        cov, cov_shrinkage = ledoit_wolf_constant_correlation(returns, periods_per_year)
    else:  # pragma: no cover - exhaustive enum
        raise InvalidInputError(f"Unknown covariance estimator {covariance_estimator!r}.")

    index = returns.index
    start = index[0].date() if isinstance(index, pd.DatetimeIndex) else None
    end = index[-1].date() if isinstance(index, pd.DatetimeIndex) else None
    return MarketEstimates(
        tickers=tuple(str(c) for c in returns.columns),
        expected_returns=np.asarray(mu, dtype=float),
        covariance=0.5 * (cov + cov.T),
        periods_per_year=periods_per_year,
        observations=t,
        start=start,
        end=end,
        mean_estimator=mean_estimator,
        covariance_estimator=covariance_estimator,
        mean_shrinkage=mean_shrinkage,
        covariance_shrinkage=cov_shrinkage,
    )
