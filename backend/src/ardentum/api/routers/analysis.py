"""Computation endpoints. All are stateless and deterministic given their inputs
(and the seed, for simulations)."""

from __future__ import annotations

from fastapi import APIRouter

from ardentum.api import schemas as s
from ardentum.api.deps import MarketService
from ardentum.services import analysis, risk_free

router = APIRouter(tags=["analysis"])


@router.post("/analytics", response_model=s.AnalyticsResponse)
def analytics(req: s.AnalyticsRequest, service: MarketService) -> s.AnalyticsResponse:
    """Per-asset historical statistics, correlation and covariance."""
    return analysis.asset_analytics(service, req)


@router.post("/optimise", response_model=s.OptimiseResponse)
def optimise(req: s.OptimiseRequest, service: MarketService) -> s.OptimiseResponse:
    """Constrained mean-variance optimisation with explanation."""
    return analysis.run_optimise(service, req)


@router.post("/frontier", response_model=s.FrontierResponse)
def frontier(req: s.FrontierRequest, service: MarketService) -> s.FrontierResponse:
    """Constrained efficient frontier (optionally against the unconstrained frontier)."""
    return analysis.run_frontier(service, req)


@router.post("/esg/impact", response_model=s.EsgImpactResponse)
def esg_impact(req: s.EsgImpactRequest, service: MarketService) -> s.EsgImpactResponse:
    """Effect of ESG constraints on return, risk, Sharpe ratio and composition."""
    return analysis.run_esg_impact(service, req)


@router.post("/montecarlo", response_model=s.MonteCarloResponse)
def montecarlo(req: s.MonteCarloRequest, service: MarketService) -> s.MonteCarloResponse:
    """Seeded Monte Carlo simulation of portfolio wealth."""
    return analysis.run_montecarlo(service, req)


@router.post("/backtest", response_model=s.BacktestResponse)
def backtest(req: s.BacktestRequest, service: MarketService) -> s.BacktestResponse:
    """Walk-forward backtest with attribution."""
    return analysis.run_backtest_service(service, req)


@router.post("/compare", response_model=s.CompareResponse)
def compare(req: s.CompareRequest, service: MarketService) -> s.CompareResponse:
    """Side-by-side comparison of fixed-weight portfolios."""
    return analysis.run_compare(service, req)


def _source_out(info: risk_free.SourceInfo, available: bool) -> s.RiskFreeSourceOut:
    return s.RiskFreeSourceOut(
        id=info.id,
        name=info.name,
        description=info.description,
        citation=info.citation,
        available=available,
    )


@router.get("/risk-free/sources", response_model=list[s.RiskFreeSourceOut])
def risk_free_sources(service: MarketService) -> list[s.RiskFreeSourceOut]:
    """Free public sources for the risk-free rate and whether this server can use them."""
    avail = risk_free.available(service)
    return [_source_out(i, avail[k]) for k, i in risk_free.SOURCES.items()]


@router.post("/risk-free", response_model=s.RiskFreeOut)
def risk_free_rate(req: s.RiskFreeRequest, service: MarketService) -> s.RiskFreeOut:
    """Effective annual risk-free rate over a window from a public source."""
    est = risk_free.estimate(service, req.source, req.start, req.end)
    return s.RiskFreeOut(
        source=_source_out(est.source, True),
        rate=est.rate,
        label=est.label,
        start=est.start,
        end=est.end,
        observations=est.observations,
        retrieved_at=est.retrieved_at,
        stale=est.stale,
    )
