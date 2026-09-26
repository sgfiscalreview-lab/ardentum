"""Walk-forward historical backtesting without look-ahead bias.

Timing convention (row ``t`` of the returns frame is the return from the close of
date ``t-1`` to the close of date ``t``):

1. At a rebalance date ``t`` (the last trading day of each period in the
   schedule) the strategy receives *only* the trailing estimation window of
   returns ``[t-L+1, ..., t]`` — information available at the close of ``t``.
   It receives a copy, so it cannot reach later data.
2. New target weights are traded at the close of ``t`` and earn returns from
   ``t+1`` onward.
3. Between rebalances, weights drift with realised returns (buy and hold).
4. Transaction costs are ``turnover * cost_bps / 10,000`` of portfolio value at
   each trade, where turnover is ``sum_i |w_target - w_drifted|`` (the initial
   purchase counts as turnover of 100%).

The first rebalance is the first scheduled date with at least ``L`` returns of
history; performance is measured strictly after it (the *evaluation period*).
Data before it is used only for estimation. Trading at the same close that
completes the estimation window assumes execution at that closing price, a
mild idealisation documented in METHODOLOGY.

Known limitations: survivorship bias of a universe selected today, no market
impact beyond linear costs, no cash drag, no taxes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError, QuantError
from ardentum.quant.estimation import (
    CovarianceEstimator,
    MeanEstimator,
    estimate,
)
from ardentum.quant.metrics import PerformanceSummary, performance_summary
from ardentum.quant.optimisation import AssetMetadata, OptimisationRequest, optimise
from ardentum.quant.portfolio import validate_weights


class RebalanceFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


_PERIOD_CODE = {
    RebalanceFrequency.MONTHLY: "M",
    RebalanceFrequency.QUARTERLY: "Q",
    RebalanceFrequency.SEMIANNUAL: "Q",  # filtered to Jun/Dec below
    RebalanceFrequency.ANNUAL: "Y",
}


@dataclass(frozen=True)
class StrategyContext:
    as_of: pd.Timestamp
    tickers: tuple[str, ...]
    periods_per_year: int
    current_weights: np.ndarray | None


class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray: ...


@dataclass(frozen=True)
class EqualWeightStrategy:
    name: str = "Equal weight"

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray:  # noqa: ARG002
        n = window.shape[1]
        return np.full(n, 1.0 / n)


@dataclass(frozen=True)
class FixedWeightStrategy:
    weights: tuple[float, ...]
    name: str = "Fixed weights"

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray:  # noqa: ARG002
        return validate_weights(np.array(self.weights), window.shape[1])


@dataclass(frozen=True)
class OptimisedStrategy:
    """Re-estimates inputs on each window and re-solves the optimisation problem."""

    request: OptimisationRequest
    metadata: AssetMetadata = field(default_factory=AssetMetadata)
    mean_estimator: MeanEstimator = MeanEstimator.HISTORICAL
    covariance_estimator: CovarianceEstimator = CovarianceEstimator.LEDOIT_WOLF
    name: str = "Optimised"

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray:
        est = estimate(
            window,
            context.periods_per_year,
            mean_estimator=self.mean_estimator,
            covariance_estimator=self.covariance_estimator,
        )
        return optimise(est, self.request, self.metadata).weights


@dataclass(frozen=True)
class BacktestConfig:
    lookback_periods: int
    rebalance: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_cost_bps: float = 0.0
    risk_free_rate: float = 0.0
    periods_per_year: int = 252
    evaluation_start: dt.date | None = None


@dataclass(frozen=True)
class RebalanceEvent:
    date: dt.date
    status: str  # "rebalanced" or "held"
    weights_before: np.ndarray
    weights_after: np.ndarray
    turnover: float
    cost: float
    estimation_start: dt.date
    estimation_end: dt.date
    message: str | None = None


@dataclass(frozen=True)
class BacktestResult:
    strategy: str
    tickers: tuple[str, ...]
    dates: pd.DatetimeIndex
    returns: np.ndarray  # net of costs
    gross_returns: np.ndarray
    wealth: np.ndarray  # length len(dates) + 1, starts at 1
    start_weights: np.ndarray  # (T x N) weights held at the start of each period
    events: tuple[RebalanceEvent, ...]
    summary: PerformanceSummary
    estimation_start: dt.date
    evaluation_start: dt.date
    evaluation_end: dt.date
    total_cost: float  # fraction of terminal wealth lost to costs: 1 - prod(1 - c_k)
    annualised_turnover: float
    config: BacktestConfig


def rebalance_schedule(index: pd.DatetimeIndex, frequency: RebalanceFrequency) -> pd.DatetimeIndex:
    """Last available date of each calendar period in ``index``."""
    periods = index.to_period(_PERIOD_CODE[frequency])
    s = pd.Series(index, index=index)
    last = s.groupby(periods).max()
    dates = pd.DatetimeIndex(last.to_numpy())
    if frequency is RebalanceFrequency.SEMIANNUAL:
        dates = dates[dates.month.isin([6, 12]) | (dates == index[-1])]
    return dates


def run_backtest(
    returns: pd.DataFrame, strategy: Strategy, config: BacktestConfig
) -> BacktestResult:
    """Simulate ``strategy`` over ``returns`` with walk-forward re-estimation."""
    if not isinstance(returns.index, pd.DatetimeIndex) or not returns.index.is_monotonic_increasing:
        raise InvalidInputError("Returns must be indexed by increasing dates.")
    x = returns.to_numpy(dtype=float)
    if not np.isfinite(x).all() or (x <= -1).any():
        raise InvalidInputError("Returns must be finite and greater than -100%.")
    if config.lookback_periods < 2:
        raise InvalidInputError("Lookback must be at least 2 periods.")
    if config.transaction_cost_bps < 0:
        raise InvalidInputError("Transaction costs cannot be negative.")
    t_len, n = x.shape
    index = returns.index
    tickers = tuple(str(c) for c in returns.columns)
    lookback = config.lookback_periods

    schedule = set(rebalance_schedule(index, config.rebalance))
    eligible = [
        i
        for i in range(lookback - 1, t_len - 1)
        if index[i] in schedule
        and (config.evaluation_start is None or index[i].date() >= config.evaluation_start)
    ]
    if not eligible:
        raise InsufficientDataError(
            f"Not enough data: a {lookback}-period estimation window plus at least one "
            "evaluation period is required before the end of the sample."
        )
    first = eligible[0]
    if t_len - 1 - first < 2:
        raise InsufficientDataError("The evaluation period must contain at least two returns.")
    rebalance_rows = set(eligible)
    cost_rate = config.transaction_cost_bps / 10_000.0

    def rebalance(i: int, current: np.ndarray | None) -> tuple[np.ndarray, RebalanceEvent]:
        lo = i - lookback + 1
        window = returns.iloc[lo : i + 1].copy()
        ctx = StrategyContext(index[i], tickers, config.periods_per_year, current)
        before = np.zeros(n) if current is None else current
        try:
            target = np.asarray(strategy.target_weights(window, ctx), dtype=float)
            target = validate_weights(target, n, allow_short=True)
        except QuantError as exc:
            if current is None:
                raise InvalidInputError(
                    f"The strategy could not form an initial portfolio on {index[i].date()}: {exc}"
                ) from exc
            return current, RebalanceEvent(
                index[i].date(),
                "held",
                before,
                current,
                0.0,
                0.0,
                index[lo].date(),
                index[i].date(),
                f"Kept drifted weights: {exc}",
            )
        turnover = float(np.abs(target - before).sum())
        return target, RebalanceEvent(
            index[i].date(),
            "rebalanced",
            before,
            target,
            turnover,
            turnover * cost_rate,
            index[lo].date(),
            index[i].date(),
        )

    w, first_event = rebalance(first, None)
    events = [first_event]
    pending_cost = first_event.cost
    n_eval = t_len - 1 - first
    gross = np.empty(n_eval)
    net = np.empty(n_eval)
    start_w = np.empty((n_eval, n))
    for j, t in enumerate(range(first + 1, t_len)):
        start_w[j] = w
        r_p = float(w @ x[t])
        gross[j] = r_p
        growth = 1.0 + r_p
        # Costs incurred at the previous close reduce the value that earns this return.
        net_growth = growth * (1.0 - pending_cost)
        pending_cost = 0.0
        drifted = w * (1.0 + x[t]) / growth if growth > 0 else w
        w = drifted
        if t in rebalance_rows:
            w, ev = rebalance(t, drifted)
            events.append(ev)
            # Cost of trading at this close is charged against this period's value.
            net_growth *= 1.0 - ev.cost
        net[j] = net_growth - 1.0

    eval_dates = index[first + 1 :]
    wealth = np.concatenate(([1.0], np.cumprod(1.0 + net)))
    years = n_eval / config.periods_per_year
    turnover_total = sum(e.turnover for e in events[1:])
    return BacktestResult(
        strategy=strategy.name,
        tickers=tickers,
        dates=eval_dates,
        returns=net,
        gross_returns=gross,
        wealth=wealth,
        start_weights=start_w,
        events=tuple(events),
        summary=performance_summary(net, config.periods_per_year, config.risk_free_rate),
        estimation_start=index[first - lookback + 1].date(),
        evaluation_start=eval_dates[0].date(),
        evaluation_end=eval_dates[-1].date(),
        total_cost=float(1.0 - np.prod([1.0 - e.cost for e in events])),
        annualised_turnover=float(turnover_total / years) if years > 0 else 0.0,
        config=config,
    )
