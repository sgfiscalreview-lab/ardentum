"""Orchestration between the API contract, the data layer and the quant engine.

This module contains no financial mathematics of its own: it converts request
models into quant-engine inputs, calls the engine and converts the results into
response models. All numbers originate in ``ardentum.quant``.
"""

from __future__ import annotations

import math
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from ardentum.api import schemas as s
from ardentum.data.models import DataProvenance
from ardentum.quant.attribution import brinson_fachler, carino_link, contributions
from ardentum.quant.backtest import (
    BacktestConfig,
    BacktestResult,
    EqualWeightStrategy,
    FixedWeightStrategy,
    OptimisedStrategy,
    Strategy,
    run_backtest,
)
from ardentum.quant.black_litterman import BlackLittermanSpec, View
from ardentum.quant.errors import InvalidInputError
from ardentum.quant.estimation import MarketEstimates, MeanEstimator, estimate, risk_free_arithmetic
from ardentum.quant.explain import explain, resampled_weight_intervals
from ardentum.quant.frontier import (
    CvarFrontierPoint,
    FrontierPoint,
    efficient_frontier,
    esg_sharpe_frontier,
    mean_cvar_frontier,
    portfolio_var_cvar,
)
from ardentum.quant.metrics import (
    MetricValue,
    PerformanceSummary,
    drawdown_series,
    performance_summary,
    tracking_error,
)
from ardentum.quant.montecarlo import (
    MonteCarloConfig,
    MonteCarloResult,
    SimulationMethod,
    simulate_bootstrap,
    simulate_parametric,
)
from ardentum.quant.optimisation import (
    OptimisationRequest,
    OptimisationResult,
    PortfolioConstraints,
    SectorLimit,
    optimise,
)
from ardentum.quant.portfolio import (
    constant_mix_returns,
    diversification_ratio,
    effective_number_of_assets,
    portfolio_expected_return,
    portfolio_volatility,
    risk_decomposition,
)
from ardentum.services.market_data import LoadedData, MarketDataService
from ardentum.services.open_esg import get_overlay, overlay_assets

# ----------------------------------------------------------------------------- helpers


def _finite(x: float) -> float:
    if not math.isfinite(x):
        raise InvalidInputError("A calculation produced a non-finite value; check the input data.")
    return float(x)


def _opt(x: float | None) -> float | None:
    return None if x is None else _finite(x)


def provenance_out(p: DataProvenance) -> s.ProvenanceOut:
    return s.ProvenanceOut(
        source=p.source,
        is_synthetic=p.is_synthetic,
        adjustment=p.adjustment,
        retrieved_at=p.retrieved_at,
        license_note=p.license_note,
        notes=list(p.notes),
    )


def data_window(data: LoadedData) -> s.DataWindowOut:
    return s.DataWindowOut(
        dataset_id=data.dataset.id,
        start=data.returns.index[0].date(),
        end=data.returns.index[-1].date(),
        observations=len(data.returns),
        frequency=data.frequency.value,
        periods_per_year=data.periods_per_year,
        currency=data.currency,
        provenance=provenance_out(data.provenance),
        quality_notes=list(data.report.notes),
        quality_warnings=list(data.report.warnings),
    )


def black_litterman_out(est: MarketEstimates) -> s.BlackLittermanOut | None:
    bl = est.black_litterman
    if bl is None:
        return None
    return s.BlackLittermanOut(
        prior=bl.spec.prior_label,
        risk_aversion=bl.spec.risk_aversion,
        tau=bl.spec.tau,
        assets=[
            s.BlackLittermanAssetOut(
                ticker=t,
                prior_weight=_finite(float(bl.prior_weights[i])),
                prior_return=_finite(float(bl.prior_returns[i])),
                posterior_return=_finite(float(bl.posterior_returns[i])),
            )
            for i, t in enumerate(est.tickers)
        ],
        views=[v.describe() for v in bl.spec.views],
    )


def estimation_out(est: MarketEstimates, settings: s.EstimationSettings) -> s.EstimationOut:
    return s.EstimationOut(
        black_litterman=black_litterman_out(est),
        risk_free_rate=settings.risk_free_rate,
        risk_free_source=settings.risk_free_source or "Entered by the user",
        mean_estimator=est.mean_estimator.value,
        covariance_estimator=est.covariance_estimator.value,
        mean_shrinkage=est.mean_shrinkage,
        covariance_shrinkage=est.covariance_shrinkage,
        observations=est.observations,
        start=est.start,
        end=est.end,
    )


def metric_out(m: MetricValue) -> s.MetricOut:
    return s.MetricOut(value=_opt(m.value), reason=m.reason)


def performance_out(p: PerformanceSummary) -> s.PerformanceOut:
    return s.PerformanceOut(
        observations=p.observations,
        total_return=_finite(p.total_return),
        cagr=_finite(p.cagr),
        arithmetic_annual_return=_finite(p.arithmetic_annual_return),
        annualised_volatility=_finite(p.annualised_volatility),
        sharpe_ratio=metric_out(p.sharpe_ratio),
        sortino_ratio=metric_out(p.sortino_ratio),
        max_drawdown=_finite(p.max_drawdown),
        calmar_ratio=metric_out(p.calmar_ratio),
        var_95=_finite(p.var_95),
        cvar_95=_finite(p.cvar_95),
        skewness=metric_out(p.skewness),
        excess_kurtosis=metric_out(p.excess_kurtosis),
        best_period=_finite(p.best_period),
        worst_period=_finite(p.worst_period),
        positive_periods_fraction=_finite(p.positive_periods_fraction),
        beta=None if p.beta is None else metric_out(p.beta),
        tracking_error=_opt(p.tracking_error),
        information_ratio=None if p.information_ratio is None else metric_out(p.information_ratio),
    )


