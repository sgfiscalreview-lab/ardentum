"""Mean-variance portfolio optimisation (Markowitz 1952) with explicit constraints.

All problems are convex and solved with CVXPY (default solver: Clarabel, an
interior-point conic solver; SCS as fallback). The covariance matrix enters via a
factor ``F`` with ``F'F = Sigma`` built from its eigen-decomposition, so variance
is ``||F w||^2``; this is numerically robust for singular (PSD) matrices.

Objectives
----------
* ``min_volatility``    minimise ``w' S w``.
* ``max_sharpe``        maximise ``(mu' w - rf) / sqrt(w' S w)``. Not convex as stated;
  solved exactly via the Charnes-Cooper / Cornuejols-Tutuncu homogenisation
  ``min y' S y  s.t. (mu - rf)' y = 1,  A y <= b k,  k >= 0`` with ``w = y / k``.
  Requires at least one feasible portfolio with expected return above ``rf``.
* ``target_return``     minimise ``w' S w`` s.t. ``mu' w >= target``.
* ``target_volatility`` maximise ``mu' w`` s.t. ``sqrt(w' S w) <= target``.
* ``max_utility``       maximise ``mu' w - (gamma / 2) w' S w``.

Constraints: full investment (``sum w = 1``), per-asset bounds, excluded assets
and sectors (weight fixed at zero), sector minimum/maximum exposure, minimum
portfolio ESG score, maximum gross exposure (``sum |w|``) and maximum ex-ante
tracking error against a benchmark weight vector.

ESG preference (tilt) replaces ``mu`` by the ESG-adjusted ``mu + tau z`` in the
objective of ``max_sharpe``, ``target_volatility`` and ``max_utility``.
``min_volatility`` and ``target_return`` have no return term in the objective,
so the tilt does not apply to them (use the minimum-ESG constraint instead);
the result carries a warning saying so. Reported returns are always unadjusted.

Every solution is verified against every constraint after solving; a solution
that violates any constraint by more than ``VERIFY_TOL`` is rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Literal

import cvxpy as cp
import numpy as np

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError, SolverError
from ardentum.quant.esg import (
    esg_adjusted_returns,
    portfolio_esg_score,
    score_vector,
)
from ardentum.quant.estimation import MarketEstimates
from ardentum.quant.metrics import historical_var_cvar
from ardentum.quant.portfolio import portfolio_volatility, validate_covariance

VERIFY_TOL = 1e-6
ZERO_WEIGHT_TOL = 1e-8
MAX_ABS_WEIGHT = 5.0


class Objective(StrEnum):
    MIN_VOLATILITY = "min_volatility"
    MAX_SHARPE = "max_sharpe"
    TARGET_RETURN = "target_return"
    TARGET_VOLATILITY = "target_volatility"
    MAX_UTILITY = "max_utility"
    MIN_CVAR = "min_cvar"


TILT_OBJECTIVES = frozenset(
    {Objective.MAX_SHARPE, Objective.TARGET_VOLATILITY, Objective.MAX_UTILITY}
)


@dataclass(frozen=True)
class SectorLimit:
    sector: str
    min_weight: float | None = None
    max_weight: float | None = None


@dataclass(frozen=True)
class PortfolioConstraints:
    """Declarative constraint set; see module docstring for semantics."""

    min_weight: float = 0.0
    max_weight: float = 1.0
    asset_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    sector_limits: tuple[SectorLimit, ...] = ()
    excluded_assets: frozenset[str] = frozenset()
    excluded_sectors: frozenset[str] = frozenset()
    min_esg_score: float | None = None
    esg_tilt: float = 0.0
    max_gross_exposure: float | None = None
    benchmark_weights: Mapping[str, float] | None = None
    max_tracking_error: float | None = None

    @property
    def uses_esg(self) -> bool:
        return self.min_esg_score is not None or self.esg_tilt > 0.0

    def without_esg(self) -> PortfolioConstraints:
        """The same constraints with every ESG-motivated element removed."""
        return replace(self, min_esg_score=None, esg_tilt=0.0, excluded_sectors=frozenset())


@dataclass(frozen=True)
class AssetMetadata:
    """Per-asset attributes needed by sector and ESG constraints."""

    sectors: Mapping[str, str] = field(default_factory=dict)
    esg_scores: Mapping[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class OptimisationRequest:
    objective: Objective
    risk_free_rate: float = 0.0  # effective annual rate
    target_return: float | None = None
    target_volatility: float | None = None
    risk_aversion: float | None = None
    constraints: PortfolioConstraints = field(default_factory=PortfolioConstraints)
    cvar_confidence: float = 0.95  # for MIN_CVAR and for the reported historical CVaR


ConstraintKind = Literal[
    "budget",
    "asset_upper",
    "asset_lower",
    "excluded",
    "sector_max",
    "sector_min",
    "min_esg",
    "target_return",
    "target_volatility",
    "gross_exposure",
    "tracking_error",
]


@dataclass(frozen=True)
class ConstraintDiagnostic:
    kind: ConstraintKind
    label: str
    value: float
    bound: float
    binding: bool
    assets: tuple[str, ...] = ()
    shadow_price: float | None = None
    shadow_price_unit: str | None = None


@dataclass(frozen=True)
class OptimisationResult:
    tickers: tuple[str, ...]
    weights: np.ndarray
    objective: Objective
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    risk_free_rate: float
    esg_score: float | None
    esg_adjusted_return: float | None
    diagnostics: tuple[ConstraintDiagnostic, ...]
    solver: str
    warnings: tuple[str, ...] = ()
    # Historical one-period VaR/CVaR of the weights over the estimation window (losses > 0).
    var: float | None = None
    cvar: float | None = None
    cvar_confidence: float | None = None

    def weight_map(self) -> dict[str, float]:
        return dict(zip(self.tickers, (float(x) for x in self.weights), strict=True))


# --------------------------------------------------------------------------- compile


@dataclass(frozen=True)
class _Row:
    coeffs: np.ndarray
    sense: Literal["le", "ge", "eq"]
    bound: float
    kind: ConstraintKind
    label: str
    assets: tuple[str, ...]


@dataclass
class _Compiled:
    tickers: tuple[str, ...]
    mu: np.ndarray
    factor: np.ndarray
    cov: np.ndarray
    lb: np.ndarray
    ub: np.ndarray
    excluded: frozenset[int]
    rows: list[_Row]
    gross: float | None
    benchmark: np.ndarray | None
    max_te: float | None
    esg_scores: np.ndarray | None  # aligned; NaN where unavailable and unused
    scenarios: np.ndarray | None = None

    @property
    def n(self) -> int:
        return len(self.tickers)

    def cvx_constraints(
        self, w: cp.Variable, kappa: cp.Variable | None = None
    ) -> tuple[list[cp.Constraint], list[tuple[cp.Constraint, _Row | str]]]:
        """Build constraints; with ``kappa`` every constant is scaled (homogenised)."""
        k = 1.0 if kappa is None else kappa
        cons: list[cp.Constraint] = []
        tagged: list[tuple[cp.Constraint, _Row | str]] = []
        for row in self.rows:
            expr = row.coeffs @ w
            if row.sense == "le":
                c = expr <= row.bound * k
            elif row.sense == "ge":
                c = expr >= row.bound * k
            else:
                c = expr == row.bound * k
            cons.append(c)
            tagged.append((c, row))
        c_lb = w >= self.lb * k
        c_ub = w <= self.ub * k
        cons += [c_lb, c_ub]
        tagged += [(c_lb, "lb"), (c_ub, "ub")]
        if self.gross is not None:
            c = cp.norm1(w) <= self.gross * k
            cons.append(c)
            tagged.append((c, "gross"))
        if self.benchmark is not None and self.max_te is not None:
            c = cp.norm(self.factor @ (w - self.benchmark * k), 2) <= self.max_te * k
            cons.append(c)
            tagged.append((c, "te"))
        if kappa is not None:
            cons.append(kappa >= 0)
        return cons, tagged


def _covariance_factor(cov: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(cov)
    vals = np.clip(vals, 0.0, None)
    return np.asarray(np.sqrt(vals)[:, None] * vecs.T)


def _compile(
    estimates: MarketEstimates,
    constraints: PortfolioConstraints,
    metadata: AssetMetadata,
    *,
    require_esg_scores: bool,
) -> _Compiled:
    tickers = estimates.tickers
    n = len(tickers)
    if n == 0:
        raise InvalidInputError("At least one asset is required.")
    mu = np.asarray(estimates.expected_returns, dtype=float)
    if mu.shape != (n,) or not np.isfinite(mu).all():
        raise InvalidInputError("Expected returns must be finite and match the asset list.")
    cov = validate_covariance(estimates.covariance)
    if cov.shape != (n, n):
        raise InvalidInputError("Covariance dimensions do not match the asset list.")

    c = constraints
    if not -MAX_ABS_WEIGHT <= c.min_weight <= c.max_weight <= MAX_ABS_WEIGHT:
        raise InvalidInputError(
            f"Weight bounds must satisfy -{MAX_ABS_WEIGHT} <= min <= max <= {MAX_ABS_WEIGHT}."
        )
    lb = np.full(n, c.min_weight)
    ub = np.full(n, c.max_weight)
    index = {t: i for i, t in enumerate(tickers)}
    for t, (lo, hi) in c.asset_bounds.items():
        if t not in index:
            raise InvalidInputError(f"Bounds given for unknown asset {t!r}.")
        if not -MAX_ABS_WEIGHT <= lo <= hi <= MAX_ABS_WEIGHT:
            raise InvalidInputError(f"Invalid bounds for {t}: lower must not exceed upper.")
        lb[index[t]], ub[index[t]] = lo, hi

    sectors_needed = bool(c.sector_limits or c.excluded_sectors)
    sector_of: dict[str, str] = {}
    if sectors_needed:
        unknown = [t for t in tickers if not metadata.sectors.get(t)]
        if unknown:
            raise InvalidInputError(
                "Sector constraints require a sector for every asset. Missing: "
                + ", ".join(unknown)
            )
        sector_of = {t: metadata.sectors[t] for t in tickers}

    excluded: set[int] = set()
    for t in c.excluded_assets:
        if t not in index:
            raise InvalidInputError(f"Excluded asset {t!r} is not in the universe.")
        excluded.add(index[t])
    for sector in c.excluded_sectors:
        in_sector = [i for i, t in enumerate(tickers) if sector_of.get(t) == sector]
        if not in_sector:
            raise InvalidInputError(f"No assets belong to the excluded sector {sector!r}.")
        excluded.update(in_sector)
    if excluded:
        if (lb[list(excluded)] > 0).any():
            raise InfeasibleProblemError("An excluded asset also has a positive minimum weight.")
        lb[list(excluded)] = 0.0
        ub[list(excluded)] = 0.0
    if len(excluded) == n:
        raise InfeasibleProblemError("Every asset is excluded; nothing is left to invest in.")

    long_only = bool((lb >= 0).all())
    if c.uses_esg and not long_only:
        raise InvalidInputError(
            "ESG constraints and tilts are only supported for long-only portfolios."
        )

    if ub.sum() < 1.0 - 1e-12:
        raise InfeasibleProblemError(
            f"Maximum weights sum to {ub.sum():.1%}, so the portfolio cannot be fully invested. "
            "Raise the maximum weight or allow more assets."
        )
    if lb.sum() > 1.0 + 1e-12:
        raise InfeasibleProblemError(f"Minimum weights sum to {lb.sum():.1%}, which exceeds 100%.")

    rows: list[_Row] = [
        _Row(np.ones(n), "eq", 1.0, "budget", "Fully invested (weights sum to 100%)", tickers)
    ]

    for lim in c.sector_limits:
        members = tuple(t for t in tickers if sector_of.get(t) == lim.sector)
        if not members:
            raise InvalidInputError(f"No assets belong to sector {lim.sector!r}.")
        a = np.array([1.0 if sector_of.get(t) == lim.sector else 0.0 for t in tickers])
        if (
            lim.min_weight is not None
            and lim.max_weight is not None
            and lim.min_weight > lim.max_weight
        ):
            raise InvalidInputError(f"Sector {lim.sector}: minimum exceeds maximum.")
        if lim.max_weight is not None:
            if not 0.0 <= lim.max_weight <= MAX_ABS_WEIGHT:
                raise InvalidInputError(f"Sector {lim.sector}: invalid maximum weight.")
            rows.append(
                _Row(
                    a,
                    "le",
                    lim.max_weight,
                    "sector_max",
                    f"{lim.sector} ≤ {lim.max_weight:.1%}",
                    members,
                )
            )
        if lim.min_weight is not None:
            if lim.min_weight < 0.0:
                raise InvalidInputError(f"Sector {lim.sector}: invalid minimum weight.")
            rows.append(
                _Row(
                    a,
                    "ge",
                    lim.min_weight,
                    "sector_min",
                    f"{lim.sector} ≥ {lim.min_weight:.1%}",
                    members,
                )
            )

    investable = [t for i, t in enumerate(tickers) if i not in excluded]
    esg_vec: np.ndarray | None = None
    if require_esg_scores or c.uses_esg:
        purpose = "The ESG constraint" if c.min_esg_score is not None else "The ESG tilt"
        s_inv = score_vector(investable, metadata.esg_scores, purpose=purpose)
        esg_vec = np.full(n, np.nan)
        for t, s in zip(investable, s_inv, strict=True):
            esg_vec[index[t]] = s
    elif metadata.esg_scores:
        esg_vec = np.array(
            [
                np.nan if metadata.esg_scores.get(t) is None else float(metadata.esg_scores[t])  # type: ignore[arg-type]
                for t in tickers
            ]
        )

    if c.min_esg_score is not None:
        assert esg_vec is not None
        best = float(np.nanmax(esg_vec[[index[t] for t in investable]]))
        if c.min_esg_score > best + 1e-12:
            raise InfeasibleProblemError(
                f"Minimum ESG score {c.min_esg_score:.1f} exceeds the best available asset "
                f"score ({best:.1f}); no portfolio can satisfy it."
            )
        a = np.nan_to_num(esg_vec, nan=0.0)
        rows.append(
            _Row(
                a,
                "ge",
                c.min_esg_score,
                "min_esg",
                f"Portfolio ESG score ≥ {c.min_esg_score:.1f}",
                tuple(investable),
            )
        )

    if c.max_gross_exposure is not None and c.max_gross_exposure < 1.0:
        raise InvalidInputError("Maximum gross exposure must be at least 100%.")

    bench: np.ndarray | None = None
    if (c.benchmark_weights is None) != (c.max_tracking_error is None):
        raise InvalidInputError("A tracking-error limit needs both benchmark weights and a limit.")
    if c.benchmark_weights is not None and c.max_tracking_error is not None:
        unknown_b = [t for t in c.benchmark_weights if t not in index]
        if unknown_b:
            raise InvalidInputError(f"Benchmark contains unknown assets: {', '.join(unknown_b)}.")
        bench = np.array([float(c.benchmark_weights.get(t, 0.0)) for t in tickers])
        if abs(bench.sum() - 1.0) > 1e-6:
            raise InvalidInputError("Benchmark weights must sum to 100%.")
        if c.max_tracking_error <= 0:
            raise InvalidInputError("Maximum tracking error must be positive.")

    return _Compiled(
        tickers=tickers,
        mu=mu,
        factor=_covariance_factor(cov),
        cov=cov,
        lb=lb,
        ub=ub,
        excluded=frozenset(excluded),
        rows=rows,
        gross=c.max_gross_exposure,
        benchmark=bench,
        max_te=c.max_tracking_error,
        esg_scores=esg_vec,
        scenarios=estimates.scenarios,
    )


# --------------------------------------------------------------------------- solve

MIN_TAIL_OBSERVATIONS = 10


def cvar_tail_warning(confidence: float, observations: int) -> str | None:
    """Warning when a historical CVaR averages over too few observations to be stable."""
    tail = (1.0 - confidence) * observations
    if tail >= MIN_TAIL_OBSERVATIONS:
        return None
    return (
        f"The {confidence:.1%} CVaR averages only about {tail:.1f} of {observations} "
        "observations, so one or two extreme periods decide it. Lengthen the window, use a "
        "higher data frequency or lower the confidence level for a steadier estimate."
    )


_SOLVERS: tuple[str, ...] = ("CLARABEL", "SCS")
SCS_TIME_LIMIT = 20.0  # seconds


def _solve(problem: cp.Problem, what: str) -> str:
    """Solve with fallbacks; raise on infeasibility or failure. Returns solver name."""
    last_status = "not solved"
    for solver in _SOLVERS:
        try:
            if solver == "SCS":
                # First-order fallback: tight tolerance, but capped so a hard problem fails
                # with a clear error instead of tying up a small server for minutes.
                problem.solve(
                    solver=solver, eps=1e-9, max_iters=100_000, time_limit_secs=SCS_TIME_LIMIT
                )
            else:
                problem.solve(solver=solver)
        except (cp.error.SolverError, ArithmeticError, ValueError):
            last_status = f"{solver} failed"
            continue
        last_status = str(problem.status)
        if problem.status == cp.OPTIMAL:
            return solver
        if problem.status in (cp.INFEASIBLE, cp.INFEASIBLE_INACCURATE):
            raise InfeasibleProblemError(
                f"The constraints for the {what} problem cannot all be satisfied at once."
            )
        if problem.status == cp.OPTIMAL_INACCURATE:
            return f"{solver} (inaccurate)"
    raise SolverError(f"The solver could not solve the {what} problem (status: {last_status}).")


def _finalise(comp: _Compiled, raw: np.ndarray, extra_checks: list[tuple[str, bool]]) -> np.ndarray:
    """Remove round-off, then verify every constraint; raise if any is violated."""
    w = np.array(raw, dtype=float)
    if not np.isfinite(w).all():
        raise SolverError("The solver returned non-finite weights.")
    w[np.abs(w) < ZERO_WEIGHT_TOL] = 0.0
    w = np.clip(w, comp.lb, comp.ub)
    total = w.sum()
    if abs(total - 1.0) > VERIFY_TOL:
        raise SolverError(f"Solver weights sum to {total:.8f}, not 1.")
    w = w / total
    violations: list[str] = []
    if (w < comp.lb - VERIFY_TOL).any() or (w > comp.ub + VERIFY_TOL).any():
        violations.append("asset weight bounds")
    for row in comp.rows:
        v = float(row.coeffs @ w)
        tol = VERIFY_TOL * max(1.0, abs(row.bound))
        if (
            (row.sense == "le" and v > row.bound + tol)
            or (row.sense == "ge" and v < row.bound - tol)
            or (row.sense == "eq" and abs(v - row.bound) > tol)
        ):
            violations.append(row.label)
    if comp.gross is not None and np.abs(w).sum() > comp.gross + VERIFY_TOL:
        violations.append("gross exposure")
    if comp.benchmark is not None and comp.max_te is not None:
        te = portfolio_volatility(w - comp.benchmark, comp.cov)
        if te > comp.max_te + VERIFY_TOL:
            violations.append("tracking error")
    violations += [name for name, ok in extra_checks if not ok]
    if violations:
        raise SolverError(
            "The optimised portfolio failed verification for: " + "; ".join(violations)
        )
    return np.asarray(w, dtype=float)


def _dual(c: cp.Constraint) -> np.ndarray | float | None:
    val = c.dual_value
    if val is None:
        return None
    return val  # type: ignore[no-any-return]


def _diagnostics(
    comp: _Compiled,
    w: np.ndarray,
    tagged: list[tuple[cp.Constraint, _Row | str]],
    shadow_unit: str | None,
    extra: list[ConstraintDiagnostic],
) -> tuple[ConstraintDiagnostic, ...]:
    out: list[ConstraintDiagnostic] = []
    for c, tag in tagged:
        dual = _dual(c) if shadow_unit else None
        if isinstance(tag, _Row):
            v = float(tag.coeffs @ w)
            binding = abs(v - tag.bound) <= VERIFY_TOL * max(1.0, abs(tag.bound)) * 10
            if tag.kind == "budget":
                continue
            out.append(
                ConstraintDiagnostic(
                    kind=tag.kind,
                    label=tag.label,
                    value=v,
                    bound=tag.bound,
                    binding=binding,
                    assets=tag.assets,
                    shadow_price=None if dual is None else float(np.abs(np.asarray(dual)).sum()),
                    shadow_price_unit=shadow_unit if dual is not None else None,
                )
            )
        elif tag in ("lb", "ub"):
            bounds = comp.lb if tag == "lb" else comp.ub
            duals = None if dual is None else np.atleast_1d(np.asarray(dual, dtype=float))
            for i, t in enumerate(comp.tickers):
                if i in comp.excluded:
                    continue
                if abs(w[i] - bounds[i]) > 10 * VERIFY_TOL:
                    continue
                kind: ConstraintKind = "asset_upper" if tag == "ub" else "asset_lower"
                sym = "≤" if tag == "ub" else "≥"
                out.append(
                    ConstraintDiagnostic(
                        kind=kind,
                        label=f"{t} {sym} {bounds[i]:.1%}",
                        value=float(w[i]),
                        bound=float(bounds[i]),
                        binding=True,
                        assets=(t,),
                        shadow_price=None if duals is None else float(abs(duals[i])),
                        shadow_price_unit=shadow_unit if duals is not None else None,
                    )
                )
        elif tag == "gross" and comp.gross is not None:
            v = float(np.abs(w).sum())
            out.append(
                ConstraintDiagnostic(
                    "gross_exposure",
                    f"Gross exposure ≤ {comp.gross:.0%}",
                    v,
                    comp.gross,
                    abs(v - comp.gross) <= 10 * VERIFY_TOL,
                )
            )
        elif tag == "te" and comp.benchmark is not None and comp.max_te is not None:
            v = portfolio_volatility(w - comp.benchmark, comp.cov)
            out.append(
                ConstraintDiagnostic(
                    "tracking_error",
                    f"Tracking error ≤ {comp.max_te:.2%}",
                    v,
                    comp.max_te,
                    abs(v - comp.max_te) <= 1e-4 * max(comp.max_te, 1e-3),
                )
            )
    for i in sorted(comp.excluded):
        out.append(
            ConstraintDiagnostic(
                "excluded", f"{comp.tickers[i]} excluded", 0.0, 0.0, True, (comp.tickers[i],)
            )
        )
    return tuple(out + extra)


def _variance(comp: _Compiled, w: cp.Expression) -> cp.Expression:
    return cp.sum_squares(comp.factor @ w)


def _max_return(comp: _Compiled, mu: np.ndarray) -> tuple[float, np.ndarray]:
    """Highest expected return (under ``mu``) attainable within the constraints."""
    w = cp.Variable(comp.n)
    cons, _ = comp.cvx_constraints(w)
    prob = cp.Problem(cp.Maximize(mu @ w), cons)
    _solve(prob, "maximum-return")
    return float(mu @ w.value), np.asarray(w.value)


def _min_variance(
    comp: _Compiled,
) -> tuple[cp.Problem, cp.Variable, list[tuple[cp.Constraint, _Row | str]], str]:
    w = cp.Variable(comp.n)
    cons, tagged = comp.cvx_constraints(w)
    prob = cp.Problem(cp.Minimize(_variance(comp, w)), cons)
    solver = _solve(prob, "minimum-volatility")
    return prob, w, tagged, solver


def optimise(
    estimates: MarketEstimates,
    request: OptimisationRequest,
    metadata: AssetMetadata | None = None,
) -> OptimisationResult:
    """Solve a constrained mean-variance problem and return a verified result."""
    meta = metadata or AssetMetadata()
    c = request.constraints
    comp = _compile(estimates, c, meta, require_esg_scores=False)
    rf = estimates.risk_free_arithmetic(request.risk_free_rate)
    warnings: list[str] = []

    mu_obj = comp.mu
    tilt_active = c.esg_tilt > 0.0 and request.objective in TILT_OBJECTIVES
    if c.esg_tilt > 0.0 and not tilt_active:
        warnings.append(
            f"The ESG preference tilt does not affect the {request.objective.value} objective "
            "because it has no expected-return term; use a minimum ESG score constraint instead."
        )
    if tilt_active:
        assert comp.esg_scores is not None
        inv = [i for i in range(comp.n) if i not in comp.excluded]
        adj = comp.mu.copy()
        adj[inv] = esg_adjusted_returns(comp.mu[inv], comp.esg_scores[inv], c.esg_tilt)
        mu_obj = adj

    extra: list[ConstraintDiagnostic] = []
    extra_checks: list[tuple[str, bool]] = []
    shadow_unit: str | None = None
    obj = request.objective

    if obj is Objective.MIN_VOLATILITY:
        _, wv, tagged, solver = _min_variance(comp)
        raw = wv.value
        shadow_unit = "annualised variance"

    elif obj is Objective.TARGET_RETURN:
        if request.target_return is None:
            raise InvalidInputError("A target return is required for the target-return objective.")
        target = request.target_return
        best, _ = _max_return(comp, comp.mu)
        if target > best + 1e-10:
            raise InfeasibleProblemError(
                f"Target return {target:.2%} exceeds the maximum achievable expected return "
                f"({best:.2%}) under the constraints."
            )
        wv = cp.Variable(comp.n)
        cons, tagged = comp.cvx_constraints(wv)
        c_target = comp.mu @ wv >= target
        prob = cp.Problem(cp.Minimize(_variance(comp, wv)), [*cons, c_target])
        solver = _solve(prob, "target-return")
        raw = wv.value
        shadow_unit = "annualised variance"
        achieved = float(comp.mu @ raw)
        binding = abs(achieved - target) <= 1e-6
        if not binding:
            warnings.append(
                f"The minimum-volatility portfolio already exceeds the {target:.2%} target, "
                "so the target constraint is not binding."
            )
        extra_checks.append(("target return", achieved >= target - VERIFY_TOL))
        extra.append(
            ConstraintDiagnostic(
                "target_return",
                f"Expected return ≥ {target:.2%}",
                achieved,
                target,
                binding,
                shadow_price=None if c_target.dual_value is None else float(c_target.dual_value),
                shadow_price_unit=shadow_unit,
            )
        )

    elif obj is Objective.TARGET_VOLATILITY:
        if request.target_volatility is None or request.target_volatility <= 0:
            raise InvalidInputError("A positive target volatility is required.")
        target = request.target_volatility
        _, w_min, _, _ = _min_variance(comp)
        min_vol = portfolio_volatility(np.asarray(w_min.value), comp.cov)
        if target < min_vol - 1e-8:
            raise InfeasibleProblemError(
                f"Target volatility {target:.2%} is below the minimum achievable volatility "
                f"({min_vol:.2%}) under the constraints."
            )
        wv = cp.Variable(comp.n)
        cons, tagged = comp.cvx_constraints(wv)
        c_vol = cp.norm(comp.factor @ wv, 2) <= target
        prob = cp.Problem(cp.Maximize(mu_obj @ wv), [*cons, c_vol])
        solver = _solve(prob, "target-volatility")
        raw = wv.value
        shadow_unit = "annual return"
        vol = portfolio_volatility(np.asarray(raw), comp.cov)
        extra_checks.append(("target volatility", vol <= target + VERIFY_TOL))
        extra.append(
            ConstraintDiagnostic(
                "target_volatility",
                f"Volatility ≤ {target:.2%}",
                vol,
                target,
                abs(vol - target) <= 1e-5,
                shadow_price=None if c_vol.dual_value is None else float(c_vol.dual_value),
                shadow_price_unit=shadow_unit,
            )
        )

    elif obj is Objective.MAX_UTILITY:
        gamma = request.risk_aversion
        if gamma is None or gamma <= 0:
            raise InvalidInputError("A positive risk-aversion coefficient is required.")
        wv = cp.Variable(comp.n)
        cons, tagged = comp.cvx_constraints(wv)
        prob = cp.Problem(cp.Maximize(mu_obj @ wv - 0.5 * gamma * _variance(comp, wv)), cons)
        solver = _solve(prob, "maximum-utility")
        raw = wv.value
        shadow_unit = "utility"

    elif obj is Objective.MAX_SHARPE:
        excess = mu_obj - rf
        best_excess, _ = _max_return(comp, excess)
        if best_excess <= 1e-10:
            raise InfeasibleProblemError(
                "No portfolio satisfying the constraints has an expected return above the "
                f"risk-free rate ({request.risk_free_rate:.2%}); the maximum-Sharpe portfolio is "
                "undefined. Lower the risk-free rate, relax constraints, or use minimum volatility."
            )
        y = cp.Variable(comp.n)
        kappa = cp.Variable()
        cons, tagged = comp.cvx_constraints(y, kappa)
        prob = cp.Problem(cp.Minimize(_variance(comp, y)), [*cons, excess @ y == 1.0])
        solver = _solve(prob, "maximum-Sharpe")
        k = float(kappa.value)
        if k <= 1e-12:
            raise SolverError("Maximum-Sharpe homogenisation returned a degenerate scale.")
        raw = np.asarray(y.value) / k

    elif obj is Objective.MIN_CVAR:
        wv, tagged, solver, cvar_diag, checks = _min_cvar(comp, request)
        if comp.scenarios is not None and (
            tail_note := cvar_tail_warning(request.cvar_confidence, comp.scenarios.shape[0])
        ):
            warnings.append(tail_note)
        raw = wv.value
        shadow_unit = "one-period CVaR"
        extra += cvar_diag
        extra_checks += checks

    else:  # pragma: no cover - exhaustive enum
        raise InvalidInputError(f"Unsupported objective {obj!r}.")

    weights = _finalise(comp, np.asarray(raw), extra_checks)
    diagnostics = _diagnostics(comp, weights, tagged, shadow_unit, extra)
    return _build_result(
        comp,
        weights,
        obj,
        request.risk_free_rate,
        rf,
        solver,
        diagnostics,
        warnings,
        mu_obj if tilt_active else None,
        request.cvar_confidence,
    )


def _min_cvar(
    comp: _Compiled, request: OptimisationRequest
) -> tuple[
    cp.Variable,
    list[tuple[cp.Constraint, _Row | str]],
    str,
    list[ConstraintDiagnostic],
    list[tuple[str, bool]],
]:
    """Rockafellar-Uryasev LP: min a + sum(u) / ((1 - beta) T), u >= -R w - a, u >= 0."""
    if comp.scenarios is None:
        raise InvalidInputError("Minimum-CVaR optimisation needs the historical return scenarios.")
    beta = request.cvar_confidence
    if not 0.5 <= beta < 1.0:
        raise InvalidInputError("CVaR confidence must be between 50% and 100% (e.g. 95%).")
    scen = comp.scenarios
    t_obs = scen.shape[0]
    if (1.0 - beta) * t_obs < 1.0:
        raise InvalidInputError(
            f"A {beta:.1%} CVaR needs at least {int(np.ceil(1 / (1 - beta)))} observations; "
            f"the window has {t_obs}. Lengthen the window or lower the confidence."
        )
    diags: list[ConstraintDiagnostic] = []
    checks: list[tuple[str, bool]] = []
    target = request.target_return
    if target is not None:
        best, _ = _max_return(comp, comp.mu)
        if target > best + 1e-10:
            raise InfeasibleProblemError(
                f"Target return {target:.2%} exceeds the maximum achievable expected return "
                f"({best:.2%}) under the constraints."
            )
    w = cp.Variable(comp.n)
    alpha = cp.Variable()
    u = cp.Variable(t_obs, nonneg=True)
    cons, tagged = comp.cvx_constraints(w)
    cons.append(u >= -scen @ w - alpha)
    c_target = None
    if target is not None:
        c_target = comp.mu @ w >= target
        cons.append(c_target)
    prob = cp.Problem(cp.Minimize(alpha + cp.sum(u) / ((1.0 - beta) * t_obs)), cons)
    solver = _solve(prob, "minimum-CVaR")
    if target is not None and c_target is not None:
        achieved = float(comp.mu @ w.value)
        checks.append(("target return", achieved >= target - VERIFY_TOL))
        diags.append(
            ConstraintDiagnostic(
                "target_return",
                f"Expected return ≥ {target:.2%}",
                achieved,
                target,
                abs(achieved - target) <= 1e-6,
                shadow_price=None if c_target.dual_value is None else float(c_target.dual_value),
                shadow_price_unit="one-period CVaR",
            )
        )
    return w, tagged, solver, diags, checks


def _build_result(
    comp: _Compiled,
    weights: np.ndarray,
    objective: Objective,
    rf_annual: float,
    rf_arith: float,
    solver: str,
    diagnostics: tuple[ConstraintDiagnostic, ...],
    warnings: list[str],
    adjusted_mu: np.ndarray | None,
    cvar_confidence: float = 0.95,
) -> OptimisationResult:
    exp_ret = float(weights @ comp.mu)
    vol = portfolio_volatility(weights, comp.cov)
    sharpe = None if vol < 1e-12 else (exp_ret - rf_arith) / vol
    esg: float | None = None
    if comp.esg_scores is not None and (weights >= -1e-12).all():
        held = weights > ZERO_WEIGHT_TOL
        if not np.isnan(comp.esg_scores[held]).any():
            esg = portfolio_esg_score(
                np.where(held, weights, 0.0), np.nan_to_num(comp.esg_scores, nan=0.0)
            )
    if "inaccurate" in solver:
        warnings.append("The solver reported reduced accuracy; the solution passed verification.")
    var = cvar = None
    if comp.scenarios is not None and 0 < cvar_confidence < 1:
        var, cvar = historical_var_cvar(-(comp.scenarios @ weights), cvar_confidence)
    return OptimisationResult(
        tickers=comp.tickers,
        weights=weights,
        objective=objective,
        expected_return=exp_ret,
        volatility=vol,
        sharpe_ratio=sharpe,
        risk_free_rate=rf_annual,
        esg_score=esg,
        esg_adjusted_return=None if adjusted_mu is None else float(weights @ adjusted_mu),
        diagnostics=diagnostics,
        solver=solver,
        warnings=tuple(warnings),
        var=var,
        cvar=cvar,
        cvar_confidence=None if cvar is None else cvar_confidence,
    )


def max_achievable_return(
    estimates: MarketEstimates,
    constraints: PortfolioConstraints,
    metadata: AssetMetadata | None = None,
) -> tuple[float, np.ndarray]:
    """Highest expected return attainable under the constraints (an LP)."""
    comp = _compile(estimates, constraints, metadata or AssetMetadata(), require_esg_scores=False)
    return _max_return(comp, comp.mu)
