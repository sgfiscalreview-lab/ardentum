import pytest

from ardentum.quant.estimation import estimate
from ardentum.quant.explain import explain, resampled_weight_intervals
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    SectorLimit,
    optimise,
)
from tests.conftest import make_returns


def test_max_sharpe_explanations_follow_kkt() -> None:
    df = make_returns(n_obs=1500, n_assets=8, seed=21)
    est = estimate(df, 252)
    req = OptimisationRequest(Objective.MAX_SHARPE, 0.02)
    res = optimise(est, req)
    ex = explain(res, est, req)
    statuses = {a.status for a in ex.assets}
    assert "held" in statuses
    for a in ex.assets:
        assert a.required_return is not None
        if a.status == "zero_by_optimiser":
            assert a.expected_return <= a.required_return + 1e-6
            assert "below" in a.reason
        if a.status == "held":
            assert a.expected_return == pytest.approx(a.required_return, abs=1e-4)
    assert sum(a.risk_contribution_pct for a in ex.assets) == pytest.approx(1.0)
    assert ex.assumptions
    assert any("standard error" in w for w in ex.warnings)


def test_a_zero_weight_kept_out_by_a_full_sector_is_attributed_to_that_limit() -> None:
    # A4 earns more than its covariance requires, so "its return is below what it would
    # need" would be false; the full sector is what keeps it out.
    df = make_returns(n_obs=1500, n_assets=6, seed=21)
    est = estimate(df, 252)
    meta = AssetMetadata(sectors={f"A{i}": "XYZ"[i // 2] for i in range(6)})
    cons = PortfolioConstraints(sector_limits=(SectorLimit("Z", max_weight=0.05),))
    req = OptimisationRequest(Objective.MAX_SHARPE, 0.02, constraints=cons)
    ex = explain(optimise(est, req, meta), est, req)
    by = {a.ticker: a for a in ex.assets}
    a4 = by["A4"]
    assert a4.status == "zero_by_optimiser"
    assert a4.required_return is not None
    assert a4.expected_return > a4.required_return
    assert "binding Z ≤ 5.0% constraint" in a4.reason
    assert "below" not in a4.reason
    for a in ex.assets:
        if a.status == "zero_by_optimiser" and "below" in a.reason:
            assert a.required_return is not None
            assert a.expected_return < a.required_return


def test_a_binding_esg_floor_is_named_only_for_assets_that_would_lower_the_score() -> None:
    df = make_returns(n_obs=1500, n_assets=6, seed=21)
    est = estimate(df, 252)
    scores = dict(zip(df.columns, [90, 85, 80, 30, 20, 10], strict=True))
    req = OptimisationRequest(
        Objective.MAX_SHARPE, 0.02, constraints=PortfolioConstraints(min_esg_score=80)
    )
    ex = explain(optimise(est, req, AssetMetadata(esg_scores=scores)), est, req)
    by = {a.ticker: a for a in ex.assets}
    # A4 earns more than its covariance requires; its low score is what keeps it out.
    assert by["A4"].status == "zero_by_optimiser"
    assert "binding Portfolio ESG score ≥ 80.0 constraint" in by["A4"].reason
    for a in ex.assets:
        if "ESG score ≥" in a.reason and a.status == "zero_by_optimiser":
            assert scores[a.ticker] < 80


def test_with_an_esg_tilt_the_conditions_use_the_adjusted_returns() -> None:
    df = make_returns(n_obs=1500, n_assets=6, seed=21)
    est = estimate(df, 252)
    meta = AssetMetadata(esg_scores=dict(zip(df.columns, [90, 85, 80, 30, 20, 10], strict=True)))
    req = OptimisationRequest(
        Objective.MAX_SHARPE, 0.02, constraints=PortfolioConstraints(esg_tilt=0.05)
    )
    res = optimise(est, req, meta)
    assert res.objective_returns is not None
    ex = explain(res, est, req)
    zero = [a for a in ex.assets if a.status == "zero_by_optimiser"]
    assert zero
    for a in ex.assets:
        assert a.required_return is not None
        if a.status == "held":
            assert a.expected_return == pytest.approx(a.required_return, abs=1e-4)
            assert "ESG-adjusted" in a.reason
    for a in zero:
        assert a.expected_return < a.required_return  # type: ignore[operator]
        assert "ESG preference adjustment" in a.reason


def test_min_vol_explanations_and_bounds() -> None:
    df = make_returns(n_obs=800, n_assets=5, seed=3)
    est = estimate(df, 252)
    req = OptimisationRequest(
        Objective.MIN_VOLATILITY,
        constraints=PortfolioConstraints(max_weight=0.3, excluded_assets=frozenset({"A4"})),
    )
    res = optimise(est, req)
    ex = explain(res, est, req)
    by = {a.ticker: a for a in ex.assets}
    assert by["A4"].status == "excluded"
    assert any(a.status == "at_upper_bound" for a in ex.assets)
    assert ex.headline.startswith("Lowest-risk")
    assert 1.0 <= ex.effective_number_of_assets <= 5.0


def test_resampled_intervals_are_ordered_and_reproducible() -> None:
    df = make_returns(n_obs=500, n_assets=4, seed=5)
    est = estimate(df, 252)
    req = OptimisationRequest(Objective.MAX_SHARPE, 0.0)
    base = optimise(est, req).weights
    a, n_ok = resampled_weight_intervals(
        df, 252, req, AssetMetadata(), base, n_resamples=20, seed=1
    )
    b, _ = resampled_weight_intervals(df, 252, req, AssetMetadata(), base, n_resamples=20, seed=1)
    assert n_ok > 0
    assert a == b
    for iv in a:
        assert iv.p05 <= iv.p50 + 1e-12 <= iv.p95 + 2e-12
        assert 0.0 <= iv.frequency_held <= 1.0
    assert sum(iv.mean for iv in a) == pytest.approx(1.0)
