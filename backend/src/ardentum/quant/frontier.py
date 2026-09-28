"""Efficient frontier and ESG-efficient frontier.

The (constrained) efficient frontier is traced by solving
``min w' S w  s.t.  mu' w >= m`` over a grid of target returns ``m`` from the
minimum-volatility portfolio's return up to the maximum achievable return under
the same constraints. Only the efficient (upper) branch is produced; portfolios
below the minimum-volatility return are dominated.

The ESG-efficient frontier (Pedersen, Fitzgibbons & Pomorski 2021) shows the
highest attainable ex-ante Sharpe ratio as a function of the minimum portfolio
ESG score, making the financial cost of an ESG requirement explicit.

The mean-CVaR frontier replaces variance by historical conditional value at risk
(expected shortfall), the average loss in the worst ``1 - beta`` of the estimation
window's periods, and is traced with the Rockafellar-Uryasev linear programme.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cvxpy as cp
import numpy as np

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError, QuantError
from ardentum.quant.esg import portfolio_esg_score
from ardentum.quant.estimation import MarketEstimates
from ardentum.quant.metrics import historical_var_cvar
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
    cvar_tail_warning,
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
        estimates,
        OptimisationRequest(Objective.MIN_VOLATILITY, risk_free_rate, constraints=constraints),
        meta,
    )
    max_sharpe: OptimisationResult | None = None
    reason: str | None = None
    try:
        max_sharpe = optimise(
            estimates,
            OptimisationRequest(
                Objective.MAX_SHARPE, risk_free_rate, constraints=replace(constraints, esg_tilt=0.0)
            ),
            meta,
        )
    except InfeasibleProblemError as exc:
        reason = str(exc)

    r_lo = min_vol.expected_return
    r_hi, _ = _max_return(comp, comp.mu)
    targets: list[float] = (
        [r_lo] if r_hi - r_lo < 1e-9 else [float(x) for x in np.linspace(r_lo, r_hi, n_points)]
    )
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
class CvarFrontierPoint:
    expected_return: float
    volatility: float
    var: float  # one-period historical VaR (loss, positive)
    cvar: float  # one-period historical CVaR (loss, positive)
    sharpe_ratio: float | None
    esg_score: float | None
    weights: np.ndarray


@dataclass(frozen=True)
class MeanCvarFrontier:
    tickers: tuple[str, ...]
    points: tuple[CvarFrontierPoint, ...]
    min_cvar: OptimisationResult
    confidence: float
    periods_per_year: int
    observations: int
    risk_free_rate: float
    asset_expected_returns: np.ndarray
    asset_var: np.ndarray
    asset_cvar: np.ndarray
    warnings: tuple[str, ...] = ()


def portfolio_var_cvar(
    estimates: MarketEstimates, weights: np.ndarray, confidence: float
) -> tuple[float, float]:
    """One-period historical VaR and CVaR (losses, positive) of fixed weights over the
    estimation window's scenarios."""
    if estimates.scenarios is None:
        raise InvalidInputError("VaR and CVaR need the historical return scenarios.")
    return historical_var_cvar(-(estimates.scenarios @ np.asarray(weights)), confidence)