def load(
    service: MarketDataService, u: s.UniverseSelection, extra: Sequence[str] = ()
) -> LoadedData:
    tickers = list(u.tickers) + [t for t in extra if t not in u.tickers]
    data = service.load(
        u.dataset_id, tickers, u.start, u.end, u.frequency, u.base_currency, u.currency_hedged
    )
    if u.esg_overlay_id is None:
        return data
    overlay = get_overlay(service, u.esg_overlay_id)
    if overlay.dataset_id != u.dataset_id:
        raise InvalidInputError(
            f"ESG overlay “{overlay.name}” was built for another dataset; build one for this "
            "dataset or remove it from the universe."
        )
    dataset = replace(data.dataset, assets=overlay_assets(data.dataset, tickers, overlay))
    note = (
        f"ESG scores from the open-data overlay “{overlay.name}”: "
        f"{overlay.spec.get('attribution', overlay.license)}"
    )
    return replace(
        data,
        dataset=dataset,
        provenance=replace(data.provenance, notes=(*data.provenance.notes, note)),
    )


def market_cap_weights(
    service: MarketDataService, data: LoadedData, tickers: Sequence[str]
) -> dict[str, float]:
    """Latest market capitalisations from asset metadata or the data source."""
    source_caps = service.market_caps(data.dataset.id) or {}
    caps: dict[str, float] = {}
    missing: list[str] = []
    for t in tickers:
        a = data.asset(t)
        cap = a.market_cap if a.market_cap is not None else source_caps.get(t)
        if cap is None:
            missing.append(t)
            continue
        if a.market_cap is not None and a.currency.upper() != data.currency:
            raise InvalidInputError(
                f"The market capitalisation of {t} is in {a.currency} but results are in "
                f"{data.currency}; use equal or custom prior weights for mixed currencies."
            )
        caps[t] = float(cap)
    if missing:
        raise InvalidInputError(
            f"No market capitalisation for {', '.join(missing)}. Add a market_cap column to "
            "the dataset metadata, or use equal or custom Black-Litterman prior weights."
        )
    return caps


def black_litterman_spec(
    service: MarketDataService,
    data: LoadedData,
    e: s.EstimationSettings,
    tickers: Sequence[str] | None = None,
) -> BlackLittermanSpec | None:
    if e.mean_estimator is not MeanEstimator.BLACK_LITTERMAN:
        return None
    b = e.black_litterman or s.BlackLittermanIn()
    names = list(tickers) if tickers is not None else list(data.tickers)
    if b.prior == "equal_weight":
        weights, label = dict.fromkeys(names, 1.0), "equal weights"
    elif b.prior == "custom":
        weights, label = dict(b.prior_weights or {}), "custom weights"
    else:
        weights, label = market_cap_weights(service, data, names), "market capitalisation"
    return BlackLittermanSpec(
        prior_weights=weights,
        views=tuple(View(v.weights, v.expected_return, v.confidence) for v in b.views),
        risk_aversion=b.risk_aversion,
        tau=b.tau,
        risk_free_rate=risk_free_arithmetic(e.risk_free_rate, data.periods_per_year),
        prior_label=label,
    )


def estimates_for(
    service: MarketDataService,
    data: LoadedData,
    e: s.EstimationSettings,
    tickers: Sequence[str] | None = None,
) -> MarketEstimates:
    rets = data.returns if tickers is None else data.returns[list(tickers)]
    return estimate(
        rets,
        data.periods_per_year,
        mean_estimator=e.mean_estimator,
        covariance_estimator=e.covariance_estimator,
        black_litterman_spec=black_litterman_spec(service, data, e, tickers),
    )


def weight_vector(tickers: Sequence[str], weights: Mapping[str, float]) -> np.ndarray:
    unknown = [t for t in weights if t not in tickers]
    if unknown:
        raise InvalidInputError(
            f"Weights reference assets outside the selection: {', '.join(unknown)}."
        )
    w = np.array([float(weights.get(t, 0.0)) for t in tickers])
    if abs(w.sum() - 1.0) > 1e-6:
        raise InvalidInputError(f"Weights must sum to 100% (they sum to {w.sum():.4%}).")
    return w


def build_constraints(
    c: s.ConstraintsIn, data: LoadedData, tickers: Sequence[str]
) -> tuple[PortfolioConstraints, list[str]]:
    """Translate API constraints; returns (constraints, assets excluded for lacking ESG scores)."""
    excluded = set(c.excluded_assets)
    unscored: list[str] = []
    if c.exclude_unscored_assets:
        unscored = [t for t in tickers if data.asset(t).esg is None and t not in excluded]
        excluded.update(unscored)
    bench = None
    max_te = None
    if c.tracking_error is not None:
        if c.tracking_error.benchmark == "equal_weight":
            bench = {t: 1.0 / len(tickers) for t in tickers}
        else:
            bench = dict(c.tracking_error.benchmark)
        max_te = c.tracking_error.max_tracking_error
    return (
        PortfolioConstraints(
            min_weight=c.min_weight,
            max_weight=c.max_weight,
            asset_bounds=dict(c.asset_bounds),
            sector_limits=tuple(
                SectorLimit(x.sector, x.min_weight, x.max_weight) for x in c.sector_limits
            ),
            excluded_assets=frozenset(excluded),
            excluded_sectors=frozenset(c.excluded_sectors),
            min_esg_score=c.min_esg_score,
            esg_tilt=c.esg_tilt,
            max_gross_exposure=c.max_gross_exposure,
            benchmark_weights=bench,
            max_tracking_error=max_te,
        ),
        unscored,
    )


