"""Risk parity (equal risk contribution) against closed forms, an independent solver and
the known ordering of volatilities (Maillard, Roncalli and Teiletche 2010)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import minimize

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError
from ardentum.quant.explain import explain
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    SectorLimit,
    optimise,
    risk_parity_gap,
)
from ardentum.quant.portfolio import portfolio_volatility, risk_decomposition
from tests.quant.test_optimisation import META, _estimates

RP = Objective.RISK_PARITY
OPEN = PortfolioConstraints(max_weight=1.0)


def _rp(cov: np.ndarray, constraints: PortfolioConstraints = OPEN, **kw: object) -> np.ndarray:
    est = _estimates(np.full(len(cov), 0.05), cov)
    return optimise(est, OptimisationRequest(RP, constraints=constraints), **kw).weights  # type: ignore[arg-type]


def _cov(vol: np.ndarray, corr: np.ndarray) -> np.ndarray:
    return np.outer(vol, vol) * corr


def _random_cov(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(n, n + 3))
    cov = a @ a.T / (n + 3)
    vol = rng.uniform(0.05, 0.4, n)
    d = np.sqrt(np.diag(cov))
    return _cov(vol, cov / np.outer(d, d))


def test_two_assets_are_inverse_volatility_whatever_the_correlation() -> None:
    vol = np.array([0.08, 0.24])
    for rho in (-0.6, 0.0, 0.3, 0.9):
        w = _rp(_cov(vol, np.array([[1.0, rho], [rho, 1.0]])))
        expected = (1 / vol) / (1 / vol).sum()
        assert w == pytest.approx(expected, abs=1e-10)


def test_equal_correlation_gives_inverse_volatility() -> None:
    # With one common correlation the solution is w_i proportional to 1 / sigma_i.
    vol = np.array([0.05, 0.12, 0.2, 0.31, 0.4])
    for rho in (0.0, 0.25, 0.7):
        corr = np.full((5, 5), rho) + (1 - rho) * np.eye(5)
        w = _rp(_cov(vol, corr))
        assert w == pytest.approx((1 / vol) / (1 / vol).sum(), abs=1e-10)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_risk_contributions_are_equal_and_match_an_independent_solver(seed: int) -> None:
    cov = _random_cov(7, seed)
    w = _rp(cov)
    rc = risk_decomposition(w, cov).percent_contribution
    assert rc == pytest.approx(np.full(7, 1 / 7), abs=1e-10)
    assert risk_parity_gap(w, cov) < 1e-10

    # Independent check: SciPy's quasi-Newton method (no conic solver) on the same convex
    # problem, written out with its gradient.
    def f(y: np.ndarray) -> float:
        return float(0.5 * y @ cov @ y - np.log(y).sum() / 7)

    def grad(y: np.ndarray) -> np.ndarray:
        return np.asarray(cov @ y - 1 / (7 * y))

    ref = minimize(
        f,
        np.ones(7),
        jac=grad,
        method="L-BFGS-B",
        bounds=[(1e-9, None)] * 7,
        options={"ftol": 1e-15, "gtol": 1e-12, "maxiter": 10_000},
    )
    assert ref.success
    assert w == pytest.approx(ref.x / ref.x.sum(), abs=1e-6)


def test_volatility_lies_between_minimum_variance_and_equal_weights() -> None:
    for seed in range(5):
        cov = _random_cov(6, seed)
        est = _estimates(np.full(6, 0.05), cov)
        w_rp = _rp(cov)
        w_mv = optimise(
            est, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=OPEN)
        ).weights
        v_mv, v_rp = portfolio_volatility(w_mv, cov), portfolio_volatility(w_rp, cov)
        assert v_mv - 1e-12 <= v_rp <= portfolio_volatility(np.full(6, 1 / 6), cov) + 1e-12


def test_ignores_expected_returns_and_excluded_assets() -> None:
    cov = _random_cov(5, 7)
    a = optimise(_estimates(np.full(5, 0.05), cov), OptimisationRequest(RP, constraints=OPEN))
    b = optimise(
        _estimates(np.array([0.3, -0.1, 0.0, 0.2, 0.05]), cov),
        OptimisationRequest(RP, constraints=OPEN),
    )
    assert a.weights == pytest.approx(b.weights, abs=1e-12)
    excl = PortfolioConstraints(max_weight=1.0, excluded_assets=frozenset({"A1"}))
    w = _rp(cov, excl)
    assert w[1] == 0.0
    keep = [0, 2, 3, 4]
    assert w[keep] == pytest.approx(_rp(cov[np.ix_(keep, keep)]), abs=1e-10)


def test_broken_constraints_are_named_not_approximated() -> None:
    vol = np.array([0.05, 0.2, 0.25, 0.3, 0.35])
    cov = _cov(vol, np.full((5, 5), 0.2) + 0.8 * np.eye(5))
    # The low-volatility asset needs about 57%: a 30% cap cannot be met exactly.
    with pytest.raises(
        InfeasibleProblemError, match=r"A0 gets 56\.\d%, above its maximum of 30\.0%"
    ):
        _rp(cov, PortfolioConstraints(max_weight=0.3))
    with pytest.raises(InfeasibleProblemError, match="Tech"):
        _rp(
            cov,
            PortfolioConstraints(sector_limits=(SectorLimit("Tech", max_weight=0.1),)),
            metadata=META,
        )
    with pytest.raises(InvalidInputError, match="short positions"):
        _rp(cov, PortfolioConstraints(min_weight=-0.1))
    # Constraints the portfolio already meets are fine and reported, not binding.
    est = _estimates(np.full(5, 0.05), cov)
    res = optimise(
        est,
        OptimisationRequest(
            RP,
            constraints=PortfolioConstraints(sector_limits=(SectorLimit("Tech", max_weight=0.6),)),
        ),
        META,
    )
    assert [d.binding for d in res.diagnostics if d.kind == "sector_max"] == [False]


def test_singular_covariance_is_refused_with_a_reason() -> None:
    vol = np.array([0.1, 0.1, 0.2])
    corr = np.array([[1.0, 1.0, 0.2], [1.0, 1.0, 0.2], [0.2, 0.2, 1.0]])  # A0 and A1 identical
    with pytest.raises(InvalidInputError, match="singular"):
        _rp(_cov(vol, corr))


def test_explanation_states_the_equal_shares() -> None:
    cov = _random_cov(4, 3)
    est = _estimates(np.full(4, 0.05), cov)
    req = OptimisationRequest(RP, constraints=OPEN)
    res = optimise(est, req, AssetMetadata())
    ex = explain(res, est, req)
    assert ex.headline.startswith("Every holding contributes the same share of risk (25.0% each)")
    assert all("25.0% of portfolio risk" in a.reason for a in ex.assets)
    assert not any("Return-seeking" in w for w in ex.warnings)
