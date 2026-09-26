"""Validation of the optimisation engine against closed-form solutions, KKT
conditions and independent numerical methods."""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from scipy.optimize import minimize

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError
from ardentum.quant.estimation import (
    CovarianceEstimator,
    MarketEstimates,
    MeanEstimator,
    estimate,
    risk_free_arithmetic,
)
from ardentum.quant.frontier import efficient_frontier, esg_sharpe_frontier
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    SectorLimit,
    max_achievable_return,
    optimise,
)
from ardentum.quant.portfolio import portfolio_volatility
from tests.conftest import make_returns

WIDE = PortfolioConstraints(min_weight=-5.0, max_weight=5.0)


def _estimates(mu: np.ndarray, cov: np.ndarray) -> MarketEstimates:
    return MarketEstimates(
        tickers=tuple(f"A{i}" for i in range(len(mu))),
        expected_returns=np.asarray(mu, dtype=float),
        covariance=np.asarray(cov, dtype=float),
        periods_per_year=252,
        observations=1000,
        start=None,
        end=None,
        mean_estimator=MeanEstimator.HISTORICAL,
        covariance_estimator=CovarianceEstimator.SAMPLE,
    )


@pytest.fixture
def five_assets() -> MarketEstimates:
    mu = np.array([0.05, 0.07, 0.09, 0.11, 0.13])
    vol = np.array([0.10, 0.14, 0.18, 0.22, 0.30])
    corr = np.array(
        [
            [1.0, 0.3, 0.2, 0.1, 0.0],
            [0.3, 1.0, 0.4, 0.2, 0.1],
            [0.2, 0.4, 1.0, 0.5, 0.3],
            [0.1, 0.2, 0.5, 1.0, 0.6],
            [0.0, 0.1, 0.3, 0.6, 1.0],
        ]
    )
    return _estimates(mu, np.outer(vol, vol) * corr)


META = AssetMetadata(
    sectors={"A0": "Utilities", "A1": "Energy", "A2": "Tech", "A3": "Tech", "A4": "Energy"},
    esg_scores={"A0": 80.0, "A1": 30.0, "A2": 60.0, "A3": 70.0, "A4": 20.0},
)


def _abc(est: MarketEstimates) -> tuple[float, float, float, np.ndarray]:
    inv = np.linalg.inv(est.covariance)
    one = np.ones(est.n_assets)
    mu = est.expected_returns
    return float(one @ inv @ one), float(one @ inv @ mu), float(mu @ inv @ mu), inv


# ----------------------------------------------------------------- closed form


def test_global_minimum_variance_closed_form(five_assets: MarketEstimates) -> None:
    a, _, _, inv = _abc(five_assets)
    expected = inv @ np.ones(5) / a
    res = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=WIDE))
    np.testing.assert_allclose(res.weights, expected, atol=1e-6)
    assert res.volatility == pytest.approx(np.sqrt(1 / a), rel=1e-6)


def test_tangency_portfolio_closed_form(five_assets: MarketEstimates) -> None:
    rf = 0.02
    rf_a = risk_free_arithmetic(rf, 252)
    inv = np.linalg.inv(five_assets.covariance)
    raw = inv @ (five_assets.expected_returns - rf_a)
    expected = raw / raw.sum()
    res = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, rf, constraints=WIDE))
    np.testing.assert_allclose(res.weights, expected, atol=1e-5)
    # Tangency Sharpe = sqrt((mu - rf)' S^-1 (mu - rf))
    ex = five_assets.expected_returns - rf_a
    assert res.sharpe_ratio == pytest.approx(np.sqrt(ex @ inv @ ex), rel=1e-6)


def test_frontier_matches_merton_hyperbola(five_assets: MarketEstimates) -> None:
    a, b, c, _ = _abc(five_assets)
    d = a * c - b * b
    for m in [0.08, 0.10, 0.12, 0.15]:
        res = optimise(
            five_assets,
            OptimisationRequest(Objective.TARGET_RETURN, target_return=m, constraints=WIDE),
        )
        assert res.expected_return == pytest.approx(m, abs=1e-7)
        assert res.volatility**2 == pytest.approx((a * m * m - 2 * b * m + c) / d, rel=1e-6)


def test_max_utility_closed_form(five_assets: MarketEstimates) -> None:
    gamma = 4.0
    a, b, _, inv = _abc(five_assets)
    eta = (b - gamma) / a
    expected = inv @ (five_assets.expected_returns - eta) / gamma
    res = optimise(
        five_assets,
        OptimisationRequest(Objective.MAX_UTILITY, risk_aversion=gamma, constraints=WIDE),
    )
    np.testing.assert_allclose(res.weights, expected, atol=1e-6)