def mean_cvar_frontier(
    estimates: MarketEstimates,
    constraints: PortfolioConstraints,
    risk_free_rate: float = 0.0,
    metadata: AssetMetadata | None = None,
    n_points: int = 30,
    confidence: float = 0.95,
) -> MeanCvarFrontier:
    """Trace the mean-CVaR efficient frontier (Rockafellar & Uryasev 2000, 2002).

    For each target ``m`` between the minimum-CVaR portfolio's expected return and the
    highest attainable return, solve the linear programme

        min_{w, a, u}  a + sum(u) / ((1 - beta) T)
        s.t.           u >= -R w - a,  u >= 0,  mu' w >= m,  w in constraints

    over the ``T`` historical return scenarios ``R`` of the estimation window. The optimum
    equals the historical CVaR of ``w`` at confidence ``beta``; it is one-period (daily,
    weekly or monthly, like the data) and is not annualised, because tail losses do not
    scale with the square root of time. Only the efficient branch is produced.
    """
    if not 2 <= n_points <= MAX_FRONTIER_POINTS:
        raise InvalidInputError(f"Number of frontier points must be in [2, {MAX_FRONTIER_POINTS}].")
    meta = metadata or AssetMetadata()
    warnings: list[str] = []
    if constraints.esg_tilt > 0:
        warnings.append(
            "The ESG preference tilt does not change the frontier, which is defined by "
            "unadjusted expected returns; ESG constraints (minimum score, exclusions) do apply."
        )
    # The tilt only changes preference-adjusted returns, which this frontier does not use.
    untilted = replace(constraints, esg_tilt=0.0)
    # The minimum-CVaR optimisation validates the confidence level and the window length.
    min_cvar = optimise(
        estimates,
        OptimisationRequest(
            Objective.MIN_CVAR, risk_free_rate, constraints=untilted, cvar_confidence=confidence
        ),
        meta,
    )
    comp = _compile(estimates, untilted, meta, require_esg_scores=False)
    scen = comp.scenarios
    if scen is None:  # pragma: no cover - optimise() above already requires scenarios
        raise InvalidInputError("The mean-CVaR frontier needs the historical return scenarios.")
    rf_arith = estimates.risk_free_arithmetic(risk_free_rate)

    r_lo = min_cvar.expected_return
    r_hi, _ = _max_return(comp, comp.mu)
    targets: list[float] = (
        [r_lo] if r_hi - r_lo < 1e-9 else [float(x) for x in np.linspace(r_lo, r_hi, n_points)]
    )
    if len(targets) > 1:
        targets[-1] = r_hi - 1e-7 * max(r_hi - r_lo, 1e-6)

    t_obs = scen.shape[0]
    if tail_note := cvar_tail_warning(confidence, t_obs):
        warnings.append(tail_note)
    w = cp.Variable(comp.n)
    alpha = cp.Variable()
    u = cp.Variable(t_obs, nonneg=True)
    t = cp.Parameter()
    cons, _ = comp.cvx_constraints(w)
    prob = cp.Problem(
        cp.Minimize(alpha + cp.sum(u) / ((1.0 - confidence) * t_obs)),
        [*cons, u >= -scen @ w - alpha, comp.mu @ w >= t],
    )

    points: list[CvarFrontierPoint] = []
    for target in targets:
        t.value = float(target)
        try:
            _solve(prob, "mean-CVaR frontier")
            raw = np.asarray(w.value)
            wv = _finalise(comp, raw, [("target return", float(comp.mu @ raw) >= target - 1e-6)])
        except QuantError:
            warnings.append(f"Frontier point at target return {target:.2%} could not be solved.")
            continue
        var, cvar = historical_var_cvar(-(scen @ wv), confidence)
        base = _point(comp.mu, comp.cov, comp.esg_scores, wv, rf_arith)
        points.append(
            CvarFrontierPoint(
                expected_return=base.expected_return,
                volatility=base.volatility,
                var=var,
                cvar=cvar,
                sharpe_ratio=base.sharpe_ratio,
                esg_score=base.esg_score,
                weights=wv,
            )
        )

    if not points:
        raise InfeasibleProblemError("No point on the mean-CVaR frontier could be computed.")
    asset_risk = np.array([historical_var_cvar(-scen[:, i], confidence) for i in range(comp.n)])
    return MeanCvarFrontier(
        tickers=estimates.tickers,
        points=tuple(points),
        min_cvar=min_cvar,
        confidence=confidence,
        periods_per_year=estimates.periods_per_year,
        observations=t_obs,
        risk_free_rate=risk_free_rate,
        asset_expected_returns=comp.mu.copy(),
        asset_var=asset_risk[:, 0],
        asset_cvar=asset_risk[:, 1],
        warnings=tuple(warnings),
    )


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
                estimates,
                OptimisationRequest(Objective.MAX_SHARPE, risk_free_rate, constraints=cons),
                metadata,
            )
            out.append(EsgFrontierPoint(float(level), True, res))
        except InfeasibleProblemError as exc:
            out.append(EsgFrontierPoint(float(level), False, None, str(exc)))
    return tuple(out)
