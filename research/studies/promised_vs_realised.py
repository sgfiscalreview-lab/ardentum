"""Study 3: the optimiser's promise versus what actually happened.

Michaud (1989) called mean-variance optimisers "error maximisers": they pour money into the
assets whose past returns look best, which is partly noise, so the portfolio they promise
is better than the one you get. Kan and Zhou (2007) and Kan and Smith (2008) showed the
in-sample efficient frontier is biased upwards. This study measures the gap directly: at
every year end from 1970, using only the past 60 or 120 months, it builds the maximum-Sharpe
portfolio, records the Sharpe ratio the optimiser promises, then the Sharpe ratio the same
weights earn over the next 12 months. It repeats this with shrinkage estimators (Bayes-Stein
means, Ledoit-Wolf covariance) to see how much of the gap they close, and draws the
promised and realised frontiers for one illustrative period.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ardentum.quant.errors import QuantError
from ardentum.quant.estimation import CovarianceEstimator, MeanEstimator, estimate
from ardentum.quant.frontier import efficient_frontier
from ardentum.quant.optimisation import (
    Objective,
    OptimisationRequest,
    PortfolioConstraints,
    optimise,
)
from research import plotting, stats

ESTIMATORS = {
    "Sample estimates": (MeanEstimator.HISTORICAL, CovarianceEstimator.SAMPLE),
    "Shrinkage (Bayes-Stein + Ledoit-Wolf)": (
        MeanEstimator.BAYES_STEIN,
        CovarianceEstimator.LEDOIT_WOLF,
    ),
}
ILLUSTRATION = ("2000-01-01", "2004-12-31", "2005-01-01", "2009-12-31")  # estimate, then realise


def realised_sharpe(weights: np.ndarray, future: pd.DataFrame, rf: pd.Series) -> float:
    ex = future.to_numpy() @ weights - rf.loc[future.index].to_numpy()
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * np.sqrt(12)) if sd > 0 else float("nan")


def run(industries: pd.DataFrame, factors: pd.DataFrame, out: Path) -> dict:  # type: ignore[type-arg]
    rf = factors["RF"]
    rets = industries.loc[industries.index.isin(rf.index)]
    ends = [d for d in rets.index if d.month == 12 and d.year >= 1969]
    results: dict[str, dict] = {}  # type: ignore[type-arg]
    records = []

    # Equal weights: nothing estimated, so nothing promised. Monthly excess returns by year.
    def next_year(end: pd.Timestamp) -> pd.DataFrame:
        pos = rets.index.get_loc(end)
        return rets.iloc[pos + 1 : pos + 13]

    equal = {
        end.year: next_year(end).mean(axis=1).to_numpy() - rf.loc[next_year(end).index].to_numpy()
        for end in ends
        if rets.index.get_loc(end) + 12 < len(rets)
    }

    for lookback in (60, 120):
        for label, (mean_est, cov_est) in ESTIMATORS.items():
            promised, realised, years, skipped = [], [], [], 0
            delivered: list[np.ndarray] = []  # every out-of-sample month, in order
            for end in ends:
                pos = rets.index.get_loc(end)
                if pos + 1 < lookback or end.year not in equal:
                    continue
                window = rets.iloc[pos - lookback + 1 : pos + 1]
                future = next_year(end)
                rf_annual = (1 + rf.loc[window.index].mean()) ** 12 - 1
                est = estimate(window, 12, mean_estimator=mean_est, covariance_estimator=cov_est)
                try:
                    res = optimise(est, OptimisationRequest(Objective.MAX_SHARPE, rf_annual))
                except QuantError:
                    skipped += 1  # no portfolio beat the T-bill in this window
                    continue
                p = float(res.sharpe_ratio) if res.sharpe_ratio is not None else float("nan")
                r = realised_sharpe(res.weights, future, rf)
                promised.append(p)
                realised.append(r)
                years.append(end.year)
                delivered.append(future.to_numpy() @ res.weights - rf.loc[future.index].to_numpy())
                records.append(
                    {
                        "lookback": lookback,
                        "estimator": label,
                        "year_end": end.year,
                        "promised": p,
                        "realised_next_12_months": r,
                    }
                )
            opt = np.concatenate(delivered)
            eq = np.concatenate([equal[y] for y in years])  # 1/N over exactly the same months
            _, p_vs_1n = stats.jkm_test(opt, eq)
            pr = np.array(promised)
            results[f"{label}, {lookback}m window"] = {
                "portfolios": len(pr),
                "skipped_no_portfolio_beats_tbill": skipped,
                "out_of_sample_months": len(opt),
                "mean_promised_sharpe": float(pr.mean()),
                "delivered_sharpe": stats.sharpe(opt),
                "delivered_sharpe_standard_error": stats.sharpe_standard_error(opt),
                "promise_minus_delivered": float(pr.mean()) - stats.sharpe(opt),
                "equal_weight_sharpe_same_months": stats.sharpe(eq),
                "p_value_delivered_vs_equal_weight": p_vs_1n,
                "corr_promised_vs_next_12_months": float(
                    pd.Series(pr).corr(pd.Series(np.array(realised)))
                ),
            }

    # Illustration: in-sample frontier (2000-2004) and the same portfolios' 2005-2009 results.
    e0, e1, r0, r1 = (pd.Timestamp(x) for x in ILLUSTRATION)
    window = rets[(rets.index >= e0) & (rets.index <= e1)]
    future = rets[(rets.index >= r0) & (rets.index <= r1)]
    est = estimate(
        window,
        12,
        mean_estimator=MeanEstimator.HISTORICAL,
        covariance_estimator=CovarianceEstimator.SAMPLE,
    )
    frontier = efficient_frontier(est, PortfolioConstraints(), n_points=25)
    promised_curve = [(p.volatility, p.expected_return) for p in frontier.points]
    realised_curve = []
    for p in frontier.points:
        r = future.to_numpy() @ p.weights
        realised_curve.append((float(r.std(ddof=1) * np.sqrt(12)), float(r.mean() * 12)))
    results["illustration"] = {
        "estimated_on": [str(e0.date()), str(e1.date())],
        "realised_on": [str(r0.date()), str(r1.date())],
        "promised": promised_curve,
        "realised": realised_curve,
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    pd.DataFrame(records).to_csv(out / "portfolios.csv", index=False)

    # Figure 1: average promise versus what was delivered, each setting, with 1/N.
    settings = [k for k in results if k != "illustration"]
    fig, ax = plotting.figure(7.0, 4.2)
    x = np.arange(len(settings))
    bars = (
        ("Promised (average, in sample)", "mean_promised_sharpe", None, plotting.SERIES[0]),
        (
            "Delivered (all following months)",
            "delivered_sharpe",
            "delivered_sharpe_standard_error",
            plotting.SERIES[1],
        ),
        (
            "Equal weights (1/N), same months",
            "equal_weight_sharpe_same_months",
            None,
            plotting.SERIES[2],
        ),
    )
    for j, (name, key, se_key, colour) in enumerate(bars):
        ax.bar(
            x + (j - 1) * 0.27,
            [results[k][key] for k in settings],
            yerr=None if se_key is None else [1.96 * results[k][se_key] for k in settings],
            width=0.27,
            color=colour,
            ecolor=plotting.INK,
            capsize=2,
            label=name if se_key is None else f"{name}, 95% interval",
        )
    ax.set_xticks(x, [k.replace(", ", "\n").replace(" (", "\n(") for k in settings], fontsize=6.5)
    ax.set_ylabel("Annualised Sharpe ratio", fontsize=8)
    ax.set_title(
        "Maximum-Sharpe portfolios: promised versus delivered, 1970 onwards",
        fontsize=9,
        color=plotting.INK,
    )
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig1_promised_vs_delivered.png")

    # Figure 2: the illustration frontiers.
    fig, ax = plotting.figure()
    ax.plot(
        *zip(*promised_curve, strict=True),
        color=plotting.SERIES[0],
        linewidth=1.3,
        marker="o",
        markersize=2.5,
        label="Frontier promised by 2000-2004 data",
    )
    ax.plot(
        *zip(*realised_curve, strict=True),
        color=plotting.SERIES[3],
        linewidth=1.3,
        marker="o",
        markersize=2.5,
        label="Same portfolios, 2005-2009 outcome",
    )
    ax.set_xlabel("Annual volatility", fontsize=8)
    ax.set_ylabel("Annual return", fontsize=8)
    ax.set_title(
        "The efficient frontier is an estimate: promised versus realised",
        fontsize=9,
        color=plotting.INK,
    )
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig2_frontier_illustration.png")

    # Figure 3: year by year, the size of the promise says little about the next year.
    fig, ax = plotting.figure(6.0, 5.0)
    df = pd.DataFrame(records)
    for i, label in enumerate(ESTIMATORS):
        sub = df[(df.lookback == 120) & (df.estimator == label)]
        ax.scatter(
            sub.promised,
            sub.realised_next_12_months,
            s=10,
            color=plotting.SERIES[i],
            label=label,
            alpha=0.85,
        )
    lo = min(df.promised.min(), df.realised_next_12_months.min())
    hi = max(df.promised.max(), df.realised_next_12_months.max())
    ax.plot(
        [lo, hi], [lo, hi], color=plotting.INK, linewidth=0.7, linestyle="--", label="Promise kept"
    )
    ax.set_xlabel("Promised Sharpe ratio (in sample, 120-month window)", fontsize=8)
    ax.set_ylabel("Sharpe ratio over the next 12 months", fontsize=8)
    ax.set_title("Each year's promise and the following year", fontsize=9, color=plotting.INK)
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig3_each_year.png")
    return results
