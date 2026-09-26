"""Minimum-CVaR optimisation: closed forms, an independent LP (SciPy) and brute force."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import linprog

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError
from ardentum.quant.estimation import estimate
from ardentum.quant.metrics import historical_var_cvar
from ardentum.quant.optimisation import (
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    optimise,
)


def _scenarios(t: int = 400, n: int = 3, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = rng.standard_t(4, size=(t, n)) * np.array([0.006, 0.012, 0.02])[:n]
    base[:, 1] += 0.4 * base[:, 0]
    idx = pd.bdate_range("2020-01-01", periods=t)
    return pd.DataFrame(base + np.array([0.0002, 0.0004, 0.0007])[:n], idx, list("ABC")[:n])


def test_historical_cvar_closed_forms() -> None:
    losses = np.arange(1.0, 101.0)  # 1..100
    var, cvar = historical_var_cvar(losses, 0.95)
    assert var == 95.0
    assert cvar == pytest.approx(np.mean([96, 97, 98, 99, 100]))
    # Non-integer tail: equals the Rockafellar-Uryasev minimum over a (data points
    # suffice because the function is piecewise linear and convex).
    rng = np.random.default_rng(0)
    x = rng.normal(size=137)
    _, c = historical_var_cvar(x, 0.9)
    ru = min(a + np.maximum(x - a, 0).sum() / (0.1 * x.size) for a in x)
    assert c == pytest.approx(ru, rel=1e-12)
    with pytest.raises(InvalidInputError):
        historical_var_cvar(x, 1.0)


def _scipy_min_cvar(r: np.ndarray, beta: float, ub: float) -> float:
    t, n = r.shape
    # variables: w (n), alpha (1), u (t)
    c = np.concatenate([np.zeros(n), [1.0], np.full(t, 1.0 / ((1 - beta) * t))])
    a_ub = np.hstack([-r, -np.ones((t, 1)), -np.eye(t)])  # -r w - a - u <= 0
    a_eq = np.concatenate([np.ones(n), [0.0], np.zeros(t)])[None, :]
    bounds = [(0.0, ub)] * n + [(None, None)] + [(0.0, None)] * t
    res = linprog(
        c, A_ub=a_ub, b_ub=np.zeros(t), A_eq=a_eq, b_eq=[1.0], bounds=bounds, method="highs"
    )
    assert res.status == 0
    return float(res.fun)


@pytest.mark.parametrize(("beta", "ub"), [(0.95, 1.0), (0.9, 0.5), (0.99, 0.7)])
def test_min_cvar_matches_scipy_linprog(beta: float, ub: float) -> None:
    df = _scenarios()
    est = estimate(df, 252)
    req = OptimisationRequest(
        Objective.MIN_CVAR, cvar_confidence=beta, constraints=PortfolioConstraints(max_weight=ub)
    )
    res = optimise(est, req)
    ref = _scipy_min_cvar(df.to_numpy(), beta, ub)
    assert res.cvar == pytest.approx(ref, rel=1e-6, abs=1e-9)
    assert res.cvar_confidence == beta
    assert res.weights.sum() == pytest.approx(1.0)
    assert res.weights.max() <= ub + 1e-8


def test_min_cvar_beats_brute_force_grid() -> None:
    df = _scenarios(t=250)
    r = df.to_numpy()
    res = optimise(estimate(df, 252), OptimisationRequest(Objective.MIN_CVAR))
    best = np.inf
    step = 0.02
    for a, b in itertools.product(np.arange(0, 1 + 1e-9, step), repeat=2):
        if a + b <= 1 + 1e-9:
            w = np.array([a, b, 1 - a - b])
            best = min(best, historical_var_cvar(-(r @ w), 0.95)[1])
    assert res.cvar is not None
    assert res.cvar <= best + 1e-9
    assert best - res.cvar < 5e-4  # the grid is close to the optimum


def test_min_cvar_with_target_return() -> None:
    df = _scenarios()
    est = estimate(df, 252)
    free = optimise(est, OptimisationRequest(Objective.MIN_CVAR))
    target = free.expected_return + 0.02
    res = optimise(est, OptimisationRequest(Objective.MIN_CVAR, target_return=target))
    assert res.expected_return >= target - 1e-7
    assert res.cvar is not None
    assert free.cvar is not None
    assert res.cvar >= free.cvar - 1e-10
    assert any(d.kind == "target_return" and d.binding for d in res.diagnostics)
    with pytest.raises(InfeasibleProblemError, match="exceeds the maximum"):
        optimise(est, OptimisationRequest(Objective.MIN_CVAR, target_return=5.0))


def test_min_cvar_input_checks() -> None:
    df = _scenarios(t=40)
    est = estimate(df, 252)
    with pytest.raises(InvalidInputError, match="observations"):
        optimise(est, OptimisationRequest(Objective.MIN_CVAR, cvar_confidence=0.99))
    with pytest.raises(InvalidInputError, match="between 50%"):
        optimise(est, OptimisationRequest(Objective.MIN_CVAR, cvar_confidence=0.3))


def test_cvar_reported_for_other_objectives() -> None:
    df = _scenarios()
    res = optimise(estimate(df, 252), OptimisationRequest(Objective.MIN_VOLATILITY))
    assert res.cvar is not None
    assert res.cvar == pytest.approx(historical_var_cvar(-(df.to_numpy() @ res.weights), 0.95)[1])
    cvar_opt = optimise(estimate(df, 252), OptimisationRequest(Objective.MIN_CVAR))
    assert cvar_opt.cvar is not None
    assert cvar_opt.cvar <= res.cvar + 1e-10
