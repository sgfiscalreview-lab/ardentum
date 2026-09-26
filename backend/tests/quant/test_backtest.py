import numpy as np
import pandas as pd
import pytest

from ardentum.quant.backtest import (
    BacktestConfig,
    EqualWeightStrategy,
    FixedWeightStrategy,
    OptimisedStrategy,
    RebalanceFrequency,
    StrategyContext,
    rebalance_schedule,
    run_backtest,
)
from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.metrics import sharpe_ratio
from ardentum.quant.optimisation import Objective, OptimisationRequest
from tests.conftest import make_returns


def test_schedule_uses_last_trading_day_of_month() -> None:
    idx = pd.bdate_range("2024-01-01", "2024-04-30")
    sched = rebalance_schedule(idx, RebalanceFrequency.MONTHLY)
    assert [d.date().isoformat() for d in sched] == [
        "2024-01-31",
        "2024-02-29",
        "2024-03-29",
        "2024-04-30",
    ]
    q = rebalance_schedule(idx, RebalanceFrequency.QUARTERLY)
    assert [d.date().isoformat() for d in q] == ["2024-03-29", "2024-04-30"]


def _manual_equal_weight(returns: pd.DataFrame, first: int, rebal: set[int]) -> np.ndarray:
    x = returns.to_numpy()
    n = x.shape[1]
    w = np.full(n, 1 / n)
    out = []
    for t in range(first + 1, len(x)):
        rp = w @ x[t]
        out.append(rp)
        w = w * (1 + x[t]) / (1 + rp)
        if t in rebal:
            w = np.full(n, 1 / n)
    return np.array(out)


def test_equal_weight_matches_manual_simulation() -> None:
    df = make_returns(n_obs=400, n_assets=4, seed=3)
    cfg = BacktestConfig(lookback_periods=60, rebalance=RebalanceFrequency.MONTHLY)
    res = run_backtest(df, EqualWeightStrategy(), cfg)
    sched = set(rebalance_schedule(df.index, RebalanceFrequency.MONTHLY))
    rows = [i for i in range(59, len(df) - 1) if df.index[i] in sched]
    expected = _manual_equal_weight(df, rows[0], set(rows))
    np.testing.assert_allclose(res.returns, expected, atol=1e-14)
    assert res.evaluation_start == df.index[rows[0] + 1].date()
    assert res.estimation_start == df.index[rows[0] - 59].date()
    np.testing.assert_allclose(res.wealth[-1], np.prod(1 + expected))


def test_fixed_weights_buy_and_hold_single_asset() -> None:
    df = make_returns(n_obs=300, n_assets=3, seed=4)
    cfg = BacktestConfig(lookback_periods=30, rebalance=RebalanceFrequency.ANNUAL)
    res = run_backtest(df, FixedWeightStrategy((0.0, 1.0, 0.0)), cfg)
    first = df.index.get_loc(pd.Timestamp(res.evaluation_start)) - 1
    np.testing.assert_allclose(res.returns, df["A1"].to_numpy()[first + 1 :], atol=1e-14)


def test_transaction_costs() -> None:
    df = make_returns(n_obs=500, n_assets=4, seed=5)
    free = run_backtest(df, EqualWeightStrategy(), BacktestConfig(60))
    costly = run_backtest(df, EqualWeightStrategy(), BacktestConfig(60, transaction_cost_bps=25))
    # Same trades, so terminal wealth ratio equals the product of (1 - cost) factors.
    ratio = costly.wealth[-1] / free.wealth[-1]
    assert ratio == pytest.approx(np.prod([1 - e.cost for e in costly.events]), rel=1e-12)
    assert costly.events[0].turnover == pytest.approx(1.0)  # initial purchase
    assert costly.events[0].cost == pytest.approx(0.0025)
    assert costly.total_cost == pytest.approx(1 - ratio, rel=1e-12)
    np.testing.assert_allclose(costly.gross_returns, free.gross_returns)


def test_no_look_ahead_future_shock_does_not_change_past() -> None:
    """Weights chosen on or before a date must be invariant to any change in later data."""
    df = make_returns(n_obs=700, n_assets=5, seed=8)
    strategy = OptimisedStrategy(OptimisationRequest(Objective.MAX_SHARPE, 0.0))
    cfg = BacktestConfig(lookback_periods=250, rebalance=RebalanceFrequency.MONTHLY)
    base = run_backtest(df, strategy, cfg)

    cut = df.index[520]
    shocked = df.copy()
    shocked.loc[shocked.index > cut, "A0"] = 0.05  # A0 becomes a spectacular asset
    after = run_backtest(shocked, strategy, cfg)

    for e1, e2 in zip(base.events, after.events, strict=True):
        if pd.Timestamp(e1.date) <= cut:
            np.testing.assert_array_equal(e1.weights_after, e2.weights_after)
    upto = base.dates <= cut
    np.testing.assert_array_equal(base.returns[upto], after.returns[upto])
    # And it does change the later decisions (the test has power).
    later = [e for e in after.events if pd.Timestamp(e.date) > cut + pd.Timedelta(days=60)]
    assert any(e.weights_after[0] > 0.5 for e in later)


class _SpyStrategy:
    name = "spy"

    def __init__(self) -> None:
        self.calls: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray:
        self.calls.append((window.index[-1], context.as_of, len(window)))
        return np.full(window.shape[1], 1 / window.shape[1])


def test_strategy_only_sees_trailing_window() -> None:
    df = make_returns(n_obs=300, n_assets=3, seed=9)
    spy = _SpyStrategy()
    run_backtest(df, spy, BacktestConfig(lookback_periods=40))
    assert spy.calls
    for last, as_of, length in spy.calls:
        assert last == as_of  # never beyond the decision date
        assert length == 40


def test_optimised_backtest_runs_and_reports_periods() -> None:
    df = make_returns(n_obs=900, n_assets=5, seed=10)
    strategy = OptimisedStrategy(OptimisationRequest(Objective.MIN_VOLATILITY))
    res = run_backtest(df, strategy, BacktestConfig(252, RebalanceFrequency.QUARTERLY, 10, 0.02))
    assert res.evaluation_start > res.estimation_start
    assert len(res.dates) == len(res.returns)
    assert res.summary.observations == len(res.returns)
    assert res.summary.sharpe_ratio.value == pytest.approx(sharpe_ratio(res.returns, 252, 0.02))
    np.testing.assert_allclose(res.start_weights.sum(axis=1), 1.0)
    assert res.annualised_turnover > 0


def test_insufficient_history() -> None:
    df = make_returns(n_obs=50, n_assets=3, seed=1)
    with pytest.raises(InsufficientDataError):
        run_backtest(df, EqualWeightStrategy(), BacktestConfig(lookback_periods=60))


def test_failing_initial_strategy_raises() -> None:
    df = make_returns(n_obs=300, n_assets=3, seed=1)
    strategy = OptimisedStrategy(OptimisationRequest(Objective.MAX_SHARPE, risk_free_rate=5.0))
    with pytest.raises(InvalidInputError, match="initial portfolio"):
        run_backtest(df, strategy, BacktestConfig(lookback_periods=60))


def test_rejects_bad_returns() -> None:
    df = make_returns(n_obs=100, n_assets=2, seed=1)
    df.iloc[5, 0] = np.nan
    with pytest.raises(InvalidInputError):
        run_backtest(df, EqualWeightStrategy(), BacktestConfig(lookback_periods=20))