# ----------------------------------------------------------------- long-only


def _slsqp(objective, n: int, bounds: list[tuple[float, float]], extra=()) -> np.ndarray:  # type: ignore[no-untyped-def]
    best = None
    rng = np.random.default_rng(0)
    for x0 in [np.full(n, 1 / n), *rng.dirichlet(np.ones(n), 15)]:
        r = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}, *extra],
            options={"ftol": 1e-14, "maxiter": 1000},
        )
        if r.success and (best is None or r.fun < best.fun):
            best = r
    assert best is not None
    return np.asarray(best.x)


def test_long_only_min_vol_matches_slsqp(five_assets: MarketEstimates) -> None:
    cov = five_assets.covariance
    res = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY))
    ref = _slsqp(lambda w: w @ cov @ w, 5, [(0, 1)] * 5)
    assert res.volatility == pytest.approx(portfolio_volatility(ref, cov), rel=1e-6)
    np.testing.assert_allclose(res.weights, ref, atol=1e-4)
    assert (res.weights >= 0).all()


def test_long_only_max_sharpe_matches_slsqp_and_pypfopt(five_assets: MarketEstimates) -> None:
    from pypfopt import EfficientFrontier

    rf = 0.03
    rf_a = risk_free_arithmetic(rf, 252)
    mu, cov = five_assets.expected_returns, five_assets.covariance
    res = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, rf))
    ref = _slsqp(lambda w: -(w @ mu - rf_a) / np.sqrt(w @ cov @ w), 5, [(0, 1)] * 5)
    ref_sharpe = (ref @ mu - rf_a) / np.sqrt(ref @ cov @ ref)
    assert res.sharpe_ratio is not None
    assert res.sharpe_ratio >= ref_sharpe - 1e-7
    np.testing.assert_allclose(res.weights, ref, atol=1e-3)

    ef = EfficientFrontier(mu, cov, weight_bounds=(0, 1))
    ef.max_sharpe(risk_free_rate=rf_a)
    w_pf = np.array(list(ef.clean_weights(rounding=None).values()))
    np.testing.assert_allclose(res.weights, w_pf, atol=1e-4)


def test_max_sharpe_brute_force_three_assets() -> None:
    mu = np.array([0.06, 0.10, 0.08])
    vol = np.array([0.12, 0.25, 0.18])
    corr = np.array([[1.0, 0.2, 0.5], [0.2, 1.0, 0.3], [0.5, 0.3, 1.0]])
    est = _estimates(mu, np.outer(vol, vol) * corr)
    res = optimise(est, OptimisationRequest(Objective.MAX_SHARPE, 0.01))
    rf_a = risk_free_arithmetic(0.01, 252)
    grid = np.linspace(0, 1, 201)
    best = -np.inf
    for w0, w1 in itertools.product(grid, grid):
        if w0 + w1 > 1:
            continue
        w = np.array([w0, w1, 1 - w0 - w1])
        best = max(best, (w @ mu - rf_a) / np.sqrt(w @ est.covariance @ w))
    assert res.sharpe_ratio is not None
    assert res.sharpe_ratio >= best - 1e-9
    assert res.sharpe_ratio - best < 1e-3  # grid resolution


def test_min_vol_kkt_conditions(five_assets: MarketEstimates) -> None:
    res = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY))
    g = five_assets.covariance @ res.weights  # proportional to the gradient
    held = res.weights > 1e-6
    lam = g[held].mean()
    np.testing.assert_allclose(g[held], lam, rtol=1e-4)
    assert (g[~held] >= lam - 1e-8).all()


def test_max_sharpe_kkt_conditions() -> None:
    est = estimate(make_returns(n_obs=1500, n_assets=8, seed=21), 252)
    rf = 0.02
    rf_a = risk_free_arithmetic(rf, 252)
    res = optimise(est, OptimisationRequest(Objective.MAX_SHARPE, rf))
    w = res.weights
    ex = est.expected_returns - rf_a
    g = est.covariance @ w
    ratio = (w @ ex) / (w @ g)
    held = w > 1e-6
    # Held assets: excess return proportional to covariance with the portfolio.
    np.testing.assert_allclose(ex[held], ratio * g[held], rtol=1e-3, atol=1e-6)
    # Zero-weight assets: excess return below what their covariance would require.
    assert (ex[~held] <= ratio * g[~held] + 1e-6).all()


# ----------------------------------------------------------------- constraints


