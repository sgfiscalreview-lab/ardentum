"""Black-Litterman expected returns (Black & Litterman, 1992; He & Litterman, 1999).

Prior (equilibrium)
    ``pi = delta * Sigma * w_eq + r_f``: the returns under which a mean-variance
    investor with risk aversion ``delta`` would hold the prior weights ``w_eq``
    (market-capitalisation weights by default). ``Sigma`` is the annualised
    covariance and ``r_f`` the risk-free rate on the same (linear) scale, so the
    prior is in total-return terms like the other mean estimators.

Views
    ``P mu = Q + e``, ``e ~ N(0, Omega)``. Each row of ``P`` is a view portfolio
    (absolute: one asset with coefficient 1; relative: +1 / -1, or any weights).
    ``Omega`` is diagonal; by default ``omega_k = tau * p_k' Sigma p_k``
    (He & Litterman, 1999). A view *confidence* ``c`` in (0, 1] uses Idzorek's
    (2005) closed form ``omega_k = tau * (1 - c) / c * p_k' Sigma p_k``, so
    ``c = 1`` makes the view hold exactly and ``c -> 0`` ignores it.

Posterior
    ``mu_BL = pi + tau Sigma P' (tau P Sigma P' + Omega)^-1 (Q - P pi)``
    ``Sigma_BL = Sigma + tau Sigma - tau Sigma P' (tau P Sigma P' + Omega)^-1 P tau Sigma``
    (the predictive covariance, which adds estimation uncertainty in the mean).
    These are the formulas implemented in PyPortfolioOpt's ``BlackLittermanModel``;
    the test-suite checks agreement with it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ardentum.quant.errors import InvalidInputError

DEFAULT_RISK_AVERSION = 2.5
DEFAULT_TAU = 0.05


@dataclass(frozen=True)
class View:
    """``sum_i weights[i] * mu_i = expected_return`` (annual, decimal)."""

    weights: Mapping[str, float]
    expected_return: float
    confidence: float | None = None  # Idzorek confidence in (0, 1]; None = He-Litterman

    def describe(self) -> str:
        items = sorted(self.weights.items(), key=lambda kv: -kv[1])
        if len(items) == 1 and items[0][1] == 1.0:
            text = f"{items[0][0]} returns {self.expected_return:.2%} a year"
        elif len(items) == 2 and items[0][1] == 1.0 and items[1][1] == -1.0:
            text = f"{items[0][0]} outperforms {items[1][0]} by {self.expected_return:.2%} a year"
        else:
            combo = " ".join(f"{w:+g}×{t}" for t, w in items)
            text = f"{combo} returns {self.expected_return:.2%} a year"
        conf = (
            "default uncertainty"
            if self.confidence is None
            else f"{self.confidence:.0%} confidence"
        )
        return f"{text} ({conf})."


@dataclass(frozen=True)
class BlackLittermanSpec:
    prior_weights: Mapping[str, float]
    views: Sequence[View] = ()
    risk_aversion: float = DEFAULT_RISK_AVERSION
    tau: float = DEFAULT_TAU
    risk_free_rate: float = 0.0  # on the linear annualisation scale of the estimates
    prior_label: str = "market capitalisation"


@dataclass(frozen=True)
class BlackLittermanResult:
    prior_weights: np.ndarray
    prior_returns: np.ndarray
    posterior_returns: np.ndarray
    posterior_covariance: np.ndarray
    P: np.ndarray
    Q: np.ndarray
    omega: np.ndarray  # diagonal entries
    spec: BlackLittermanSpec


def normalise_prior(tickers: Sequence[str], weights: Mapping[str, float]) -> np.ndarray:
    missing = [t for t in tickers if t not in weights]
    if missing:
        raise InvalidInputError(
            f"Black-Litterman prior weights are missing for {', '.join(missing)}; "
            "provide a market capitalisation or weight for every selected asset."
        )
    w = np.array([float(weights[t]) for t in tickers])
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise InvalidInputError(
            "Black-Litterman prior weights must be non-negative and not all zero."
        )
    return np.asarray(w / w.sum(), dtype=float)


def implied_returns(
    covariance: np.ndarray,
    prior_weights: np.ndarray,
    risk_aversion: float,
    risk_free_rate: float = 0.0,
) -> np.ndarray:
    """Equilibrium returns ``delta * Sigma * w + r_f``."""
    if not 0 < risk_aversion <= 100:
        raise InvalidInputError("Risk aversion must be positive (typically 1 to 5).")
    return np.asarray(risk_aversion * covariance @ prior_weights + risk_free_rate, dtype=float)


def view_matrices(tickers: Sequence[str], views: Sequence[View]) -> tuple[np.ndarray, np.ndarray]:
    index = {t: i for i, t in enumerate(tickers)}
    p = np.zeros((len(views), len(tickers)))
    q = np.zeros(len(views))
    for k, v in enumerate(views):
        unknown = [t for t in v.weights if t not in index]
        if unknown:
            raise InvalidInputError(
                f"View {k + 1} refers to assets outside the selection: {', '.join(unknown)}."
            )
        for t, c in v.weights.items():
            p[k, index[t]] = float(c)
        if not np.isfinite(p[k]).all() or np.allclose(p[k], 0.0):
            raise InvalidInputError(f"View {k + 1} needs at least one non-zero asset weight.")
        if not np.isfinite(v.expected_return):
            raise InvalidInputError(f"View {k + 1}: expected return must be a finite number.")
        if v.confidence is not None and not 0 < v.confidence <= 1:
            raise InvalidInputError(f"View {k + 1}: confidence must be in (0%, 100%].")
        q[k] = v.expected_return
    if len(views) and np.linalg.matrix_rank(p) < len(views):
        raise InvalidInputError(
            "Views are linearly dependent (one view is a combination of others); remove duplicates."
        )
    return p, q


def view_uncertainty(
    p: np.ndarray, covariance: np.ndarray, tau: float, views: Sequence[View]
) -> np.ndarray:
    base = tau * np.einsum("ki,ij,kj->k", p, covariance, p)
    out = base.copy()
    for k, v in enumerate(views):
        if v.confidence is not None:
            out[k] = base[k] * (1.0 - v.confidence) / v.confidence
    return np.asarray(out, dtype=float)


def black_litterman(
    tickers: Sequence[str], covariance: np.ndarray, spec: BlackLittermanSpec
) -> BlackLittermanResult:
    if not 0 < spec.tau <= 1:
        raise InvalidInputError("tau must be in (0, 1]; values of 0.01-0.1 are typical.")
    sigma = np.asarray(covariance, dtype=float)
    w = normalise_prior(tickers, spec.prior_weights)
    pi = implied_returns(sigma, w, spec.risk_aversion, spec.risk_free_rate)
    p, q = view_matrices(tickers, spec.views)
    tau_sigma = spec.tau * sigma
    if len(spec.views) == 0:
        return BlackLittermanResult(w, pi, pi.copy(), sigma + tau_sigma, p, q, np.zeros(0), spec)
    omega = view_uncertainty(p, sigma, spec.tau, spec.views)
    a = p @ tau_sigma @ p.T + np.diag(omega)
    gain = np.linalg.solve(a, p @ tau_sigma).T  # tau Sigma P' A^-1
    mu = pi + gain @ (q - p @ pi)
    post_cov = sigma + tau_sigma - gain @ p @ tau_sigma
    post_cov = 0.5 * (post_cov + post_cov.T)
    return BlackLittermanResult(w, pi, mu, post_cov, p, q, omega, spec)