def opt_request(
    o: s.ObjectiveIn, e: s.EstimationSettings, cons: PortfolioConstraints
) -> OptimisationRequest:
    return OptimisationRequest(
        objective=o.objective,
        risk_free_rate=e.risk_free_rate,
        target_return=o.target_return,
        target_volatility=o.target_volatility,
        risk_aversion=o.risk_aversion,
        constraints=cons,
        cvar_confidence=o.cvar_confidence,
    )


def sector_exposures(
    tickers: Sequence[str], w: np.ndarray, data: LoadedData
) -> list[s.SectorExposureOut]:
    agg: dict[str, float] = {}
    for t, x in zip(tickers, w, strict=True):
        sector = data.asset(t).sector or "Unclassified"
        agg[sector] = agg.get(sector, 0.0) + float(x)
    return [
        s.SectorExposureOut(sector=k, weight=v)
        for k, v in sorted(agg.items(), key=lambda kv: -abs(kv[1]))
        if abs(v) > 1e-9
    ]


def portfolio_result_out(
    res: OptimisationResult, est: MarketEstimates, req: OptimisationRequest, data: LoadedData
) -> tuple[s.PortfolioResultOut, s.ExplanationOut]:
    ex = explain(res, est, req)
    try:
        rd = risk_decomposition(res.weights, est.covariance)
        rc, rcp, mc = rd.risk_contribution, rd.percent_contribution, rd.marginal_contribution
        div: float | None = diversification_ratio(res.weights, est.covariance)
    except Exception:
        rc = rcp = mc = np.zeros_like(res.weights)
        div = None
    holdings = []
    for i, a in enumerate(ex.assets):
        info = data.asset(a.ticker)
        holdings.append(
            s.HoldingOut(
                ticker=a.ticker,
                name=info.name,
                sector=info.sector,
                weight=_finite(a.weight),
                expected_return=_finite(a.expected_return),
                volatility=_finite(a.volatility),
                esg_score=info.esg.score if info.esg else None,
                risk_contribution=_finite(float(rc[i])),
                risk_contribution_pct=_finite(float(rcp[i])),
                marginal_contribution=_finite(float(mc[i])),
                beta_to_portfolio=_finite(a.beta_to_portfolio),
                required_return=_opt(a.required_return),
                status=a.status,
                reason=a.reason,
            )
        )
    out = s.PortfolioResultOut(
        objective=res.objective.value,
        expected_return=_finite(res.expected_return),
        volatility=_finite(res.volatility),
        sharpe_ratio=_opt(res.sharpe_ratio),
        esg_score=_opt(res.esg_score),
        esg_adjusted_return=_opt(res.esg_adjusted_return),
        risk_free_rate=res.risk_free_rate,
        diversification_ratio=_opt(div),
        effective_number_of_assets=_finite(ex.effective_number_of_assets),
        holdings=holdings,
        sector_exposures=sector_exposures(res.tickers, res.weights, data),
        var=_opt(res.var),
        cvar=_opt(res.cvar),
        cvar_confidence=res.cvar_confidence,
        diagnostics=[
            s.ConstraintDiagnosticOut(
                kind=d.kind,
                label=d.label,
                value=_finite(d.value),
                bound=_finite(d.bound),
                binding=d.binding,
                assets=list(d.assets),
                shadow_price=_opt(d.shadow_price),
                shadow_price_unit=d.shadow_price_unit,
            )
            for d in res.diagnostics
        ],
        solver=res.solver,
        warnings=list(res.warnings),
    )
    explanation = s.ExplanationOut(
        objective_summary=ex.objective_summary,
        headline=ex.headline,
        statements=list(ex.statements),
        warnings=list(ex.warnings),
        assumptions=list(ex.assumptions),
    )
    return out, explanation


# ----------------------------------------------------------------------------- analytics


def asset_analytics(service: MarketDataService, req: s.AnalyticsRequest) -> s.AnalyticsResponse:
    bench = req.benchmark
    data = load(service, req.universe, [bench] if bench else [])
    tickers = list(req.universe.tickers)
    est = estimates_for(service, data, req.estimation, tickers)
    b_ret = data.returns[bench].to_numpy() if bench else None
    assets = []
    for i, t in enumerate(tickers):
        info = data.asset(t)
        perf = performance_summary(
            data.returns[t].to_numpy(), data.periods_per_year, req.estimation.risk_free_rate, b_ret
        )
        assets.append(
            s.AssetStatsOut(
                ticker=t,
                name=info.name,
                sector=info.sector,
                esg_score=info.esg.score if info.esg else None,
                expected_return=_finite(float(est.expected_returns[i])),
                performance=performance_out(perf),
            )
        )
    rets = data.returns[tickers]
    std = rets.std()
    corr = rets.corr().to_numpy() if (std > 0).all() else np.eye(len(tickers))
    # Weekly sampling keeps the chart payload small without changing the path shape.
    prices = data.prices[tickers]
    if data.frequency.value == "daily" and len(prices) > 800:
        prices = prices.resample("W-FRI").last().dropna()
    norm = prices / prices.iloc[0] * 100.0
    return s.AnalyticsResponse(
        data=data_window(data),
        estimation=estimation_out(est, req.estimation),
        benchmark=bench,
        assets=assets,
        tickers=tickers,
        correlation=[[_finite(x) for x in row] for row in corr],
        covariance=[[_finite(x) for x in row] for row in est.covariance],
        price_dates=[d.date() for d in norm.index],
        normalised_prices={t: [_finite(x) for x in norm[t]] for t in tickers},
    )


