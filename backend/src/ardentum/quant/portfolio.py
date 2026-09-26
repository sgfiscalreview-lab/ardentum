"""Portfolio-level analytics: expected return, volatility, risk decomposition.

Weights are fractions of portfolio value that sum to one. Expected returns and
covariances passed here are *annualised* (see ``ardentum.quant.estimation``).

Risk decomposition (Euler allocation): portfolio volatility ``sigma_p = sqrt(w' S w)``
is homogeneous of degree one in ``w``, so ``sigma_p = sum_i w_i * d sigma_p / d w_i``.
The marginal contribution is ``(S w)_i / sigma_p`` and the (absolute) risk
contribution is ``w_i (S w)_i / sigma_p``; contributions sum exactly to ``sigma_p``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ardentum.quant.errors import InvalidInputError, UndefinedMetricError

WEIGHT_SUM_TOL = 1e-6


def validate_weights(
    weights: np.ndarray,
    n_assets: int | None = None,
    *,
    allow_short: bool = False,
    tol: float = WEIGHT_SUM_TOL,
) -> np.ndarray:
    """Return weights as a float array after checking shape, finiteness and budget."""
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1:
        raise InvalidInputError("Weights must be a one-dimensional vector.")
    if n_assets is not None and w.shape[0] != n_assets:
        raise InvalidInputError(f"Expected {n_assets} weights, received {w.shape[0]}.")
    if not np.isfinite(w).all():
        raise InvalidInputError("Weights contain missing or infinite values.")
    if abs(w.sum() - 1.0) > tol:
        raise InvalidInputError(f"Weights must sum to 1 (sum is {w.sum():.8f}).")
    if not allow_short and (w < -tol).any():
        raise InvalidInputError("Negative weights (short positions) are not allowed.")
    return w


def validate_covariance(cov: np.ndarray, *, tol: float = 1e-10) -> np.ndarray:
    """Check that ``cov`` is a finite, symmetric, positive semi-definite matrix."""
    c = np.asarray(cov, dtype=float)
    if c.ndim != 2 or c.shape[0] != c.shape[1]:
        raise InvalidInputError("Covariance matrix must be square.")
    if not np.isfinite(c).all():
        raise InvalidInputError("Covariance matrix contains missing or infinite values.")
    scale = max(float(np.abs(c).max()), 1e-300)
    if np.abs(c - c.T).max() > 1e-8 * scale:
        raise InvalidInputError("Covariance matrix must be symmetric.")
    c = 0.5 * (c + c.T)
    min_eig = float(np.linalg.eigvalsh(c).min())
    if min_eig < -tol * scale:
        raise InvalidInputError(
            f"Covariance matrix is not positive semi-definite (smallest eigenvalue {min_eig:.3e})."
        )
    return c


def portfolio_expected_return(weights: np.ndarray, expected_returns: np.ndarray) -> float:
    """``w' mu``."""
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(expected_returns, dtype=float)
    if w.shape != mu.shape:
        raise InvalidInputError("Weights and expected returns must have the same length.")
    return float(w @ mu)


def portfolio_variance(weights: np.ndarray, cov: np.ndarray) -> float:
    """``w' S w`` (clipped at zero to remove tiny negative round-off)."""
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    if c.shape != (w.shape[0], w.shape[0]):
        raise InvalidInputError("Covariance dimensions do not match the number of weights.")
    return max(float(w @ c @ w), 0.0)


def portfolio_volatility(weights: np.ndarray, cov: np.ndarray) -> float:
    """``sqrt(w' S w)``."""
    return float(np.sqrt(portfolio_variance(weights, cov)))


def portfolio_sharpe(
    weights: np.ndarray, expected_returns: np.ndarray, cov: np.ndarray, risk_free_rate: float
) -> float:
    """Ex-ante Sharpe ratio ``(w' mu - rf) / sqrt(w' S w)`` from annualised inputs."""
    vol = portfolio_volatility(weights, cov)
    if vol < 1e-14:
        raise UndefinedMetricError("Sharpe ratio is undefined for a zero-volatility portfolio.")
    return (portfolio_expected_return(weights, expected_returns) - risk_free_rate) / vol


def constant_mix_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Portfolio returns when rebalanced to ``weights`` at the start of every period."""
    w = np.asarray(weights, dtype=float)
    if returns.shape[1] != w.shape[0]:
        raise InvalidInputError("Number of weights must match the number of return columns.")
    return pd.Series(returns.to_numpy(dtype=float) @ w, index=returns.index, name="portfolio")


def buy_and_hold_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Portfolio returns for weights set once at the start and left to drift.

    Portfolio value is ``V_t = sum_i w_i prod_{s<=t}(1 + r_{i,s})``.
    """
    w = np.asarray(weights, dtype=float)
    if returns.shape[1] != w.shape[0]:
        raise InvalidInputError("Number of weights must match the number of return columns.")
    growth = np.cumprod(1.0 + returns.to_numpy(dtype=float), axis=0)
    value = np.concatenate(([1.0], growth @ w))
    return pd.Series(value[1:] / value[:-1] - 1.0, index=returns.index, name="portfolio")


@dataclass(frozen=True)
class RiskDecomposition:
    volatility: float
    marginal_contribution: np.ndarray  # d sigma_p / d w_i
    risk_contribution: np.ndarray  # w_i * marginal; sums to volatility
    percent_contribution: np.ndarray  # risk_contribution / volatility; sums to 1


def risk_decomposition(weights: np.ndarray, cov: np.ndarray) -> RiskDecomposition:
    """Euler decomposition of portfolio volatility into per-asset contributions."""
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    vol = portfolio_volatility(w, c)
    if vol < 1e-14:
        raise UndefinedMetricError("Risk contributions are undefined for zero volatility.")
    marginal = (c @ w) / vol
    contribution = w * marginal
    return RiskDecomposition(vol, marginal, contribution, contribution / vol)


def diversification_ratio(weights: np.ndarray, cov: np.ndarray) -> float:
    """Weighted average asset volatility divided by portfolio volatility (>= 1 long-only)."""
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    vol = portfolio_volatility(w, c)
    if vol < 1e-14:
        raise UndefinedMetricError("Diversification ratio is undefined for zero volatility.")
    return float(w @ np.sqrt(np.diag(c)) / vol)


def effective_number_of_assets(weights: np.ndarray) -> float:
    """Inverse Herfindahl index ``1 / sum(w_i^2)``: N for equal weights, 1 for one asset."""
    w = np.asarray(weights, dtype=float)
    hhi = float(np.sum(w**2))
    if hhi <= 0.0:
        raise UndefinedMetricError("Effective number of assets is undefined for zero weights.")
    return 1.0 / hhi
