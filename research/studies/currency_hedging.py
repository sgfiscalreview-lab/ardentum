"""Study 2: should a European investor hedge the dollar?

A euro- or pound-based investor who buys US shares carries two risks: the shares and the
dollar. Hedging (selling dollars forward) removes the second. The textbook answer is "hedge,
it cuts risk"; Campbell, Serfaty-de Medeiros and Viceira (2010, Journal of Finance) found the
dollar tends to rise when stocks fall, so keeping it can *reduce* risk. This study measures
it for euro and sterling investors in US equities from 1999 to the latest month.

Hedge: a one-month forward re-set each month end, priced by covered interest parity from the
two central banks' policy rates known at the start of the month (the same method as
Ardentum's currency-hedged returns, ``ardentum.quant.currency.hedged_returns``).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ardentum.quant.currency import hedged_returns
from research import plotting, stats

INVESTORS = {"EUR": "euro", "GBP": "sterling"}
CRISES = {
    "2008 financial crisis": ("2007-10-31", "2009-03-31"),
    "2020 Covid crash": ("2020-01-31", "2020-03-31"),
    "2022 rate shock": ("2021-12-31", "2022-09-30"),
}


def investor_returns(
    us: pd.Series, fx: pd.Series, base_rate: pd.Series, usd_rate: pd.Series
) -> pd.DataFrame:
    """Monthly returns of a US asset in the investor's currency: unhedged and hedged."""
    idx = us.index.intersection(fx.index).intersection(base_rate.index).intersection(usd_rate.index)
    us = us.loc[idx]
    fx_ret = fx.loc[idx].pct_change()
    start_base = base_rate.loc[idx].shift(1)  # rate known at the start of each month
    start_usd = usd_rate.loc[idx].shift(1)
    # hedged_returns takes the period length from the date gaps, so it runs on the full
    # aligned index; the first month (no starting rate or exchange rate) is dropped after.
    unhedged = (1 + us) * (1 + fx_ret) - 1
    hedged = hedged_returns(us, fx_ret, start_base, start_usd)
    frame = pd.DataFrame(
        {"local_usd": us, "currency": fx_ret, "unhedged": unhedged, "hedged": hedged}
    )
    return frame.dropna()


def min_variance_hedge_ratio(frame: pd.DataFrame) -> float:
    """Hedge ratio h (0 = none, 1 = full) minimising the variance of h*hedged + (1-h)*unhedged."""
    d = (frame["hedged"] - frame["unhedged"]).to_numpy()
    u = frame["unhedged"].to_numpy()
    return float(-np.cov(u, d, ddof=1)[0, 1] / d.var(ddof=1))


def run(
    industries: pd.DataFrame,
    factors: pd.DataFrame,
    fx: dict[str, pd.Series],
    rates: dict[str, pd.Series],
    out: Path,
) -> dict:  # type: ignore[type-arg]
    assets = pd.concat(
        [factors[["MKT"]].rename(columns={"MKT": "US market"}), industries], axis=1
    ).dropna()
    results: dict[str, dict] = {}  # type: ignore[type-arg]
    market_frames: dict[str, pd.DataFrame] = {}
    for ccy, label in INVESTORS.items():
        per_asset = {}
        for name in assets.columns:
            frame = investor_returns(assets[name], fx[ccy], rates[ccy], rates["USD"])
            if name == "US market":
                market_frames[ccy] = frame
            vol_u = frame["unhedged"].std(ddof=1) * np.sqrt(12)
            vol_h = frame["hedged"].std(ddof=1) * np.sqrt(12)
            per_asset[name] = {
                "months": len(frame),
                "volatility_unhedged": float(vol_u),
                "volatility_hedged": float(vol_h),
                "risk_change_from_hedging": float(vol_h / vol_u - 1),
                "mean_unhedged_annual": float(frame["unhedged"].mean() * 12),
                "mean_hedged_annual": float(frame["hedged"].mean() * 12),
                "corr_us_stocks_vs_dollar": float(frame["local_usd"].corr(frame["currency"])),
                "min_variance_hedge_ratio": min_variance_hedge_ratio(frame),
                "max_drawdown_unhedged": stats.max_drawdown(frame["unhedged"].to_numpy()),
                "max_drawdown_hedged": stats.max_drawdown(frame["hedged"].to_numpy()),
            }
        m = market_frames[ccy]
        crises = {}
        for c, (a, b) in CRISES.items():
            sel = (m.index > pd.Timestamp(a)) & (m.index <= pd.Timestamp(b))
            crises[c] = {
                k: float(np.prod(1 + m.loc[sel, k]) - 1)
                for k in ("local_usd", "unhedged", "hedged", "currency")
            }
        rolling = {}
        for end in range(m.index[0].year + 5, m.index[-1].year + 1):
            window = m[(m.index.year > end - 5) & (m.index.year <= end)]
            if len(window) >= 48:
                rolling[str(end)] = min_variance_hedge_ratio(window)
        results[label] = {
            "assets": per_asset,
            "crises_us_market": crises,
            "rolling_5y_hedge_ratio_us_market": rolling,
            "sample": [str(m.index[0].date()), str(m.index[-1].date())],
        }

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    rows = [
        {"investor": inv, "asset": a, **v}
        for inv, r in results.items()
        for a, v in r["assets"].items()
    ]
    pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)

    # Figure 1: volatility hedged vs unhedged, US market and industries, euro investor.
    euro = results["euro"]["assets"]
    names = list(euro)
    fig, ax = plotting.figure()
    x = np.arange(len(names))
    ax.bar(
        x - 0.19,
        [euro[n]["volatility_unhedged"] for n in names],
        width=0.38,
        color=plotting.SERIES[0],
        label="Unhedged",
    )
    ax.bar(
        x + 0.19,
        [euro[n]["volatility_hedged"] for n in names],
        width=0.38,
        color=plotting.SERIES[1],
        label="Hedged",
    )
    ax.set_xticks(x, names, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Annual volatility (euro terms)", fontsize=8)
    ax.set_title(
        "Does hedging the dollar reduce risk for a euro investor?", fontsize=9, color=plotting.INK
    )
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig1_volatility_euro.png")

    # Figure 2: rolling 5-year risk-minimising hedge ratio for the US market.
    fig, ax = plotting.figure()
    for i, (label, r) in enumerate(results.items()):
        roll = r["rolling_5y_hedge_ratio_us_market"]
        ax.plot(
            [int(k) for k in roll],
            list(roll.values()),
            color=plotting.SERIES[i],
            marker="o",
            markersize=2.5,
            linewidth=1.1,
            label=f"{label} investor",
        )
    ax.axhline(1, color=plotting.INK, linewidth=0.6, linestyle="--")
    ax.axhline(0, color=plotting.INK, linewidth=0.6)
    ax.set_ylabel("Risk-minimising hedge ratio (1 = fully hedged)", fontsize=8)
    ax.set_title(
        "How much of the dollar to hedge, rolling 5-year estimate", fontsize=9, color=plotting.INK
    )
    ax.legend(fontsize=7, frameon=False)
    plotting.save(fig, out / "fig2_hedge_ratio.png")
    return results