# ----------------------------------------------------------------------------- optimise


def run_optimise(service: MarketDataService, req: s.OptimiseRequest) -> s.OptimiseResponse:
    data = load(service, req.universe)
    est = estimates_for(service, data, req.estimation)
    cons, unscored = build_constraints(req.constraints, data, data.tickers)
    oreq = opt_request(req.objective, req.estimation, cons)
    meta = data.metadata()
    res = optimise(est, oreq, meta)
    result, explanation = portfolio_result_out(res, est, oreq, data)
    stability = None
    n_ok = None
    seed = None
    if req.stability_resamples > 0:
        seed = req.seed if req.seed is not None else secrets.randbelow(2**31)
        intervals, n_ok = resampled_weight_intervals(
            data.returns,
            data.periods_per_year,
            oreq,
            meta,
            res.weights,
            n_resamples=req.stability_resamples,
            seed=seed,
            mean_estimator=req.estimation.mean_estimator,
            covariance_estimator=req.estimation.covariance_estimator,
            black_litterman_spec=black_litterman_spec(service, data, req.estimation),
        )
        stability = [
            s.StabilityOut(
                ticker=iv.ticker,
                weight=iv.weight,
                mean=iv.mean,
                p05=iv.p05,
                p50=iv.p50,
                p95=iv.p95,
                frequency_held=iv.frequency_held,
            )
            for iv in intervals
        ]
    return s.OptimiseResponse(
        result=result,
        explanation=explanation,
        estimation=estimation_out(est, req.estimation),
        data=data_window(data),
        excluded_unscored=unscored,
        stability=stability,
        stability_resamples=n_ok,
        seed=seed,
    )


def _point_out(p: FrontierPoint, tickers: Sequence[str]) -> s.FrontierPointOut:
    return s.FrontierPointOut(
        expected_return=_finite(p.expected_return),
        volatility=_finite(p.volatility),
        sharpe_ratio=_opt(p.sharpe_ratio),
        esg_score=_opt(p.esg_score),
        weights={t: float(w) for t, w in zip(tickers, p.weights, strict=True) if abs(w) > 1e-9},
    )


def _result_point(r: OptimisationResult) -> s.FrontierPointOut:
    return s.FrontierPointOut(
        expected_return=_finite(r.expected_return),
        volatility=_finite(r.volatility),
        sharpe_ratio=_opt(r.sharpe_ratio),
        esg_score=_opt(r.esg_score),
        weights={t: float(w) for t, w in r.weight_map().items() if abs(w) > 1e-9},
    )


def run_frontier(service: MarketDataService, req: s.FrontierRequest) -> s.FrontierResponse:
    data = load(service, req.universe)
    est = estimates_for(service, data, req.estimation)
    cons, unscored = build_constraints(req.constraints, data, data.tickers)
    meta = data.metadata()
    rf = req.estimation.risk_free_rate
    ef = efficient_frontier(est, cons, rf, meta, req.n_points)
    unconstrained = None
    if req.compare_unconstrained and (req.constraints.uses_esg or cons != PortfolioConstraints()):
        base = efficient_frontier(est, PortfolioConstraints(), rf, meta, req.n_points)
        unconstrained = [_point_out(p, est.tickers) for p in base.points]
    return s.FrontierResponse(
        points=[_point_out(p, est.tickers) for p in ef.points],
        min_volatility=_result_point(ef.min_volatility),
        max_sharpe=None if ef.max_sharpe is None else _result_point(ef.max_sharpe),
        max_sharpe_unavailable_reason=ef.max_sharpe_unavailable_reason,
        unconstrained_points=unconstrained,
        assets=[
            s.FrontierAssetOut(
                ticker=t,
                expected_return=_finite(float(ef.asset_expected_returns[i])),
                volatility=_finite(float(ef.asset_volatilities[i])),
                esg_score=(a.esg.score if (a := data.asset(t)).esg else None),
                sector=a.sector,
            )
            for i, t in enumerate(est.tickers)
        ],
        risk_free_rate=rf,
        risk_free_rate_arithmetic=est.risk_free_arithmetic(rf),
        warnings=list(ef.warnings),
        estimation=estimation_out(est, req.estimation),
        data=data_window(data),
        excluded_unscored=unscored,
    )


def _cvar_point_out(p: CvarFrontierPoint, tickers: Sequence[str]) -> s.CvarFrontierPointOut:
    return s.CvarFrontierPointOut(
        expected_return=_finite(p.expected_return),
        volatility=_finite(p.volatility),
        var=_finite(p.var),
        cvar=_finite(p.cvar),
        sharpe_ratio=_opt(p.sharpe_ratio),
        esg_score=_opt(p.esg_score),
        weights={t: float(w) for t, w in zip(tickers, p.weights, strict=True) if abs(w) > 1e-9},
    )