def test_max_weight_constraint_binding(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(max_weight=0.25)
    res = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons))
    assert res.weights.max() <= 0.25 + 1e-9
    assert any(d.kind == "asset_upper" and d.binding for d in res.diagnostics)
    assert res.weights.sum() == pytest.approx(1.0, abs=1e-12)


def test_infeasible_max_weight(five_assets: MarketEstimates) -> None:
    with pytest.raises(InfeasibleProblemError, match="cannot be fully invested"):
        optimise(
            five_assets,
            OptimisationRequest(
                Objective.MIN_VOLATILITY, constraints=PortfolioConstraints(max_weight=0.1)
            ),
        )


def test_invalid_bounds(five_assets: MarketEstimates) -> None:
    with pytest.raises(InvalidInputError):
        optimise(
            five_assets,
            OptimisationRequest(
                Objective.MIN_VOLATILITY,
                constraints=PortfolioConstraints(min_weight=0.5, max_weight=0.2),
            ),
        )


def test_asset_bounds_and_exclusions(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(
        asset_bounds={"A4": (0.10, 0.20)}, excluded_assets=frozenset({"A0"})
    )
    res = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons))
    assert res.weights[0] == 0.0
    assert 0.10 - 1e-9 <= res.weights[4] <= 0.20 + 1e-9
    assert any(d.kind == "excluded" for d in res.diagnostics)


def test_sector_limits(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(
        sector_limits=(SectorLimit("Tech", max_weight=0.2), SectorLimit("Energy", min_weight=0.3))
    )
    res = optimise(
        five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons), META
    )
    w = res.weight_map()
    assert w["A2"] + w["A3"] <= 0.2 + 1e-8
    assert w["A1"] + w["A4"] >= 0.3 - 1e-8
    kinds = {d.kind: d for d in res.diagnostics}
    assert "sector_max" in kinds
    assert "sector_min" in kinds


def test_sector_constraint_requires_metadata(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(sector_limits=(SectorLimit("Tech", max_weight=0.2),))
    with pytest.raises(InvalidInputError, match="sector"):
        optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons))


def test_excluded_sector(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(excluded_sectors=frozenset({"Energy"}))
    res = optimise(
        five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons), META
    )
    w = res.weight_map()
    assert w["A1"] == 0.0
    assert w["A4"] == 0.0


def test_all_excluded_is_infeasible(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(excluded_assets=frozenset({f"A{i}" for i in range(5)}))
    with pytest.raises(InfeasibleProblemError):
        optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons))


def test_gross_exposure_with_shorts(five_assets: MarketEstimates) -> None:
    # A 14% target exceeds the best asset (13%), so it needs shorting. With gross
    # exposure <= 130% the best attainable is 1.15 * 13% - 0.15 * 5% = 14.2%.
    cons = PortfolioConstraints(min_weight=-1.0, max_weight=2.0, max_gross_exposure=1.3)
    best, _ = max_achievable_return(five_assets, cons)
    assert best == pytest.approx(1.15 * 0.13 - 0.15 * 0.05, abs=1e-7)
    res = optimise(
        five_assets,
        OptimisationRequest(Objective.TARGET_RETURN, target_return=0.14, constraints=cons),
    )
    assert np.abs(res.weights).sum() <= 1.3 + 1e-7
    assert res.weights.min() < 0
    assert res.expected_return >= 0.14 - 1e-8


def test_tracking_error_limit(five_assets: MarketEstimates) -> None:
    bench = {f"A{i}": 0.2 for i in range(5)}
    unconstrained = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0))
    ew = np.full(5, 0.2)
    te_free = portfolio_volatility(unconstrained.weights - ew, five_assets.covariance)
    limit = te_free / 3
    cons = PortfolioConstraints(benchmark_weights=bench, max_tracking_error=limit)
    res = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons))
    te = portfolio_volatility(res.weights - ew, five_assets.covariance)
    assert te <= limit + 1e-6
    assert te == pytest.approx(limit, rel=1e-3)  # binding
    assert res.sharpe_ratio is not None
    assert unconstrained.sharpe_ratio is not None
    assert res.sharpe_ratio <= unconstrained.sharpe_ratio + 1e-9


# ----------------------------------------------------------------- objectives


def test_target_return_infeasible_above_max(five_assets: MarketEstimates) -> None:
    best, _ = max_achievable_return(five_assets, PortfolioConstraints(max_weight=0.5))
    assert best == pytest.approx(0.5 * 0.13 + 0.5 * 0.11)
    with pytest.raises(InfeasibleProblemError, match="exceeds the maximum achievable"):
        optimise(
            five_assets,
            OptimisationRequest(
                Objective.TARGET_RETURN,
                target_return=0.125,
                constraints=PortfolioConstraints(max_weight=0.5),
            ),
        )


