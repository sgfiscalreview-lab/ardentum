"""Black-Litterman: agreement with PyPortfolioOpt and closed-form properties."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pypfopt import black_litterman as ppo

from ardentum.quant.black_litterman import BlackLittermanSpec, View, black_litterman
from ardentum.quant.errors import InvalidInputError
from ardentum.quant.estimation import MeanEstimator, estimate
from ardentum.quant.optimisation import Objective, OptimisationRequest, optimise

TICKERS = ["A", "B", "C", "D"]
CAPS = {"A": 400.0, "B": 300.0, "C": 200.0, "D": 100.0}


def _cov() -> np.ndarray:
    vol = np.array([0.15, 0.20, 0.25, 0.30])
    corr = np.array(
        [[1, 0.5, 0.3, 0.2], [0.5, 1, 0.4, 0.3], [0.3, 0.4, 1, 0.5], [0.2, 0.3, 0.5, 1.0]]
    )
    return np.outer(vol, vol) * corr


VIEWS = [
    View({"A": 1.0}, 0.10),
    View({"C": 1.0, "D": -1.0}, 0.02),
]


def test_prior_matches_pypfopt() -> None:
    cov = _cov()
    spec = BlackLittermanSpec(CAPS, (), risk_aversion=3.0, risk_free_rate=0.02)
    res = black_litterman(TICKERS, cov, spec)
    ref = ppo.market_implied_prior_returns(
        pd.Series(CAPS), 3.0, pd.DataFrame(cov, TICKERS, TICKERS), risk_free_rate=0.02
    )
    np.testing.assert_allclose(res.prior_returns, ref.to_numpy(), rtol=1e-12)
    # With no views the posterior is the prior.
    np.testing.assert_allclose(res.posterior_returns, res.prior_returns)


def test_posterior_matches_pypfopt_default_omega() -> None:
    cov = _cov()
    res = black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, VIEWS, tau=0.05))
    cov_df = pd.DataFrame(cov, TICKERS, TICKERS)
    model = ppo.BlackLittermanModel(
        cov_df, pi=pd.Series(res.prior_returns, TICKERS), P=res.P, Q=res.Q, tau=0.05
    )
    np.testing.assert_allclose(res.posterior_returns, model.bl_returns().to_numpy(), rtol=1e-10)
    np.testing.assert_allclose(res.posterior_covariance, model.bl_cov().to_numpy(), rtol=1e-10)
    np.testing.assert_allclose(res.omega, np.diag(model.omega), rtol=1e-12)


def test_posterior_matches_pypfopt_idzorek() -> None:
    cov = _cov()
    views = [View({"A": 1.0}, 0.10, 0.6), View({"C": 1.0, "D": -1.0}, 0.02, 0.25)]
    res = black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, views, tau=0.05))
    model = ppo.BlackLittermanModel(
        pd.DataFrame(cov, TICKERS, TICKERS),
        pi=pd.Series(res.prior_returns, TICKERS),
        P=res.P,
        Q=res.Q,
        omega="idzorek",
        view_confidences=[0.6, 0.25],
        tau=0.05,
    )
    np.testing.assert_allclose(res.posterior_returns, model.bl_returns().to_numpy(), rtol=1e-10)


def test_full_confidence_view_holds_exactly_and_weak_view_is_ignored() -> None:
    cov = _cov()
    sure = black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, [View({"A": 1.0}, 0.10, 1.0)]))
    assert sure.posterior_returns[0] == pytest.approx(0.10, abs=1e-12)
    weak = black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, [View({"A": 1.0}, 0.10, 1e-9)]))
    np.testing.assert_allclose(weak.posterior_returns, weak.prior_returns, atol=1e-8)


def test_reverse_optimisation_recovers_prior_weights() -> None:
    # Unconstrained mean-variance weights under the prior are the prior weights:
    # w* = (delta Sigma)^-1 (pi - rf) = w_eq.
    cov = _cov()
    res = black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, (), risk_aversion=2.5))
    w = np.linalg.solve(2.5 * cov, res.prior_returns)
    np.testing.assert_allclose(w, [0.4, 0.3, 0.2, 0.1], rtol=1e-12)


def test_estimate_and_optimise_with_black_litterman(returns_df: pd.DataFrame) -> None:
    tickers = list(returns_df.columns)
    caps = {t: float(i + 1) for i, t in enumerate(tickers)}
    spec = BlackLittermanSpec(caps, [View({tickers[0]: 1.0}, 0.12, 0.8)])
    est = estimate(
        returns_df, 252, mean_estimator=MeanEstimator.BLACK_LITTERMAN, black_litterman_spec=spec
    )
    assert est.black_litterman is not None
    np.testing.assert_allclose(est.expected_returns, est.black_litterman.posterior_returns)
    res = optimise(est, OptimisationRequest(objective=Objective.MAX_SHARPE))
    assert res.weights.sum() == pytest.approx(1.0)
    with pytest.raises(InvalidInputError, match="prior weights"):
        estimate(returns_df, 252, mean_estimator=MeanEstimator.BLACK_LITTERMAN)


def test_validation_messages() -> None:
    cov = _cov()
    with pytest.raises(InvalidInputError, match="missing for D"):
        black_litterman(TICKERS, cov, BlackLittermanSpec({"A": 1, "B": 1, "C": 1}))
    with pytest.raises(InvalidInputError, match="outside the selection"):
        black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, [View({"Z": 1.0}, 0.1)]))
    with pytest.raises(InvalidInputError, match="linearly dependent"):
        black_litterman(
            TICKERS, cov, BlackLittermanSpec(CAPS, [View({"A": 1.0}, 0.1), View({"A": 2.0}, 0.2)])
        )
    with pytest.raises(InvalidInputError, match="confidence"):
        black_litterman(TICKERS, cov, BlackLittermanSpec(CAPS, [View({"A": 1.0}, 0.1, 0.0)]))
    assert "outperforms" in View({"C": 1.0, "D": -1.0}, 0.02).describe()