def run_cvar_frontier(
    service: MarketDataService, req: s.CvarFrontierRequest
) -> s.CvarFrontierResponse:
    data = load(service, req.universe)
    est = estimates_for(service, data, req.estimation)
    cons, unscored = build_constraints(req.constraints, data, data.tickers)
    meta = data.metadata()
    rf = req.estimation.risk_free_rate
    beta = req.cvar_confidence
    fr = mean_cvar_frontier(est, cons, rf, meta, req.n_points, beta)
    # The mean-variance frontier's portfolios, measured by the same historical CVaR.
    mv = efficient_frontier(est, cons, rf, meta, req.n_points)
    mv_points = []
    for p in mv.points:
        var, cvar = portfolio_var_cvar(est, p.weights, beta)
        mv_points.append(
            _cvar_point_out(
                CvarFrontierPoint(
                    p.expected_return,
                    p.volatility,
                    var,
                    cvar,
                    p.sharpe_ratio,
                    p.esg_score,
                    p.weights,
                ),
                est.tickers,
            )
        )
    m = fr.min_cvar
    var, cvar = portfolio_var_cvar(est, m.weights, beta)
    min_point = CvarFrontierPoint(
        m.expected_return, m.volatility, var, cvar, m.sharpe_ratio, m.esg_score, m.weights
    )
    return s.CvarFrontierResponse(
        points=[_cvar_point_out(p, est.tickers) for p in fr.points],
        min_cvar=_cvar_point_out(min_point, est.tickers),
        mean_variance_points=mv_points,
        assets=[
            s.CvarFrontierAssetOut(
                ticker=t,
                expected_return=_finite(float(fr.asset_expected_returns[i])),
                var=_finite(float(fr.asset_var[i])),
                cvar=_finite(float(fr.asset_cvar[i])),
                sector=data.asset(t).sector,
            )
            for i, t in enumerate(est.tickers)
        ],
        cvar_confidence=beta,
        frequency=data.frequency.value,
        observations=fr.observations,
        risk_free_rate=rf,
        warnings=list(dict.fromkeys([*fr.warnings, *mv.warnings])),
        estimation=estimation_out(est, req.estimation),
        data=data_window(data),
        excluded_unscored=unscored,
    )


# ----------------------------------------------------------------------------- ESG impact


def _without_esg(c: s.ConstraintsIn) -> s.ConstraintsIn:
    return c.model_copy(
        update={
            "min_esg_score": None,
            "esg_tilt": 0.0,
            "excluded_sectors": [],
            "exclude_unscored_assets": False,
        }
    )


def run_esg_impact(service: MarketDataService, req: s.EsgImpactRequest) -> s.EsgImpactResponse:
    if not req.constraints.uses_esg:
        raise InvalidInputError(
            "Specify at least one ESG setting (minimum score, tilt, sector exclusion or "
            "exclusion of unscored assets) to measure its impact."
        )
    data = load(service, req.universe)
    est = estimates_for(service, data, req.estimation)
    meta = data.metadata()
    tickers = data.tickers
    base_cons, _ = build_constraints(_without_esg(req.constraints), data, tickers)
    esg_cons, unscored = build_constraints(req.constraints, data, tickers)
    base_req = opt_request(req.objective, req.estimation, base_cons)
    esg_req = opt_request(req.objective, req.estimation, esg_cons)
    base = optimise(est, base_req, meta)
    esg = optimise(est, esg_req, meta)
    base_out, _ = portfolio_result_out(base, est, base_req, data)
    esg_out, _ = portfolio_result_out(esg, est, esg_req, data)

    diff = esg.weights - base.weights
    te_ante = portfolio_volatility(diff, est.covariance)
    r_base = constant_mix_returns(data.returns, base.weights).to_numpy()
    r_esg = constant_mix_returns(data.returns, esg.weights).to_numpy()
    te_post = tracking_error(r_esg, r_base, data.periods_per_year)

    changes = []
    for i, t in enumerate(tickers):
        info = data.asset(t)
        if abs(base.weights[i]) < 1e-9 and abs(esg.weights[i]) < 1e-9:
            continue
        changes.append(
            s.WeightChangeOut(
                ticker=t,
                name=info.name,
                sector=info.sector,
                esg_score=info.esg.score if info.esg else None,
                baseline_weight=float(base.weights[i]),
                esg_weight=float(esg.weights[i]),
                change=float(diff[i]),
            )
        )
    changes.sort(key=lambda c: -abs(c.change))
    sec_b = {x.sector: x.weight for x in base_out.sector_exposures}
    sec_e = {x.sector: x.weight for x in esg_out.sector_exposures}
    sector_changes: list[dict[str, float | str]] = [
        {
            "sector": k,
            "baseline": sec_b.get(k, 0.0),
            "esg": sec_e.get(k, 0.0),
            "change": sec_e.get(k, 0.0) - sec_b.get(k, 0.0),
        }
        for k in sorted(set(sec_b) | set(sec_e))
    ]

    frontier: list[s.EsgFrontierPointOut] = []
    scored = [t for t in tickers if data.asset(t).esg is not None]
    if scored:
        # The ESG-efficient frontier needs scores for every investable asset.
        fr_cons, _ = build_constraints(
            _without_esg(req.constraints).model_copy(update={"exclude_unscored_assets": True}),
            data,
            tickers,
        )
        scores = [data.asset(t).esg.score for t in scored]  # type: ignore[union-attr]
        levels = req.esg_levels or [float(x) for x in np.linspace(min(scores), max(scores), 12)]
        for p in esg_sharpe_frontier(est, fr_cons, meta, req.estimation.risk_free_rate, levels):
            if p.feasible and p.result is not None:
                frontier.append(
                    s.EsgFrontierPointOut(
                        min_esg_score=p.min_esg_score,
                        feasible=True,
                        esg_score=_opt(p.result.esg_score),
                        expected_return=_finite(p.result.expected_return),
                        volatility=_finite(p.result.volatility),
                        sharpe_ratio=_opt(p.result.sharpe_ratio),
                    )
                )
            else:
                frontier.append(
                    s.EsgFrontierPointOut(
                        min_esg_score=p.min_esg_score, feasible=False, reason=p.reason
                    )
                )

    sources = sorted({a.esg.source for t in tickers if (a := data.asset(t)).esg})
    notes = [f"ESG scores source: {src}." for src in sources]
    if any(a.esg and a.esg.is_synthetic for t in tickers if (a := data.asset(t))):
        notes.append("These ESG scores are synthetic and illustrative; they are not real ratings.")
    notes.append(
        "ESG ratings differ materially between providers; conclusions depend on the rating source."
    )
    return s.EsgImpactResponse(
        baseline=base_out,
        esg=esg_out,
        delta_expected_return=_finite(esg.expected_return - base.expected_return),
        delta_volatility=_finite(esg.volatility - base.volatility),
        delta_sharpe_ratio=(
            None
            if esg.sharpe_ratio is None or base.sharpe_ratio is None
            else _finite(esg.sharpe_ratio - base.sharpe_ratio)
        ),
        delta_esg_score=(
            None
            if esg.esg_score is None or base.esg_score is None
            else _finite(esg.esg_score - base.esg_score)
        ),
        ex_ante_tracking_error=_finite(te_ante),
        ex_post_tracking_error=_finite(te_post),
        ex_post_tracking_error_note=(
            "Realised tracking error of the ESG portfolio against the baseline over the estimation "
            "window (in-sample; both portfolios rebalanced every period)."
        ),
        weight_changes=changes,
        sector_changes=sector_changes,
        esg_frontier=frontier,
        esg_data_notes=notes,
        estimation=estimation_out(est, req.estimation),
        data=data_window(data),
        excluded_unscored=unscored,
    )