def test_target_return_below_min_vol_is_not_binding(five_assets: MarketEstimates) -> None:
    res = optimise(five_assets, OptimisationRequest(Objective.TARGET_RETURN, target_return=0.0))
    mv = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY))
    np.testing.assert_allclose(res.weights, mv.weights, atol=1e-6)
    assert res.warnings


def test_target_volatility(five_assets: MarketEstimates) -> None:
    res = optimise(
        five_assets, OptimisationRequest(Objective.TARGET_VOLATILITY, target_volatility=0.15)
    )
    assert res.volatility == pytest.approx(0.15, abs=1e-6)
    # It must lie on the frontier: min vol for its return equals 15%.
    tr = optimise(
        five_assets,
        OptimisationRequest(Objective.TARGET_RETURN, target_return=res.expected_return - 1e-9),
    )
    assert tr.volatility == pytest.approx(0.15, abs=1e-5)
    with pytest.raises(InfeasibleProblemError, match="below the minimum achievable"):
        optimise(
            five_assets, OptimisationRequest(Objective.TARGET_VOLATILITY, target_volatility=0.01)
        )


def test_max_sharpe_undefined_when_rf_too_high(five_assets: MarketEstimates) -> None:
    with pytest.raises(InfeasibleProblemError, match="risk-free rate"):
        optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, risk_free_rate=0.20))


def test_missing_objective_parameters(five_assets: MarketEstimates) -> None:
    with pytest.raises(InvalidInputError):
        optimise(five_assets, OptimisationRequest(Objective.TARGET_RETURN))
    with pytest.raises(InvalidInputError):
        optimise(five_assets, OptimisationRequest(Objective.MAX_UTILITY))


def test_single_asset() -> None:
    est = _estimates(np.array([0.07]), np.array([[0.04]]))
    res = optimise(est, OptimisationRequest(Objective.MIN_VOLATILITY))
    np.testing.assert_allclose(res.weights, [1.0])
    assert res.volatility == pytest.approx(0.2)


def test_singular_covariance_duplicate_assets() -> None:
    vol = np.array([0.2, 0.2, 0.1])
    corr = np.array([[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    est = _estimates(np.array([0.08, 0.08, 0.04]), np.outer(vol, vol) * corr)
    res = optimise(est, OptimisationRequest(Objective.MIN_VOLATILITY))
    # Min variance of x in combined 20%-vol asset and y in 10%-vol asset: y = 0.8.
    assert res.weights[2] == pytest.approx(0.8, abs=1e-5)
    assert res.volatility == pytest.approx(np.sqrt(0.2**2 * 0.04 + 0.8**2 * 0.01), rel=1e-5)


# ----------------------------------------------------------------- ESG


def test_min_esg_constraint(five_assets: MarketEstimates) -> None:
    base = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0), META)
    assert base.esg_score is not None
    level = base.esg_score + 10
    cons = PortfolioConstraints(min_esg_score=level)
    res = optimise(
        five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons), META
    )
    assert res.esg_score is not None
    assert res.esg_score >= level - 1e-6
    assert any(d.kind == "min_esg" and d.binding for d in res.diagnostics)
    assert res.sharpe_ratio is not None
    assert base.sharpe_ratio is not None
    assert res.sharpe_ratio <= base.sharpe_ratio + 1e-9  # constraint cannot help


def test_min_esg_above_best_score_is_infeasible(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(min_esg_score=85.0)
    with pytest.raises(InfeasibleProblemError, match="best available"):
        optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons), META)


def test_min_esg_requires_scores(five_assets: MarketEstimates) -> None:
    meta = AssetMetadata(esg_scores={"A0": 50.0})
    cons = PortfolioConstraints(min_esg_score=40.0)
    with pytest.raises(InvalidInputError, match="Missing: A1"):
        optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons), meta)
    # Excluding the unscored assets resolves it.
    cons_ok = PortfolioConstraints(
        min_esg_score=40.0, excluded_assets=frozenset({"A1", "A2", "A3", "A4"})
    )
    res = optimise(
        five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons_ok), meta
    )
    assert res.weights[0] == pytest.approx(1.0)


def test_esg_rejected_for_long_short(five_assets: MarketEstimates) -> None:
    cons = PortfolioConstraints(min_weight=-0.5, min_esg_score=50.0)
    with pytest.raises(InvalidInputError, match="long-only"):
        optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY, constraints=cons), META)


