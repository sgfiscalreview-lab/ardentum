"""Mean-CVaR efficient frontier: independent LP (SciPy HiGHS), brute force and shape."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import linprog

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.estimation import estimate
from ardentum.quant.frontier import mean_cvar_frontier
from ardentum.quant.metrics import historical_var_cvar
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    optimise,
)


def _scenarios(t: int = 400, n: int = 3, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = rng.standard_t(4, size=(t, n)) * np.array([0.006, 0.012, 0.02, 0.015])[:n]
    base[:, 1] += 0.4 * base[:, 0]
    idx = pd.bdate_range("2020-01-01", periods=t)
    drift = np.array([0.0002, 0.0004, 0.0008, 0.0005])[:n]
    return pd.DataFrame(base + drift, idx, list("ABCD")[:n])


def _scipy_cvar_at_target(
    r: np.ndarray, mu: np.ndarray, target: float, beta: float, ub: float = 1.0
) -> float:
    """Independent Rockafellar-Uryasev LP: variables w (n), alpha, u (T)."""
    t, n = r.shape
    c = np.concatenate([np.zeros(n), [1.0], np.full(t, 1.0 / ((1 - beta) * t))])
    a_ub = np.vstack(
        [
            np.hstack([-r, -np.ones((t, 1)), -np.eye(t)]),  # -R w - a - u <= 0
            np.concatenate([-mu, [0.0], np.zeros(t)])[None, :],  # -mu w <= -target
        ]
    )
    b_ub = np.concatenate([np.zeros(t), [-target]])
    a_eq = np.concatenate([np.ones(n), [0.0], np.zeros(t)])[None, :]
    bounds = [(0.0, ub)] * n + [(None, None)] + [(0.0, None)] * t
    res = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=[1.0], bounds=bounds, method="highs")
    assert res.status == 0
    return float(res.fun)


@pytest.mark.parametrize(("beta", "ub"), [(0.95, 1.0), (0.9, 0.6)])
def test_each_point_matches_independent_lp(beta: float, ub: float) -> None:
    df = _scenarios()
    est = estimate(df, 252)
    fr = mean_cvar_frontier(est, PortfolioConstraints(max_weight=ub), n_points=8, confidence=beta)
    assert len(fr.points) == 8
    r = df.to_numpy()
    for p in fr.points[:-1]:  # the last target is backed off by a negligible amount
        ref = _scipy_cvar_at_target(r, est.expected_returns, p.expected_return - 1e-9, beta, ub)
        assert p.cvar == pytest.approx(ref, rel=1e-5, abs=1e-8)


def test_point_cvar_is_the_historical_cvar_of_its_weights() -> None:
    df = _scenarios()
    fr = mean_cvar_frontier(estimate(df, 252), PortfolioConstraints(), n_points=6)
    r = df.to_numpy()
    for p in fr.points:
        var, cvar = historical_var_cvar(-(r @ p.weights), 0.95)
        assert p.cvar == pytest.approx(cvar, rel=1e-12)
        assert p.var == pytest.approx(var, rel=1e-12)
        assert p.cvar >= p.var - 1e-12
        assert p.weights.sum() == pytest.approx(1.0)
        assert (p.weights >= -1e-9).all()


def test_frontier_shape_and_endpoints() -> None:
    df = _scenarios()
    est = estimate(df, 252)
    fr = mean_cvar_frontier(est, PortfolioConstraints(), n_points=10)
    rets = np.array([p.expected_return for p in fr.points])
    cvars = np.array([p.cvar for p in fr.points])
    # Efficient branch: return rises and CVaR never falls (the LP value is convex in m).
    assert (np.diff(rets) > 0).all()
    assert (np.diff(cvars) >= -1e-9).all()
    # First point is the minimum-CVaR portfolio; the last reaches the maximum return.
    free = optimise(est, OptimisationRequest(Objective.MIN_CVAR))
    assert fr.points[0].cvar == pytest.approx(free.cvar, rel=1e-6)
    assert fr.min_cvar.cvar == pytest.approx(free.cvar, rel=1e-9)
    assert rets[-1] == pytest.approx(est.expected_returns.max(), rel=1e-5)
    assert fr.observations == len(df)
    assert fr.periods_per_year == 252


def test_no_grid_portfolio_beats_the_frontier() -> None:
    df = _scenarios(t=250)
    est = estimate(df, 252)
    r = df.to_numpy()
    fr = mean_cvar_frontier(est, PortfolioConstraints(), n_points=5)
    step = 0.02
    grid = [
        np.array([a, b, 1 - a - b])
        for a, b in itertools.product(np.arange(0, 1 + 1e-9, step), repeat=2)
        if a + b <= 1 + 1e-9
    ]
    grid_ret = np.array([w @ est.expected_returns for w in grid])
    grid_cvar = np.array([historical_var_cvar(-(r @ w), 0.95)[1] for w in grid])
    for p in fr.points[:-1]:
        feasible = grid_ret >= p.expected_return - 1e-12
        assert p.cvar <= grid_cvar[feasible].min() + 1e-9


def test_input_checks() -> None:
    df = _scenarios(t=40)
    est = estimate(df, 252)
    with pytest.raises(InvalidInputError, match="observations"):
        mean_cvar_frontier(est, PortfolioConstraints(), confidence=0.99)
    with pytest.raises(InvalidInputError, match="frontier points"):
        mean_cvar_frontier(est, PortfolioConstraints(), n_points=1)


def test_esg_tilt_warning_and_constraints_apply() -> None:
    df = _scenarios()
    est = estimate(df, 252)
    meta = AssetMetadata(esg_scores={"A": 40.0, "B": 60.0, "C": 80.0})
    fr = mean_cvar_frontier(
        est, PortfolioConstraints(max_weight=0.5, esg_tilt=0.1, min_esg_score=60.0), 0.0, meta, 4
    )
    assert any("tilt" in w for w in fr.warnings)
    for p in fr.points:
        assert p.weights.max() <= 0.5 + 1e-8
        assert p.esg_score is not None
        assert p.esg_score >= 60.0 - 1e-6
