"""Study 1: the 1/N puzzle, twenty years later.

DeMiguel, Garlappi and Uppal (2009, Review of Financial Studies) found that no optimised
portfolio reliably beat simply splitting money equally (1/N) out of sample, because
estimation error in expected returns swamps the gains from optimisation. Their data ended in
the early 2000s. This study reruns the horse race on 12 US industry portfolios with a
walk-forward backtest (each month uses only the previous 60 or 120 months), then asks
whether the result still holds in the twenty years since (2005 to the latest month).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ardentum.quant.backtest import (
    BacktestConfig,
    EqualWeightStrategy,
    OptimisedStrategy,
    RebalanceFrequency,
    StrategyContext,
    run_backtest,
)
from ardentum.quant.errors import QuantError
from ardentum.quant.estimation import CovarianceEstimator, MeanEstimator, estimate
from ardentum.quant.optimisation import Objective, OptimisationRequest, optimise
from research import plotting, stats

EVAL_START = pd.Timestamp("1970-01-01")
SPLIT = pd.Timestamp("2005-01-01")  # after the original paper's sample
CRISES = {"2008 financial crisis": ("2007-10-31", "2009-03-31"), "2020 Covid crash": ("2020-01-31", "2020-03-31"), "2022 rate shock": ("2021-12-31", "2022-09-30")}


@dataclass(frozen=True)
class TangencyStrategy:
    """Maximum-Sharpe portfolio using the average T-bill rate of the estimation window.

    Falls back to minimum variance when no portfolio beats the T-bill in the window
    (reported as a fallback count, never hidden).
    """

    rf: pd.Series
    mean_estimator: MeanEstimator
    covariance_estimator: CovarianceEstimator
    name: str
    fallbacks: list[str]

    def target_weights(self, window: pd.DataFrame, context: StrategyContext) -> np.ndarray:
        est = estimate(window, 12, mean_estimator=self.mean_estimator, covariance_estimator=self.covariance_estimator)
        rf_monthly = float(self.rf.loc[window.index].mean())
        rf_annual = (1 + rf_monthly) ** 12 - 1
        try:
            return optimise(est, OptimisationRequest(Objective.MAX_SHARPE, rf_annual)).weights
        except QuantError:
            self.fallbacks.append(str(context.as_of.date()))
            return optimise(est, OptimisationRequest(Objective.MIN_VOLATILITY)).weights


def strategies(rf: pd.Series, fallbacks: dict[str, list[str]]) -> list:  # type: ignore[type-arg]
    def tangency(name: str, mean: MeanEstimator, cov: CovarianceEstimator) -> TangencyStrategy:
        fallbacks[name] = []
        return TangencyStrategy(rf, mean, cov, name, fallbacks[name])

    return [
        EqualWeightStrategy(name="1/N (equal weight)"),
        OptimisedStrategy(OptimisationRequest(Objective.MIN_VOLATILITY), covariance_estimator=CovarianceEstimator.SAMPLE, name="Minimum variance (sample)"),
        OptimisedStrategy(OptimisationRequest(Objective.MIN_VOLATILITY), covariance_estimator=CovarianceEstimator.LEDOIT_WOLF, name="Minimum variance (shrinkage)"),
        tangency("Maximum Sharpe (sample)", MeanEstimator.HISTORICAL, CovarianceEstimator.SAMPLE),
        tangency("Maximum Sharpe (shrinkage)", MeanEstimator.BAYES_STEIN, CovarianceEstimator.LEDOIT_WOLF),
        OptimisedStrategy(OptimisationRequest(Objective.MIN_CVAR, cvar_confidence=0.90), covariance_estimator=CovarianceEstimator.LEDOIT_WOLF, name="Minimum CVaR 90% (tail risk)"),
    ]


def evaluate(net: pd.Series, rf: pd.Series, bench: pd.Series) -> dict[str, float]:
    ex = (net - rf.loc[net.index]).to_numpy()
    ex_b = (bench - rf.loc[bench.index]).to_numpy()
    z, p = stats.jkm_test(ex, ex_b)
    return {
        "months": len(ex),
        "mean_excess_annual": float(ex.mean() * 12),
        "volatility_annual": float(ex.std(ddof=1) * np.sqrt(12)),
        "sharpe": stats.sharpe(ex),
        "sharpe_minus_1n": stats.sharpe(ex) - stats.sharpe(ex_b),
        "p_value_vs_1n": p,
        "certainty_equivalent": stats.certainty_equivalent(ex),
        "max_drawdown": stats.max_drawdown(net.to_numpy()),
    }


def run(industries: pd.DataFrame, factors: pd.DataFrame, out: Path) -> dict:  # type: ignore[type-arg]
    rf = factors["RF"]
    rets = industries.loc[industries.index.isin(rf.index)]
    results: dict[str, dict] = {}  # type: ignore[type-arg]
    series: dict[str, pd.Series] = {}
    for lookback in (60, 120):
        for cost_bps in (0.0, 50.0):
            key = f"window {lookback}m, costs {int(cost_bps)}bp"
            fallbacks: dict[str, list[str]] = {}
            runs = {}
            for strat in strategies(rf, fallbacks):
                cfg = BacktestConfig(
                    lookback_periods=lookback,
                    rebalance=RebalanceFrequency.MONTHLY,
                    transaction_cost_bps=cost_bps,
                    periods_per_year=12,
                    evaluation_start=(EVAL_START - pd.offsets.MonthEnd(1)).date(),
                )
                res = run_backtest(rets, strat, cfg)
                net = pd.Series(res.returns, index=res.dates)
                runs[strat.name] = (net, res)
            bench = runs["1/N (equal weight)"][0]
            block: dict[str, dict] = {}  # type: ignore[type-arg]
            for name, (net, res) in runs.items():
                periods = {
                    "full": (net.index >= EVAL_START),
                    "1970-2004": (net.index >= EVAL_START) & (net.index < SPLIT),
                    "2005-latest": (net.index >= SPLIT),
                }
                row: dict[str, object] = {
                    p: evaluate(net[m], rf, bench[m]) for p, m in periods.items()
                }
                row["annual_turnover"] = res.annualised_turnover
                row["held_rebalances"] = sum(e.status == "held" for e in res.events)
                row["tangency_fallbacks"] = len(fallbacks.get(name, []))
                row["crisis_returns"] = {
                    c: float(np.prod(1 + net[(net.index > pd.Timestamp(a)) & (net.index <= pd.Timestamp(b))]) - 1)
                    for c, (a, b) in CRISES.items()
                }
                block[name] = row
                if lookback == 120 and cost_bps == 50.0:
                    series[name] = net
            results[key] = block

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    rows = []
    for key, block in results.items():
        for name, row in block.items():
            for period in ("full", "1970-2004", "2005-latest"):
                rows.append({"setting": key, "strategy": name, "period": period, **row[period]})
    pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)

    # Figure 1: growth of $1 (120-month window, 50bp costs), log scale.
    fig, ax = plotting.figure()
    for i, (name, net) in enumerate(series.items()):
        ax.plot(net.index, np.cumprod(1 + net), label=name, color=plotting.SERIES[i], linewidth=1.1)
    ax.set_yscale("log")
    ax.set_title("Growth of $1, 1970 onwards (120-month window, 0.5% trading costs)", fontsize=9, color=plotting.INK)
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig1_growth.png")

    # Figure 2: Sharpe ratio minus 1/N, before and after 2005.
    block = results["window 120m, costs 50bp"]
    names = [n for n in block if not n.startswith("1/N")]
    fig, ax = plotting.figure()
    x = np.arange(len(names))
    for j, (period, colour) in enumerate((("1970-2004", plotting.SERIES[0]), ("2005-latest", plotting.SERIES[1]))):
        ax.bar(x + (j - 0.5) * 0.38, [block[n][period]["sharpe_minus_1n"] for n in names], width=0.38, color=colour, label=period)
    ax.axhline(0, color=plotting.INK, linewidth=0.8)
    ax.set_xticks(x, [n.replace(" (", "\n(") for n in names], fontsize=7)
    ax.set_ylabel("Sharpe ratio minus 1/N", fontsize=8)
    ax.set_title("Does optimising beat equal weights? (above zero = beats 1/N)", fontsize=9, color=plotting.INK)
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig2_sharpe_vs_1n.png")
    return results
