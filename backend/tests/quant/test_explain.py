import pytest

from ardentum.quant.estimation import estimate
from ardentum.quant.explain import explain, resampled_weight_intervals
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
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