# ----------------------------------------------------------------------------- Monte Carlo


def _pct_keys(d: Mapping[int, Any]) -> list[tuple[str, Any]]:
    return [(f"p{k:02d}", v) for k, v in sorted(d.items())]


def run_montecarlo(service: MarketDataService, req: s.MonteCarloRequest) -> s.MonteCarloResponse:
    data = load(service, req.universe)
    w = weight_vector(data.tickers, req.weights)
    seed = req.seed if req.seed is not None else secrets.randbelow(2**31)
    ppy = data.periods_per_year
    cfg = MonteCarloConfig(
        seed=seed,
        method=req.method,
        n_paths=req.n_paths,
        horizon_years=req.horizon_years,
        initial_value=req.initial_value,
        periods_per_year=ppy,
        periods_per_step=max(1, ppy // 12),
        mean_block_length=req.mean_block_length,
        target_value=req.target_value,
        annual_cash_flow=req.annual_cash_flow,
        cash_flows_per_year=req.cash_flows_per_year,
        cash_flow_growth=req.cash_flow_growth,
    )
    est = estimates_for(service, data, req.estimation)
    exp_ret = portfolio_expected_return(w, est.expected_returns)
    vol = portfolio_volatility(w, est.covariance)
    if req.method is SimulationMethod.PARAMETRIC:
        res: MonteCarloResult = simulate_parametric(cfg, exp_ret, vol)
    else:
        hist = constant_mix_returns(data.returns, w).to_numpy()
        res = simulate_bootstrap(cfg, hist)
    counts, edges = res.histogram(40)
    return s.MonteCarloResponse(
        method=req.method.value,
        seed=seed,
        n_paths=req.n_paths,
        horizon_years=req.horizon_years,
        initial_value=req.initial_value,
        times_years=[float(x) for x in res.times_years],
        percentiles={k: [_finite(float(x)) for x in v] for k, v in _pct_keys(res.percentile_paths)},
        mean_path=[_finite(float(x)) for x in res.mean_path],
        sample_paths=[[_finite(float(x)) for x in row] for row in res.sample_paths],
        terminal_histogram=s.HistogramOut(
            edges=[float(x) for x in edges], counts=[int(c) for c in counts]
        ),
        terminal_percentiles={k: _finite(float(v)) for k, v in _pct_keys(res.terminal_percentiles)},
        probability_of_loss=res.probability_of_loss,
        probability_of_target=res.probability_of_target,
        target_value=req.target_value,
        terminal_return_var_95=_finite(res.terminal_return_var_95),
        terminal_return_cvar_95=_finite(res.terminal_return_cvar_95),
        cagr_percentiles={k: _finite(float(v)) for k, v in _pct_keys(res.cagr_percentiles)},
        max_drawdown_percentiles={
            k: _finite(float(v)) for k, v in _pct_keys(res.max_drawdown_percentiles)
        },
        portfolio_expected_return=_finite(exp_ret),
        portfolio_volatility=_finite(vol),
        net_cash_flow=_finite(res.net_cash_flow),
        probability_of_depletion=res.probability_of_depletion,
        depletion_years_percentiles=(
            None
            if res.depletion_years_percentiles is None
            else {k: float(v) for k, v in _pct_keys(res.depletion_years_percentiles)}
        ),
        assumptions=list(res.assumptions),
        data=data_window(data),
    )


# ----------------------------------------------------------------------------- backtest


def _strategy(
    service: MarketDataService, req: s.BacktestRequest, data: LoadedData, tickers: Sequence[str]
) -> Strategy:
    st = req.strategy
    if isinstance(st, s.EqualWeightStrategyIn):
        return EqualWeightStrategy()
    if isinstance(st, s.FixedStrategyIn):
        return FixedWeightStrategy(tuple(weight_vector(tickers, st.weights)), name="Fixed weights")
    cons, _ = build_constraints(st.constraints, data, tickers)
    oreq = opt_request(st.objective, req.estimation, cons)
    label = st.objective.objective.value.replace("_", " ")
    return OptimisedStrategy(
        oreq,
        data.metadata(),
        req.estimation.mean_estimator,
        req.estimation.covariance_estimator,
        name=f"Optimised ({label})",
        black_litterman_spec=black_litterman_spec(service, data, req.estimation, tickers),
    )


def _series(name: str, r: BacktestResult) -> s.SeriesOut:
    return s.SeriesOut(
        name=name,
        wealth=[_finite(float(x)) for x in r.wealth],
        drawdown=[_finite(float(x)) for x in drawdown_series(r.returns)],
    )


def run_backtest_service(service: MarketDataService, req: s.BacktestRequest) -> s.BacktestResponse:
    bench = req.benchmark
    extra = [bench.ticker] if bench is not None and bench.type == "asset" and bench.ticker else []
    data = load(service, req.universe, extra)
    tickers = list(req.universe.tickers)
    ppy = data.periods_per_year
    lookback = max(2, round(req.lookback_years * ppy))
    cfg = BacktestConfig(
        lookback_periods=lookback,
        rebalance=req.rebalance,
        transaction_cost_bps=req.transaction_cost_bps,
        risk_free_rate=req.estimation.risk_free_rate,
        periods_per_year=ppy,
    )
    rets = data.returns[tickers]
    result = run_backtest(rets, _strategy(service, req, data, tickers), cfg)

    b_res: BacktestResult | None = None
    if bench is not None:
        if bench.type == "equal_weight":
            b_res = run_backtest(rets, EqualWeightStrategy(name="Equal-weight benchmark"), cfg)
        else:
            assert bench.ticker is not None
            b_res = run_backtest(
                data.returns[[bench.ticker]], FixedWeightStrategy((1.0,), name=bench.ticker), cfg
            )
        if len(b_res.returns) != len(result.returns):  # pragma: no cover - same schedule
            raise InvalidInputError("Benchmark and strategy evaluation periods do not align.")
    perf = performance_summary(
        result.returns, ppy, req.estimation.risk_free_rate, None if b_res is None else b_res.returns
    )

    # Attribution: per-asset gross contributions plus a trading-cost line, Carino-linked
    # so that the contributions sum exactly to the strategy's compounded net return.
    x = rets.loc[result.dates].to_numpy()
    contrib = contributions(result.start_weights, x)
    cost_line = (result.returns - result.gross_returns)[:, None]
    linked = carino_link(np.hstack([contrib, cost_line]), result.returns)
    asset_contrib = [
        s.ContributionOut(name=t, contribution=_finite(float(v)))
        for t, v in zip(tickers, linked[:-1], strict=True)
    ]
    asset_contrib.append(
        s.ContributionOut(name="Transaction costs", contribution=_finite(float(linked[-1])))
    )
    by_sector: dict[str, float] = {}
    for t, v in zip(tickers, linked[:-1], strict=True):
        key = data.asset(t).sector or "Unclassified"
        by_sector[key] = by_sector.get(key, 0.0) + float(v)
    sector_contrib = [
        s.ContributionOut(name=k, contribution=v)
        for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])
    ]

    brinson = None
    if b_res is not None and bench is not None and bench.type == "equal_weight":
        sectors = {t: sec for t in tickers if (sec := data.asset(t).sector)}
        if len(sectors) == len(tickers):
            bf = brinson_fachler(tickers, sectors, result.start_weights, b_res.start_weights, x)
            brinson = [
                s.BrinsonOut(
                    sector=sec,
                    allocation=float(bf.allocation[i]),
                    selection=float(bf.selection[i]),
                    interaction=float(bf.interaction[i]),
                    total=float(bf.allocation[i] + bf.selection[i] + bf.interaction[i]),
                    portfolio_weight=float(bf.portfolio_weights[i]),
                    benchmark_weight=float(bf.benchmark_weights[i]),
                )
                for i, sec in enumerate(bf.sectors)
            ]

    assumptions = [
        f"Walk-forward: at each {req.rebalance.value} rebalance the strategy sees only the trailing "
        f"{lookback} {data.frequency.value} returns ({req.lookback_years:g} years) up to that date.",
        "Trades execute at the rebalance date's closing price; weights drift between rebalances.",
        f"Transaction costs: {req.transaction_cost_bps:g} bps of traded value (including the initial purchase).",
        "Performance is measured only after the first rebalance (the evaluation period).",
        "Gross attribution uses start-of-period weights; effects are linked with Carino (1999).",
        "Survivorship bias: the asset list is chosen today, which can flatter historical results.",
        "No taxes, market impact beyond linear costs, or cash holdings.",
    ]
    return s.BacktestResponse(
        strategy=result.strategy,
        dates=[d.date() for d in result.dates],
        wealth_dates=[result.events[0].date, *(d.date() for d in result.dates)],
        portfolio=_series(result.strategy, result),
        benchmark=None if b_res is None else _series(b_res.strategy, b_res),
        performance=performance_out(perf),
        benchmark_performance=(
            None
            if b_res is None
            else performance_out(
                performance_summary(b_res.returns, ppy, req.estimation.risk_free_rate)
            )
        ),
        estimation_start=result.estimation_start,
        evaluation_start=result.evaluation_start,
        evaluation_end=result.evaluation_end,
        lookback_periods=lookback,
        rebalance=req.rebalance.value,
        transaction_cost_bps=req.transaction_cost_bps,
        total_cost=_finite(result.total_cost),
        annualised_turnover=_finite(result.annualised_turnover),
        events=[
            s.RebalanceEventOut(
                date=e.date,
                status=e.status,
                turnover=_finite(e.turnover),
                cost=_finite(e.cost),
                estimation_start=e.estimation_start,
                estimation_end=e.estimation_end,
                weights={t: float(v) for t, v in zip(tickers, e.weights_after, strict=True)},
                message=e.message,
            )
            for e in result.events
        ],
        asset_contributions=asset_contrib,
        sector_contributions=sector_contrib,
        brinson=brinson,
        assumptions=assumptions,
        data=data_window(data),
    )