def test_esg_tilt_increases_score_and_reports_unadjusted_return(
    five_assets: MarketEstimates,
) -> None:
    scores = []
    for tilt in [0.0, 0.01, 0.03, 0.1]:
        cons = PortfolioConstraints(esg_tilt=tilt)
        res = optimise(
            five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.0, constraints=cons), META
        )
        assert res.esg_score is not None
        scores.append(res.esg_score)
        assert res.expected_return == pytest.approx(
            float(res.weights @ five_assets.expected_returns)
        )
        if tilt > 0:
            assert res.esg_adjusted_return is not None
    assert all(b >= a - 1e-6 for a, b in itertools.pairwise(scores))
    assert scores[-1] > scores[0] + 1.0


def test_esg_tilt_inactive_for_min_vol(five_assets: MarketEstimates) -> None:
    base = optimise(five_assets, OptimisationRequest(Objective.MIN_VOLATILITY), META)
    tilted = optimise(
        five_assets,
        OptimisationRequest(
            Objective.MIN_VOLATILITY, constraints=PortfolioConstraints(esg_tilt=0.05)
        ),
        META,
    )
    np.testing.assert_allclose(base.weights, tilted.weights, atol=1e-8)
    assert any("does not affect" in w for w in tilted.warnings)


def test_esg_sharpe_frontier_is_non_increasing(five_assets: MarketEstimates) -> None:
    pts = esg_sharpe_frontier(
        five_assets, PortfolioConstraints(), META, 0.0, [30, 45, 60, 70, 79, 90]
    )
    feasible = [p for p in pts if p.feasible]
    assert not pts[-1].feasible  # 90 > best score 80
    sharpes = [p.result.sharpe_ratio for p in feasible if p.result]
    assert all(b <= a + 1e-7 for a, b in itertools.pairwise(sharpes))  # type: ignore[operator]


# ----------------------------------------------------------------- frontier


def test_frontier_properties(five_assets: MarketEstimates) -> None:
    ef = efficient_frontier(five_assets, PortfolioConstraints(), 0.02, n_points=25)
    rets = np.array([p.expected_return for p in ef.points])
    vols = np.array([p.volatility for p in ef.points])
    assert len(ef.points) == 25
    assert np.all(np.diff(rets) > 0)
    assert np.all(np.diff(vols) >= -1e-9)  # volatility rises along the efficient branch
    assert vols[0] == pytest.approx(ef.min_volatility.volatility, rel=1e-6)
    assert ef.max_sharpe is not None
    assert ef.max_sharpe.sharpe_ratio is not None
    for p in ef.points:
        assert p.sharpe_ratio is not None
        assert p.sharpe_ratio <= ef.max_sharpe.sharpe_ratio + 1e-7
    # Convexity of the frontier in (return, variance) space.
    var = vols**2
    slopes = np.diff(var) / np.diff(rets)
    assert np.all(np.diff(slopes) >= -1e-6)
    # Top end is the highest-return asset in a long-only universe.
    assert rets[-1] == pytest.approx(0.13, abs=1e-6)


def test_unconstrained_frontier_matches_merton(five_assets: MarketEstimates) -> None:
    ef = efficient_frontier(
        five_assets, PortfolioConstraints(min_weight=-1.0, max_weight=2.0), 0.0, n_points=10
    )
    a, b, c, _ = _abc(five_assets)
    d = a * c - b * b
    interior = [
        p for p in ef.points if (p.weights > -1 + 1e-6).all() and (p.weights < 2 - 1e-6).all()
    ]
    assert len(interior) >= 3
    for p in interior:  # where no bound binds, the Merton closed form applies
        m = p.expected_return
        assert p.volatility**2 == pytest.approx((a * m * m - 2 * b * m + c) / d, rel=1e-5)


def test_esg_constraint_shifts_frontier_right(five_assets: MarketEstimates) -> None:
    base = efficient_frontier(five_assets, PortfolioConstraints(), 0.0, META, n_points=15)
    esg = efficient_frontier(
        five_assets, PortfolioConstraints(min_esg_score=65.0), 0.0, META, n_points=15
    )
    assert esg.min_volatility.volatility >= base.min_volatility.volatility - 1e-9
    for p in esg.points:
        assert p.esg_score is not None
        assert p.esg_score >= 65.0 - 1e-6


def test_optimisation_is_deterministic(five_assets: MarketEstimates) -> None:
    a = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.01), META)
    b = optimise(five_assets, OptimisationRequest(Objective.MAX_SHARPE, 0.01), META)
    np.testing.assert_array_equal(a.weights, b.weights)
