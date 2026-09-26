"""Explainable portfolio decisions.

Explanations are derived deterministically from the optimisation's first-order
(KKT) conditions, the Euler risk decomposition and the constraint diagnostics —
never from free-form text generation — so every statement is a verifiable fact
about the solution.

Key identities used
-------------------
* Minimum variance: every held asset not at a bound has the same marginal
  variance ``(S w)_i``; a zero-weight asset has marginal variance at least that
  high, i.e. adding it would increase risk.
* Maximum Sharpe (tangency): for held, unbounded assets
  ``mu_i - rf = beta_i (mu_p - rf)`` with ``beta_i = (S w)_i / (w' S w)``. An
  excluded-by-optimiser asset has ``mu_i - rf < beta_i (mu_p - rf)``: its expected
  excess return is too low for the risk it would add.

Weight stability: :func:`resampled_weight_intervals` re-estimates inputs on
bootstrap resamples of the return history and re-optimises (in the spirit of
Michaud 1998, "Efficient Asset Management"), showing how sensitive the weights
are to estimation error.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ardentum.quant.errors import QuantError
from ardentum.quant.estimation import (
    CovarianceEstimator,
    MarketEstimates,
    MeanEstimator,
    estimate,
)
from ardentum.quant.optimisation import (
    AssetMetadata,
    Objective,
    OptimisationRequest,
    OptimisationResult,
    optimise,
)
from ardentum.quant.portfolio import (
    diversification_ratio,
    effective_number_of_assets,
    risk_decomposition,
)

HELD_TOL = 1e-6


@dataclass(frozen=True)
class AssetExplanation:
    ticker: str
    weight: float
    expected_return: float
    volatility: float
    beta_to_portfolio: float
    required_return: float | None  # return the asset needs to justify inclusion (max Sharpe)
    risk_contribution_pct: float
    status: str  # "held", "at_upper_bound", "at_lower_bound", "zero_by_optimiser", "excluded"
    reason: str


@dataclass(frozen=True)
class Explanation:
    objective_summary: str
    headline: str
    statements: tuple[str, ...]
    assets: tuple[AssetExplanation, ...]
    effective_number_of_assets: float
    diversification_ratio: float | None
    largest_risk_contributors: tuple[tuple[str, float], ...]
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]


_OBJECTIVE_TEXT = {
    Objective.MIN_VOLATILITY: "Minimise expected portfolio volatility.",
    Objective.MAX_SHARPE: "Maximise the expected Sharpe ratio (excess return per unit of volatility).",
    Objective.TARGET_RETURN: "Minimise volatility while achieving at least the target expected return.",
    Objective.TARGET_VOLATILITY: "Maximise expected return without exceeding the target volatility.",
    Objective.MAX_UTILITY: "Maximise mean-variance utility: expected return minus a risk-aversion penalty on variance.",
}


def explain(
    result: OptimisationResult,
    estimates: MarketEstimates,
    request: OptimisationRequest,
) -> Explanation:
    """Build a structured, verifiable explanation of an optimisation result."""
    w = result.weights
    mu = estimates.expected_returns
    cov = estimates.covariance
    vols = estimates.volatilities
    var_p = float(w @ cov @ w)
    cov_wp = cov @ w
    betas = cov_wp / var_p if var_p > 1e-16 else np.zeros_like(w)
    rf = estimates.risk_free_arithmetic(request.risk_free_rate)
    excess_p = result.expected_return - rf

    try:
        rd = risk_decomposition(w, cov)
        pct = rd.percent_contribution
        div = diversification_ratio(w, cov)
    except QuantError:
        pct = np.zeros_like(w)
        div = None

    excluded = {a for d in result.diagnostics if d.kind == "excluded" for a in d.assets}
    upper = {a for d in result.diagnostics if d.kind == "asset_upper" for a in d.assets}
    lower = {a for d in result.diagnostics if d.kind == "asset_lower" for a in d.assets}
    lam = float(np.mean(cov_wp[w > HELD_TOL])) if (w > HELD_TOL).any() else 0.0

    assets: list[AssetExplanation] = []
    for i, t in enumerate(result.tickers):
        required = rf + betas[i] * excess_p if request.objective is Objective.MAX_SHARPE else None
        if t in excluded:
            status, reason = "excluded", "Excluded by a constraint (asset or sector exclusion)."
        elif abs(w[i]) <= HELD_TOL:
            status = "zero_by_optimiser"
            reason = _zero_reason(request.objective, mu[i], required, cov_wp[i], lam)
        elif t in upper:
            status = "at_upper_bound"
            reason = (
                f"Held at its maximum weight of {w[i]:.1%}; the optimiser would hold more "
                "without this limit."
            )
        elif t in lower:
            status = "at_lower_bound"
            reason = f"Held at its minimum weight of {w[i]:.1%} required by a constraint."
        else:
            status = "held"
            reason = _held_reason(request.objective, w[i], pct[i])
        assets.append(
            AssetExplanation(
                ticker=t,
                weight=float(w[i]),
                expected_return=float(mu[i]),
                volatility=float(vols[i]),
                beta_to_portfolio=float(betas[i]),
                required_return=None if required is None else float(required),
                risk_contribution_pct=float(pct[i]),
                status=status,
                reason=reason,
            )
        )

    n_eff = effective_number_of_assets(np.clip(w, 0, None)) if (w > 0).any() else 0.0
    order = np.argsort(-pct)
    top = tuple((result.tickers[i], float(pct[i])) for i in order[:3] if w[i] > HELD_TOL)

    statements: list[str] = []
    held = [a for a in assets if a.weight > HELD_TOL]
    statements.append(
        f"The portfolio holds {len(held)} of {len(assets)} assets; its effective number of "
        f"independent positions (inverse Herfindahl) is {n_eff:.1f}."
    )
    statements.append(
        f"Expected return {result.expected_return:.2%} and volatility {result.volatility:.2%} "
        "per year are model estimates from the historical window, not forecasts of realised returns."
    )
    if result.sharpe_ratio is not None:
        statements.append(
            f"Expected Sharpe ratio {result.sharpe_ratio:.2f} using a {request.risk_free_rate:.2%} "
            "risk-free rate."
        )
    if top:
        statements.append(
            "Largest sources of risk: "
            + ", ".join(f"{t} ({p:.0%} of volatility)" for t, p in top)
            + "."
        )
    for d in result.diagnostics:
        if d.binding and d.kind in {
            "sector_max",
            "sector_min",
            "min_esg",
            "tracking_error",
            "gross_exposure",
            "target_return",
            "target_volatility",
        }:
            statements.append(f"Binding constraint: {d.label} (achieved {_fmt(d.kind, d.value)}).")
    if result.esg_score is not None:
        statements.append(f"Value-weighted portfolio ESG score: {result.esg_score:.1f} / 100.")

    warnings = list(result.warnings)
    if w.max() > 0.4:
        warnings.append(
            f"Concentration: {result.tickers[int(np.argmax(w))]} is {w.max():.0%} of the portfolio."
        )
    years = estimates.observations / estimates.periods_per_year
    if years < 3:
        warnings.append(
            f"The estimation window covers only {years:.1f} years; expected-return estimates "
            "from short histories are highly uncertain."
        )
    if request.objective in {
        Objective.MAX_SHARPE,
        Objective.TARGET_RETURN,
        Objective.TARGET_VOLATILITY,
        Objective.MAX_UTILITY,
    }:
        se = float(np.median(vols) / np.sqrt(max(years, 1e-9)))
        warnings.append(
            f"Return-seeking objectives are sensitive to expected-return estimates; the typical "
            f"standard error of an asset's estimated annual mean here is about {se:.1%}."
        )

    headline = _headline(request.objective, result)
    return Explanation(
        objective_summary=_OBJECTIVE_TEXT[request.objective],
        headline=headline,
        statements=tuple(statements),
        assets=tuple(assets),
        effective_number_of_assets=float(n_eff),
        diversification_ratio=div,
        largest_risk_contributors=top,
        warnings=tuple(warnings),
        assumptions=assumptions_for(estimates, request),
    )


def _fmt(kind: str, value: float) -> str:
    return f"{value:.1f}" if kind == "min_esg" else f"{value:.2%}"


def _headline(objective: Objective, r: OptimisationResult) -> str:
    if objective is Objective.MIN_VOLATILITY:
        return f"Lowest-risk portfolio available under the constraints: {r.volatility:.2%} expected volatility."
    if objective is Objective.MAX_SHARPE:
        return f"Best expected risk-adjusted return: Sharpe ratio {r.sharpe_ratio:.2f}."
    if objective is Objective.TARGET_RETURN:
        return f"Lowest-risk way to reach {r.expected_return:.2%} expected return: {r.volatility:.2%} volatility."
    if objective is Objective.TARGET_VOLATILITY:
        return f"Highest expected return ({r.expected_return:.2%}) within {r.volatility:.2%} volatility."
    return f"Best risk-return trade-off for the chosen risk aversion: {r.expected_return:.2%} return, {r.volatility:.2%} volatility."


def _held_reason(objective: Objective, weight: float, pct: float) -> str:
    if objective is Objective.MIN_VOLATILITY:
        return (
            f"Held at {weight:.1%}: at this weight its marginal contribution to variance equals "
            f"that of every other unconstrained holding. It contributes {pct:.0%} of risk."
        )
    if objective is Objective.MAX_SHARPE:
        return (
            f"Held at {weight:.1%}: its expected excess return compensates for the risk it adds "
            f"(return proportional to its beta to the portfolio). It contributes {pct:.0%} of risk."
        )
    return f"Held at {weight:.1%}; it contributes {pct:.0%} of portfolio risk."


def _zero_reason(
    objective: Objective,
    mu_i: float,
    required: float | None,
    marginal_var: float,
    lam: float,
) -> str:
    if objective is Objective.MAX_SHARPE and required is not None:
        return (
            f"Not held: its expected return ({mu_i:.2%}) is below the {required:.2%} its "
            "covariance with the portfolio would require, so adding it would lower the Sharpe ratio."
        )
    if objective is Objective.MIN_VOLATILITY:
        return (
            "Not held: its covariance with the portfolio is at least as high as the portfolio's "
            "own variance, so adding any amount would increase risk."
            if marginal_var >= lam - 1e-12
            else "Not held by the optimiser."
        )
    return "Not held: including it would not improve the objective given its return and risk."


_MEAN_NAMES = {
    MeanEstimator.HISTORICAL: "historical sample mean",
    MeanEstimator.BAYES_STEIN: "Bayes-Stein shrinkage estimator (Jorion 1986)",
}
_COV_NAMES = {
    CovarianceEstimator.SAMPLE: "sample covariance",
    CovarianceEstimator.LEDOIT_WOLF: "Ledoit-Wolf shrinkage toward a scaled identity",
    CovarianceEstimator.LEDOIT_WOLF_CONSTANT_CORRELATION: "Ledoit-Wolf shrinkage toward constant correlation",
}


def assumptions_for(estimates: MarketEstimates, request: OptimisationRequest) -> tuple[str, ...]:
    years = estimates.observations / estimates.periods_per_year
    window = (
        f"{estimates.start} to {estimates.end}"
        if estimates.start and estimates.end
        else "the sample"
    )
    out = [
        f"Estimation window: {window} ({estimates.observations} observations, {years:.1f} years, "
        f"{estimates.periods_per_year} periods per year).",
        f"Expected returns: {_MEAN_NAMES[estimates.mean_estimator]} of arithmetic mean "
        "returns, annualised linearly.",
        f"Covariance: {_COV_NAMES[estimates.covariance_estimator]}"
        + (
            f" (shrinkage intensity {estimates.covariance_shrinkage:.2f})."
            if estimates.covariance_shrinkage is not None
            else "."
        ),
        f"Risk-free rate: {request.risk_free_rate:.2%} (effective annual).",
        "Single-period mean-variance model: returns are summarised by their mean and covariance; "
        "higher moments and regime changes are ignored.",
        "No transaction costs, taxes or liquidity constraints in the optimisation.",
    ]
    if estimates.mean_shrinkage is not None:
        out.insert(2, f"Bayes-Stein shrinkage intensity for means: {estimates.mean_shrinkage:.2f}.")
    return tuple(out)


@dataclass(frozen=True)
class WeightInterval:
    ticker: str
    weight: float
    mean: float  # resampled (Michaud-style) average weight; means sum to one
    p05: float
    p50: float
    p95: float
    frequency_held: float  # share of resamples in which the asset is held


def resampled_weight_intervals(
    returns: pd.DataFrame,
    periods_per_year: int,
    request: OptimisationRequest,
    metadata: AssetMetadata,
    base_weights: np.ndarray,
    *,
    n_resamples: int = 50,
    seed: int = 0,
    mean_estimator: MeanEstimator = MeanEstimator.HISTORICAL,
    covariance_estimator: CovarianceEstimator = CovarianceEstimator.LEDOIT_WOLF,
) -> tuple[tuple[WeightInterval, ...], int]:
    """Weight percentiles across bootstrap resamples of the estimation window.

    Returns (intervals, number of successful resamples). Resamples whose
    optimisation is infeasible are skipped and counted out.
    """
    rng = np.random.default_rng(seed)
    t_len = len(returns)
    samples: list[np.ndarray] = []
    for _ in range(n_resamples):
        idx = rng.integers(0, t_len, size=t_len)
        boot = returns.iloc[idx].reset_index(drop=True)
        boot.index = returns.index  # keep a valid date index for provenance
        try:
            est = estimate(
                boot,
                periods_per_year,
                mean_estimator=mean_estimator,
                covariance_estimator=covariance_estimator,
            )
            samples.append(optimise(est, request, metadata).weights)
        except QuantError:
            continue
    if not samples:
        return (), 0
    arr = np.vstack(samples)
    out = tuple(
        WeightInterval(
            ticker=str(t),
            weight=float(base_weights[i]),
            mean=float(arr[:, i].mean()),
            p05=float(np.percentile(arr[:, i], 5)),
            p50=float(np.percentile(arr[:, i], 50)),
            p95=float(np.percentile(arr[:, i], 95)),
            frequency_held=float(np.mean(arr[:, i] > HELD_TOL)),
        )
        for i, t in enumerate(returns.columns)
    )
    return out, len(samples)
