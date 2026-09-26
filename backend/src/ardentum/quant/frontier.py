"""Efficient frontier and ESG-efficient frontier.

The (constrained) efficient frontier is traced by solving
``min w' S w  s.t.  mu' w >= m`` over a grid of target returns ``m`` from the
minimum-volatility portfolio's return up to the maximum achievable return under
the same constraints. Only the efficient (upper) branch is produced; portfolios
below the minimum-volatility return are dominated.

The ESG-efficient frontier (Pedersen, Fitzgibbons & Pomorski 2021) shows the
highest attainable ex-ante Sharpe ratio as a function of the minimum portfolio
ESG score, making the financial cost of an ESG requirement explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cvxpy as cp
import numpy as np

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError, QuantError
from ardentum.quant.esg import portfolio_esg_score
from ardentum.quant.estimation import MarketEstimates
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    OptimisationResult,
    PortfolioConstraints,
    _compile,
    _finalise,
    _max_return,
    _solve,
    _variance,
    optimise,
)
from ardentum.quant.portfolio import portfolio_volatility

MAX_FRONTIER_POINTS = 200


@dataclass(frozen=True)
class FrontierPoint:
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    esg_score: float | None
    weights: np.ndarray


@dataclass(frozen=True)
class EfficientFrontier:
    tickers: tuple[str, ...]
    points: tuple[FrontierPoint, ...]
    min_volatility: OptimisationResult
    max_sharpe: OptimisationResult | None
    max_sharpe_unavailable_reason: str | None
    risk_free_rate: float
    asset_expected_returns: np.ndarray
    asset_volatilities: np.ndarray
    warnings: tuple[str, ...] = ()


def efficient_frontier(
    estimates: MarketEstimates,
    constraints: PortfolioConstraints,
    risk_free_rate: float = 0.0,
    metadata: AssetMetadata | None = None,
    n_points: int = 40,
) -> EfficientFrontier:
    """Trace the constrained efficient frontier with ``n_points`` target returns."""
    if not 2 <= n_points <= MAX_FRONTIER_POINTS:
        raise InvalidInputError(f"Number of frontier points must be in [2, {MAX_FRONTIER_POINTS}].")
    meta = metadata or AssetMetadata()
    warnings: list[str] = []
    if constraints.esg_tilt > 0:
        warnings.append(
            "The ESG preference tilt does not change the frontier, which is defined by "
            "unadjusted expected returns; ESG constraints (minimum score, exclusions) do apply."
        )
    comp = _compile(estimates, constraints, meta, require_esg_scores=False)
    rf_arith = estimates.risk_free_arithmetic(risk_free_rate)

    min_vol = optimise(
        estimates, OptimisationRequest(Objective.MIN_VOLATILITY, risk_free_rate, constraints=constraints), meta
    )
    max_sharpe: OptimisationResult | None = None
    reason: str | None = None
    try:
        max_sharpe = optimise(
            estimates, OptimisationRequest(Objective.MAX_SHARPE, risk_free_rate, constraints=replace(constraints, esg_tilt=0.0)), meta
        )
    except InfeasibleProblemError as exc:
        reason = str(exc)

    r_lo = min_vol.expected_return
    r_hi, _ = _max_return(comp, comp.mu)
    targets = [r_lo] if r_hi - r_lo < 1e-9 else list(np.linspace(r_lo, r_hi, n_points))
    if len(targets) > 1:
        # The last target admits a single portfolio; back off by a negligible amount
        # so the interior-point solver has a strictly feasible region.
        targets[-1] = r_hi - 1e-7 * max(r_hi - r_lo, 1e-6)

    w = cp.Variable(comp.n)
    t = cp.Parameter()
    cons, _ = comp.cvx_constraints(w)
    prob = cp.Problem(cp.Minimize(_variance(comp, w)), [*cons, comp.mu @ w >= t])

    points: list[FrontierPoint] = []
    for target in targets:
        t.value = float(target)
        try:
            _solve(prob, "efficient-frontier")
            wv = _finalise(comp, np.asarray(w.value), [])
        except QuantError:
            warnings.append(f"Frontier point at target return {target:.2%} could not be solved.")
            continue
        points.append(_point(comp.mu, comp.cov, comp.esg_scores, wv, rf_arith))

    if not points:
        raise InfeasibleProblemError("No point on the efficient frontier could be computed.")
    return EfficientFrontier(
        tickers=estimates.tickers,
        points=tuple(points),
        min_volatility=min_vol,
        max_sharpe=max_sharpe,
        max_sharpe_unavailable_reason=reason,
        risk_free_rate=risk_free_rate,
        asset_expected_returns=comp.mu.copy(),
        asset_volatilities=np.sqrt(np.clip(np.diag(comp.cov), 0.0, None)),
        warnings=tuple(warnings),
    )


def _point(
    mu: np.ndarray, cov: np.ndarray, esg: np.ndarray | None, w: np.ndarray, rf_arith: float
) -> FrontierPoint:
    ret = float(w @ mu)
    vol = portfolio_volatility(w, cov)
    score: float | None = None
    if esg is not None and (w >= -1e-12).all():
        held = w > 1e-8
        if not np.isnan(esg[held]).any():
            score = portfolio_esg_score(np.where(held, w, 0.0), np.nan_to_num(esg, nan=0.0))
    return FrontierPoint(ret, vol, None if vol < 1e-12 else (ret - rf_arith) / vol, score, w)


@dataclass(frozen=True)
class EsgFrontierPoint:
    min_esg_score: float
    feasible: bool
    result: OptimisationResult | None
    reason: str | None = None


def esg_sharpe_frontier(
    estimates: MarketEstimates,
    constraints: PortfolioConstraints,
    metadata: AssetMetadata,
    risk_free_rate: float,
    levels: list[float],
) -> tuple[EsgFrontierPoint, ...]:
    """Maximum-Sharpe portfolio for each minimum-ESG level (ESG-efficient frontier)."""
    if not levels:
        raise InvalidInputError("At least one ESG level is required.")
    out: list[EsgFrontierPoint] = []
    for level in sorted(levels):
        cons = replace(constraints, min_esg_score=float(level), esg_tilt=0.0)
        try:
            res = optimise(
                estimates, OptimisationRequest(Objective.MAX_SHARPE, risk_free_rate, constraints=cons), metadata
            )
            out.append(EsgFrontierPoint(float(level), True, res))
        except InfeasibleProblemError as exc:
            out.append(EsgFrontierPoint(float(level), False, None, str(exc)))
    return tuple(out)
