"""Orchestration for crisis replay, factor exposure and trade lists.

Like ``analysis``, this module only converts between the API contract, the data layer and
the quant engine; every number comes from ``ardentum.quant``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ardentum.api import schemas as s
from ardentum.data import crises
from ardentum.data.providers import kenfrench
from ardentum.quant.errors import InvalidInputError, QuantError
from ardentum.quant.factors import FACTORS, factor_regression, period_factors
from ardentum.quant.portfolio import constant_mix_returns
from ardentum.quant.stress import PeriodNotCoveredError, replay, require_daily
from ardentum.quant.trades import trade_list
from ardentum.services.analysis import _finite, data_window, load, weight_vector
from ardentum.services.market_data import MarketDataService

LOAD_MARGIN = dt.timedelta(days=10)  # prices just before a period's first day
HOLD_THRESHOLD = 0.005  # trades below half a cent are shown as "hold"

STRESS_METHOD = (
    "The portfolio is bought at the close on each period's first day and then held "
    "without trading, so each holding's weight drifts with its price. No costs or taxes. "
    "Recovery keeps holding after the period, using all later data, until the value is "
    "back at the high it had before the low."
)
SYNTHETIC_REASON = (
    "The demo data is synthetic: its dates do not contain this real event. Choose US "
    "industries (real data) to replay it, or replay your own dates."
)
FACTOR_INFO = {
    "MKT_RF": ("Market", "The US stock market's return above the risk-free rate."),
    "SMB": ("Size", "Small companies' shares minus large companies' shares (small minus big)."),
    "HML": ("Value", "Cheap shares (high book-to-market) minus expensive ones (high minus low)."),
}
FACTOR_METHOD = (
    "Ordinary least squares of the portfolio's return above the risk-free rate on the three "
    "Fama-French factors, with Newey-West standard errors. The portfolio is rebalanced to "
    "its weights every period. Loadings are per unit of each factor; alpha and the "
    "contributions are annual averages over the window."
)
TRADES_METHOD = (
    "Trades move every holding to its target weight of the value left after trading. "
    "Costs are the given basis points of each amount traded, paid out of the portfolio, so "
    "the value invested afterwards is the current value plus new money minus all costs."
)


@dataclass(frozen=True)
class _Period:
    key: str
    name: str
    summary: str
    start: dt.date
    end: dt.date
    historical: bool


def _periods(req: s.StressRequest) -> list[_Period]:
    keys = [e.key for e in crises.EPISODES] if req.episodes is None else req.episodes
    unknown = [k for k in keys if k not in crises.BY_KEY]
    if unknown:
        raise InvalidInputError(
            f"Unknown crisis: {', '.join(unknown)}. Choose from "
            f"{', '.join(e.key for e in crises.EPISODES)}."
        )
    out = [
        _Period(e.key, e.name, e.summary, e.start, e.end, True)
        for e in crises.EPISODES
        if e.key in keys
    ]
    if req.custom is not None:
        c = req.custom
        out.append(_Period("custom", c.name, "Dates you chose.", c.start, c.end, False))
    if not out:
        raise InvalidInputError("Choose at least one period to replay.")
    return out


def _held(portfolio: s.PortfolioSpecIn) -> tuple[list[str], np.ndarray]:
    held = {t: w for t, w in portfolio.weights.items() if abs(w) > 1e-12}
    if not held:
        raise InvalidInputError("The portfolio has no holdings.")
    tickers = list(held)
    return tickers, weight_vector(tickers, held)


def crisis_catalogue() -> list[s.CrisisOut]:
    return [
        s.CrisisOut(key=e.key, name=e.name, summary=e.summary, start=e.start, end=e.end)
        for e in crises.EPISODES
    ]


def run_stress(service: MarketDataService, req: s.StressRequest) -> s.StressResponse:
    periods = _periods(req)
    tickers, w = _held(req.portfolio)
    info, _ = service.get_dataset(req.universe.dataset_id)
    bench = next((a for a in info.assets if a.is_benchmark), None)
    extra = [bench.ticker] if bench is not None and bench.ticker not in tickers else []
    u = req.universe
    data = service.load(
        u.dataset_id,
        tickers + extra,
        min(p.start for p in periods) - LOAD_MARGIN,
        None,
        "daily",
        u.base_currency,
        u.currency_hedged,
    )
    require_daily(data.returns)
    synthetic = data.provenance.is_synthetic
    out: list[s.EpisodeOut] = []
    for p in periods:
        base = {"key": p.key, "name": p.name, "summary": p.summary, "start": p.start, "end": p.end}
        if synthetic and p.historical:
            out.append(s.EpisodeOut(**base, available=False, reason=SYNTHETIC_REASON))
            continue
        try:
            res = replay(data.returns[tickers], w, p.start, p.end)
        except PeriodNotCoveredError as exc:
            out.append(s.EpisodeOut(**base, available=False, reason=str(exc)))
            continue
        bench_res = (
            replay(data.returns[[bench.ticker]], np.array([1.0]), p.start, p.end)
            if bench is not None
            else None
        )
        out.append(
            s.EpisodeOut(
                **base,
                available=True,
                total_return=_finite(res.total_return),
                max_drawdown=_finite(res.max_drawdown),
                worst_day_return=_finite(res.worst_period_return),
                worst_day=res.worst_period_date,
                trough_date=res.trough_date,
                recovery_date=res.recovery_date,
                recovery_days=res.recovery_days,
                benchmark_total_return=None
                if bench_res is None
                else _finite(bench_res.total_return),
                trading_days=len(res.period_returns),
                assets=[
                    s.EpisodeAssetOut(
                        ticker=t,
                        weight=float(w[i]),
                        total_return=_finite(float(res.asset_returns[i])),
                        contribution=_finite(float(res.contributions[i])),
                    )
                    for i, t in enumerate(tickers)
                ],
                dates=[d.date() for d in res.dates],
                portfolio_path=[_finite(float(v)) for v in res.value],
                benchmark_path=None
                if bench_res is None
                else [_finite(float(v)) for v in bench_res.value],
            )
        )
    return s.StressResponse(
        portfolio_name=req.portfolio.name,
        benchmark_ticker=bench.ticker if bench is not None else None,
        benchmark_name=bench.name if bench is not None else None,
        episodes=out,
        data_end=data.returns.index[-1].date(),
        method=STRESS_METHOD,
        source=crises.SOURCE,
        data=data_window(data),
    )


def run_factors(service: MarketDataService, req: s.FactorRequest) -> s.FactorResponse:
    tickers, w = _held(req.portfolio)
    data = load(service, req.universe.model_copy(update={"tickers": tickers}))
    if data.provenance.is_synthetic:
        raise InvalidInputError(
            "Factor exposure needs real returns: the demo data is synthetic, so it has no "
            "link to the real Fama-French factors. Choose US industries (real data) or your "
            "own data."
        )
    daily, payload = service.fama_french_factors()
    pf = period_factors(daily, pd.DatetimeIndex(data.prices.index))
    rets = data.returns.loc[pf.frame.index, tickers]
    rf = pf.frame["RF"].to_numpy()
    f = pf.frame[list(FACTORS)].to_numpy()
    ppy = data.periods_per_year
    port = constant_mix_returns(rets, w).to_numpy()
    reg = factor_regression(port - rf, f, ppy)

    notes: list[str] = []
    last_factor = daily.index[-1].date()
    if pf.dropped_after:
        notes.append(
            f"The factors are published up to {last_factor.isoformat()}; the last "
            f"{pf.dropped_after} periods of the window are not used."
        )
    if pf.dropped_before:
        notes.append(
            f"The factors start {daily.index[0].date().isoformat()}; the first "
            f"{pf.dropped_before} periods of the window are not used."
        )
    if pf.dropped_empty:
        notes.append(f"{pf.dropped_empty} periods contain no US trading day and are not used.")
    if data.currency != "USD":
        notes.append(
            f"Returns are in {data.currency} but the factors are US dollar returns, so "
            "exchange-rate moves show up in alpha and in the unexplained part."
        )
    assets: list[s.AssetFactorOut] = []
    for i, t in enumerate(tickers):
        try:
            a = factor_regression(rets[t].to_numpy() - rf, f, ppy)
        except QuantError as exc:
            notes.append(f"{t}: no factor loadings ({exc})")
            continue
        assets.append(
            s.AssetFactorOut(
                ticker=t,
                weight=float(w[i]),
                alpha=_finite(a.alpha),
                loadings={k: _finite(float(v)) for k, v in zip(FACTORS, a.loadings, strict=True)},
                r_squared=_finite(a.r_squared),
            )
        )
    stale = " (the Data Library could not be reached; last cached copy)" if payload.stale else ""
    return s.FactorResponse(
        portfolio_name=req.portfolio.name,
        alpha=_finite(reg.alpha),
        alpha_std_error=_finite(float(reg.std_errors[0]) * ppy),
        alpha_t_stat=_finite(float(reg.t_stats[0])),
        alpha_p_value=_finite(float(reg.p_values[0])),
        factors=[
            s.FactorLoadingOut(
                key=k,
                name=FACTOR_INFO[k][0],
                description=FACTOR_INFO[k][1],
                loading=_finite(float(reg.loadings[j])),
                std_error=_finite(float(reg.std_errors[j + 1])),
                t_stat=_finite(float(reg.t_stats[j + 1])),
                p_value=_finite(float(reg.p_values[j + 1])),
                factor_mean=_finite(float(reg.factor_means[j])),
                contribution=_finite(float(reg.contributions[j])),
            )
            for j, k in enumerate(FACTORS)
        ],
        r_squared=_finite(reg.r_squared),
        adj_r_squared=_finite(reg.adj_r_squared),
        residual_volatility=_finite(reg.residual_volatility),
        mean_excess_return=_finite(reg.mean_excess_return),
        observations=reg.observations,
        newey_west_lags=reg.lags,
        first_period=pf.frame.index[0].date(),
        last_period=pf.frame.index[-1].date(),
        assets=assets,
        factor_source=(
            "Fama-French three factors and risk-free rate (daily), "
            f"{kenfrench.SOURCE}, retrieved {payload.fetched_at.date().isoformat()}{stale}. "
            "Fama and French (1993)."
        ),
        method=FACTOR_METHOD,
        notes=notes,
        data=data_window(data),
    )


def run_trades(req: s.TradesRequest) -> s.TradesResponse:
    target = {t: w for t, w in req.target.weights.items() if abs(w) > 1e-12}
    tickers = sorted(target, key=lambda t: -target[t]) + sorted(
        t for t in req.holdings if t not in target
    )
    h = np.array([float(req.holdings.get(t, 0.0)) for t in tickers])
    w = np.array([float(target.get(t, 0.0)) for t in tickers])
    tl = trade_list(h, w, req.new_money, req.transaction_cost_bps / 10_000.0)
    cw = tl.current_weights
    return s.TradesResponse(
        trades=[
            s.TradeOut(
                ticker=t,
                action="buy"
                if tl.trades[i] >= HOLD_THRESHOLD
                else "sell"
                if tl.trades[i] <= -HOLD_THRESHOLD
                else "hold",
                current_value=_finite(float(h[i])),
                current_weight=None if cw is None else _finite(float(cw[i])),
                target_weight=float(w[i]),
                target_value=_finite(float(tl.target_values[i])),
                trade=_finite(float(tl.trades[i])),
                cost=_finite(float(tl.costs[i])),
            )
            for i, t in enumerate(tickers)
        ],
        value_before=_finite(tl.value_before),
        new_money=_finite(tl.new_money),
        value_after=_finite(tl.value_after),
        total_costs=_finite(tl.total_costs),
        bought=_finite(tl.bought),
        sold=_finite(tl.sold),
        method=TRADES_METHOD,
    )
