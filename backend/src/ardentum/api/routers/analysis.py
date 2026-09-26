"""Computation endpoints. All are stateless and deterministic given their inputs
(and the seed, for simulations)."""

from __future__ import annotations

from fastapi import APIRouter

from ardentum.api import schemas as s
from ardentum.api.deps import MarketService
from ardentum.services import analysis

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