# ----------------------------------------------------------------------------- compare


def run_compare(service: MarketDataService, req: s.CompareRequest) -> s.CompareResponse:
    data = load(service, req.universe)
    tickers = list(data.tickers)
    est = estimates_for(service, data, req.estimation)
    ppy = data.periods_per_year
    cfg = BacktestConfig(
        lookback_periods=2,
        rebalance=req.rebalance,
        transaction_cost_bps=req.transaction_cost_bps,
        risk_free_rate=req.estimation.risk_free_rate,
        periods_per_year=ppy,
    )
    rf_a = est.risk_free_arithmetic(req.estimation.risk_free_rate)
    names = [p.name for p in req.portfolios]
    if len(set(names)) != len(names):
        raise InvalidInputError("Portfolio names must be unique.")
    out: list[s.ComparedPortfolioOut] = []
    series: list[np.ndarray] = []
    dates: pd.DatetimeIndex | None = None
    start_date = None
    for p in req.portfolios:
        w = weight_vector(tickers, p.weights)
        exp_r = portfolio_expected_return(w, est.expected_returns)
        vol = portfolio_volatility(w, est.covariance)
        esg_vals = [data.asset(t).esg for t in tickers]
        held = [i for i in range(len(tickers)) if abs(w[i]) > 1e-9]
        esg = (
            float(sum(w[i] * esg_vals[i].score for i in held))  # type: ignore[union-attr]
            if held and all(esg_vals[i] is not None for i in held) and (w >= -1e-12).all()
            else None
        )
        try:
            rd = risk_decomposition(w, est.covariance)
            order = np.argsort(-rd.percent_contribution)[:3]
            top = [
                s.ContributionOut(name=tickers[i], contribution=float(rd.percent_contribution[i]))
                for i in order
            ]
        except Exception:
            top = []
        bt = run_backtest(data.returns, FixedWeightStrategy(tuple(w), name=p.name), cfg)
        dates = bt.dates
        start_date = bt.events[0].date
        series.append(bt.returns)
        out.append(
            s.ComparedPortfolioOut(
                name=p.name,
                weights={t: float(x) for t, x in zip(tickers, w, strict=True) if abs(x) > 1e-12},
                expected_return=_finite(exp_r),
                volatility=_finite(vol),
                sharpe_ratio=None if vol < 1e-12 else _finite((exp_r - rf_a) / vol),
                esg_score=esg,
                effective_number_of_assets=_finite(effective_number_of_assets(np.clip(w, 0, None)))
                if (w > 0).any()
                else 0.0,
                top_risk_contributors=top,
                historical=performance_out(bt.summary),
                wealth=[_finite(float(x)) for x in bt.wealth],
                drawdown=[_finite(float(x)) for x in drawdown_series(bt.returns)],
            )
        )
    assert dates is not None
    assert start_date is not None
    mat = np.vstack(series)
    corr = np.corrcoef(mat) if (mat.std(axis=1) > 0).all() else np.eye(len(series))
    return s.CompareResponse(
        portfolios=out,
        dates=[d.date() for d in dates],
        wealth_dates=[start_date, *(d.date() for d in dates)],
        return_correlation=[[_finite(float(x)) for x in row] for row in np.atleast_2d(corr)],
        in_sample_warning=(
            "Historical results replay fixed weights over the same window used to estimate "
            "returns and risk. If any of these weights were optimised on this window, their "
            "historical performance is in-sample and overstates what could have been achieved; "
            "use the walk-forward backtest for an out-of-sample evaluation."
        ),
        estimation=estimation_out(est, req.estimation),
        data=data_window(data),
    )
