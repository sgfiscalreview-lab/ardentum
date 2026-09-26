"""Request and response models for the public HTTP API (v1).

Conventions: rates and weights are decimal fractions (0.05 = 5%); returns and
volatilities are annualised unless the field name says otherwise; dates are
ISO-8601. Request models forbid unknown fields so typos fail loudly.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ardentum.quant.backtest import RebalanceFrequency
from ardentum.quant.estimation import CovarianceEstimator, MeanEstimator
from ardentum.quant.montecarlo import SimulationMethod
from ardentum.quant.optimisation import Objective

Ticker = Annotated[
    str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-_^=]*$")
]
Weight = Annotated[float, Field(ge=-1.0, le=1.0)]
MAX_ASSETS = 60


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    # Fields with defaults are always present in responses, so mark them required
    # in the serialization schema (keeps generated frontend types precise).
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


# ----------------------------------------------------------------------------- inputs


class UniverseSelection(RequestModel):
    dataset_id: str = Field(min_length=1, max_length=64)
    tickers: list[Ticker] = Field(min_length=1, max_length=MAX_ASSETS)
    start: dt.date | None = None
    end: dt.date | None = None
    frequency: Literal["daily", "weekly", "monthly"] = "daily"
    base_currency: str | None = Field(
        None,
        pattern=r"^[A-Z]{3}$",
        description="Express all prices in this ISO 4217 currency (unhedged, ECB rates).",
    )

    @field_validator("tickers")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("Tickers must be unique.")
        return v

    @model_validator(mode="after")
    def _dates(self) -> UniverseSelection:
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be before end.")
        return self


class EstimationSettings(RequestModel):
    mean_estimator: MeanEstimator = MeanEstimator.HISTORICAL
    covariance_estimator: CovarianceEstimator = CovarianceEstimator.LEDOIT_WOLF
    risk_free_rate: float = Field(0.0, ge=-0.05, le=0.25, description="Effective annual rate.")
    risk_free_source: str | None = Field(
        None, max_length=200, description="Where the rate came from; echoed in results."
    )


class RiskFreeRequest(RequestModel):
    source: Literal["fred_dgs3mo", "kenfrench_rf"] = "kenfrench_rf"
    start: dt.date | None = None
    end: dt.date | None = None

    @model_validator(mode="after")
    def _dates(self) -> RiskFreeRequest:
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be before end.")
        return self


class SectorLimitIn(RequestModel):
    sector: str = Field(min_length=1, max_length=80)
    min_weight: float | None = Field(None, ge=0.0, le=1.0)
    max_weight: float | None = Field(None, ge=0.0, le=1.0)


class TrackingErrorIn(RequestModel):
    benchmark: Literal["equal_weight"] | dict[Ticker, Weight] = "equal_weight"
    max_tracking_error: float = Field(gt=0.0, le=0.5)


class ConstraintsIn(RequestModel):
    min_weight: float = Field(0.0, ge=-1.0, le=1.0)
    max_weight: float = Field(1.0, ge=0.0, le=1.0)
    asset_bounds: dict[Ticker, tuple[Weight, Weight]] = Field(default_factory=dict)
    sector_limits: list[SectorLimitIn] = Field(default_factory=list, max_length=30)
    excluded_assets: list[Ticker] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list, max_length=30)
    min_esg_score: float | None = Field(None, ge=0.0, le=100.0)
    esg_tilt: float = Field(0.0, ge=0.0, le=0.2, description="Annual return per 1 SD of ESG score.")
    exclude_unscored_assets: bool = False
    max_gross_exposure: float | None = Field(None, ge=1.0, le=3.0)
    tracking_error: TrackingErrorIn | None = None

    @model_validator(mode="after")
    def _bounds(self) -> ConstraintsIn:
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight must not exceed max_weight.")
        for t, (lo, hi) in self.asset_bounds.items():
            if lo > hi:
                raise ValueError(f"Bounds for {t}: lower exceeds upper.")
        return self

    @property
    def uses_esg(self) -> bool:
        return (
            self.min_esg_score is not None
            or self.esg_tilt > 0
            or bool(self.excluded_sectors)
            or self.exclude_unscored_assets
        )


class ObjectiveIn(RequestModel):
    objective: Objective = Objective.MAX_SHARPE
    target_return: float | None = Field(None, ge=-0.5, le=2.0)
    target_volatility: float | None = Field(None, gt=0.0, le=2.0)
    risk_aversion: float | None = Field(None, gt=0.0, le=100.0)

    @model_validator(mode="after")
    def _params(self) -> ObjectiveIn:
        if self.objective is Objective.TARGET_RETURN and self.target_return is None:
            raise ValueError("target_return is required for the target_return objective.")
        if self.objective is Objective.TARGET_VOLATILITY and self.target_volatility is None:
            raise ValueError("target_volatility is required for the target_volatility objective.")
        if self.objective is Objective.MAX_UTILITY and self.risk_aversion is None:
            raise ValueError("risk_aversion is required for the max_utility objective.")
        return self


class OptimiseRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    objective: ObjectiveIn = Field(default_factory=ObjectiveIn)
    constraints: ConstraintsIn = Field(default_factory=ConstraintsIn)
    stability_resamples: int = Field(0, ge=0, le=100)
    seed: int | None = Field(None, ge=0, le=2**31 - 1)


class FrontierRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    constraints: ConstraintsIn = Field(default_factory=ConstraintsIn)
    n_points: int = Field(30, ge=5, le=100)
    compare_unconstrained: bool = True


class EsgImpactRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    objective: ObjectiveIn = Field(default_factory=ObjectiveIn)
    constraints: ConstraintsIn
    esg_levels: list[float] | None = Field(None, max_length=25)


class AnalyticsRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    benchmark: Ticker | None = None


class MonteCarloRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    weights: dict[Ticker, Weight]
    method: SimulationMethod = SimulationMethod.PARAMETRIC
    n_paths: int = Field(5000, ge=100, le=20_000)
    horizon_years: float = Field(10.0, gt=0.0, le=40.0)
    initial_value: float = Field(10_000.0, gt=0.0, le=1e12)
    target_value: float | None = Field(None, gt=0.0, le=1e13)
    mean_block_length: float = Field(21.0, ge=1.0, le=252.0)
    seed: int | None = Field(None, ge=0, le=2**31 - 1)


class OptimisedStrategyIn(RequestModel):
    type: Literal["optimised"] = "optimised"
    objective: ObjectiveIn = Field(default_factory=ObjectiveIn)
    constraints: ConstraintsIn = Field(default_factory=ConstraintsIn)


class FixedStrategyIn(RequestModel):
    type: Literal["fixed"] = "fixed"
    weights: dict[Ticker, Weight]


class EqualWeightStrategyIn(RequestModel):
    type: Literal["equal_weight"] = "equal_weight"


StrategyIn = Annotated[
    OptimisedStrategyIn | FixedStrategyIn | EqualWeightStrategyIn, Field(discriminator="type")
]


class BenchmarkIn(RequestModel):
    type: Literal["equal_weight", "asset"] = "equal_weight"
    ticker: Ticker | None = None

    @model_validator(mode="after")
    def _ticker(self) -> BenchmarkIn:
        if self.type == "asset" and not self.ticker:
            raise ValueError("An asset benchmark needs a ticker.")
        return self


class BacktestRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    strategy: StrategyIn
    lookback_years: float = Field(3.0, ge=0.25, le=20.0)
    rebalance: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_cost_bps: float = Field(10.0, ge=0.0, le=500.0)
    benchmark: BenchmarkIn | None = Field(default_factory=BenchmarkIn)


class PortfolioSpecIn(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    weights: dict[Ticker, Weight]


class CompareRequest(RequestModel):
    universe: UniverseSelection
    estimation: EstimationSettings = Field(default_factory=EstimationSettings)
    portfolios: list[PortfolioSpecIn] = Field(min_length=2, max_length=6)
    rebalance: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_cost_bps: float = Field(0.0, ge=0.0, le=500.0)


class PortfolioIn(RequestModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    dataset_id: str = Field(min_length=1, max_length=64)
    weights: dict[Ticker, Weight] = Field(min_length=1, max_length=MAX_ASSETS)
    spec: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None

    @field_validator("weights")
    @classmethod
    def _budget(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1 (got {total:.6f}).")
        return v


class DevLoginRequest(RequestModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ----------------------------------------------------------------------------- outputs


class MetricOut(ResponseModel):
    value: float | None
    reason: str | None = None


class ProvenanceOut(ResponseModel):
    source: str
    is_synthetic: bool
    adjustment: str
    retrieved_at: dt.datetime | None = None
    license_note: str | None = None
    notes: list[str] = Field(default_factory=list)


class DataWindowOut(ResponseModel):
    dataset_id: str
    start: dt.date
    end: dt.date
    observations: int
    frequency: str
    periods_per_year: int
    currency: str
    provenance: ProvenanceOut
    quality_notes: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


class RiskFreeSourceOut(ResponseModel):
    id: str
    name: str
    description: str
    citation: str
    available: bool


class RiskFreeOut(ResponseModel):
    source: RiskFreeSourceOut
    rate: float = Field(description="Effective annual rate (decimal).")
    label: str
    start: dt.date
    end: dt.date
    observations: int
    retrieved_at: dt.datetime
    stale: bool


class AssetOut(ResponseModel):
    ticker: str
    name: str
    asset_class: str
    sector: str | None
    currency: str
    isin: str | None
    market_cap: float | None
    esg_score: float | None
    esg_source: str | None
    esg_as_of: dt.date | None
    esg_is_synthetic: bool
    is_benchmark: bool


class DatasetOut(ResponseModel):
    id: str
    name: str
    kind: str
    description: str
    is_synthetic: bool
    provenance: ProvenanceOut
    start: dt.date | None
    end: dt.date | None
    assets: list[AssetOut]
    sectors: list[str]
    owned: bool = False


class DatasetSummaryOut(ResponseModel):
    id: str
    name: str
    kind: str
    description: str
    is_synthetic: bool
    n_assets: int
    start: dt.date | None
    end: dt.date | None
    owned: bool = False


class EstimationOut(ResponseModel):
    risk_free_rate: float
    risk_free_source: str
    mean_estimator: str
    covariance_estimator: str
    mean_shrinkage: float | None
    covariance_shrinkage: float | None
    observations: int
    start: dt.date | None
    end: dt.date | None


class PerformanceOut(ResponseModel):
    observations: int
    total_return: float
    cagr: float
    arithmetic_annual_return: float
    annualised_volatility: float
    sharpe_ratio: MetricOut
    sortino_ratio: MetricOut
    max_drawdown: float
    calmar_ratio: MetricOut
    var_95: float
    cvar_95: float
    skewness: MetricOut
    excess_kurtosis: MetricOut
    best_period: float
    worst_period: float
    positive_periods_fraction: float
    beta: MetricOut | None = None
    tracking_error: float | None = None
    information_ratio: MetricOut | None = None


class AssetStatsOut(ResponseModel):
    ticker: str
    name: str
    sector: str | None
    esg_score: float | None
    expected_return: float
    performance: PerformanceOut


class AnalyticsResponse(ResponseModel):
    data: DataWindowOut
    estimation: EstimationOut
    benchmark: str | None
    assets: list[AssetStatsOut]
    tickers: list[str]
    correlation: list[list[float]]
    covariance: list[list[float]]
    price_dates: list[dt.date]
    normalised_prices: dict[str, list[float]]


class ConstraintDiagnosticOut(ResponseModel):
    kind: str
    label: str
    value: float
    bound: float
    binding: bool
    assets: list[str]
    shadow_price: float | None
    shadow_price_unit: str | None


class HoldingOut(ResponseModel):
    ticker: str
    name: str
    sector: str | None
    weight: float
    expected_return: float
    volatility: float
    esg_score: float | None
    risk_contribution: float
    risk_contribution_pct: float
    marginal_contribution: float
    beta_to_portfolio: float
    required_return: float | None
    status: str
    reason: str


class ExplanationOut(ResponseModel):
    objective_summary: str
    headline: str
    statements: list[str]
    warnings: list[str]
    assumptions: list[str]


class StabilityOut(ResponseModel):
    ticker: str
    weight: float
    mean: float
    p05: float
    p50: float
    p95: float
    frequency_held: float


class SectorExposureOut(ResponseModel):
    sector: str
    weight: float


class PortfolioResultOut(ResponseModel):
    objective: str
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    esg_score: float | None
    esg_adjusted_return: float | None
    risk_free_rate: float
    diversification_ratio: float | None
    effective_number_of_assets: float
    holdings: list[HoldingOut]
    sector_exposures: list[SectorExposureOut]
    diagnostics: list[ConstraintDiagnosticOut]
    solver: str
    warnings: list[str]


class OptimiseResponse(ResponseModel):
    result: PortfolioResultOut
    explanation: ExplanationOut
    estimation: EstimationOut
    data: DataWindowOut
    excluded_unscored: list[str]
    stability: list[StabilityOut] | None = None
    stability_resamples: int | None = None
    seed: int | None = None


class FrontierPointOut(ResponseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    esg_score: float | None
    weights: dict[str, float]


class FrontierAssetOut(ResponseModel):
    ticker: str
    expected_return: float
    volatility: float
    esg_score: float | None
    sector: str | None


class FrontierResponse(ResponseModel):
    points: list[FrontierPointOut]
    min_volatility: FrontierPointOut
    max_sharpe: FrontierPointOut | None
    max_sharpe_unavailable_reason: str | None
    unconstrained_points: list[FrontierPointOut] | None
    assets: list[FrontierAssetOut]
    risk_free_rate: float
    risk_free_rate_arithmetic: float
    warnings: list[str]
    estimation: EstimationOut
    data: DataWindowOut
    excluded_unscored: list[str]


class WeightChangeOut(ResponseModel):
    ticker: str
    name: str
    sector: str | None
    esg_score: float | None
    baseline_weight: float
    esg_weight: float
    change: float


class EsgFrontierPointOut(ResponseModel):
    min_esg_score: float
    feasible: bool
    esg_score: float | None = None
    expected_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    reason: str | None = None


class EsgImpactResponse(ResponseModel):
    baseline: PortfolioResultOut
    esg: PortfolioResultOut
    delta_expected_return: float
    delta_volatility: float
    delta_sharpe_ratio: float | None
    delta_esg_score: float | None
    ex_ante_tracking_error: float
    ex_post_tracking_error: float
    ex_post_tracking_error_note: str
    weight_changes: list[WeightChangeOut]
    sector_changes: list[dict[str, float | str]]
    esg_frontier: list[EsgFrontierPointOut]
    esg_data_notes: list[str]
    estimation: EstimationOut
    data: DataWindowOut
    excluded_unscored: list[str]


class HistogramOut(ResponseModel):
    edges: list[float]
    counts: list[int]


class MonteCarloResponse(ResponseModel):
    method: str
    seed: int
    n_paths: int
    horizon_years: float
    initial_value: float
    times_years: list[float]
    percentiles: dict[str, list[float]]
    mean_path: list[float]
    sample_paths: list[list[float]]
    terminal_histogram: HistogramOut
    terminal_percentiles: dict[str, float]
    probability_of_loss: float
    probability_of_target: float | None
    target_value: float | None
    terminal_return_var_95: float
    terminal_return_cvar_95: float
    cagr_percentiles: dict[str, float]
    max_drawdown_percentiles: dict[str, float]
    portfolio_expected_return: float
    portfolio_volatility: float
    assumptions: list[str]
    data: DataWindowOut


class RebalanceEventOut(ResponseModel):
    date: dt.date
    status: str
    turnover: float
    cost: float
    estimation_start: dt.date
    estimation_end: dt.date
    weights: dict[str, float]
    message: str | None


class ContributionOut(ResponseModel):
    name: str
    contribution: float


class BrinsonOut(ResponseModel):
    sector: str
    allocation: float
    selection: float
    interaction: float
    total: float
    portfolio_weight: float
    benchmark_weight: float


class SeriesOut(ResponseModel):
    name: str
    wealth: list[float]
    drawdown: list[float]


class BacktestResponse(ResponseModel):
    strategy: str
    dates: list[dt.date]
    wealth_dates: list[dt.date]  # first rebalance date followed by `dates` (wealth/drawdown axis)
    portfolio: SeriesOut
    benchmark: SeriesOut | None
    performance: PerformanceOut
    benchmark_performance: PerformanceOut | None
    estimation_start: dt.date
    evaluation_start: dt.date
    evaluation_end: dt.date
    lookback_periods: int
    rebalance: str
    transaction_cost_bps: float
    total_cost: float
    annualised_turnover: float
    events: list[RebalanceEventOut]
    asset_contributions: list[ContributionOut]
    sector_contributions: list[ContributionOut]
    brinson: list[BrinsonOut] | None
    assumptions: list[str]
    data: DataWindowOut


class ComparedPortfolioOut(ResponseModel):
    name: str
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    esg_score: float | None
    effective_number_of_assets: float
    top_risk_contributors: list[ContributionOut]
    historical: PerformanceOut
    wealth: list[float]
    drawdown: list[float]


class CompareResponse(ResponseModel):
    portfolios: list[ComparedPortfolioOut]
    dates: list[dt.date]
    wealth_dates: list[dt.date]  # start date followed by `dates` (wealth/drawdown axis)
    return_correlation: list[list[float]]
    in_sample_warning: str
    estimation: EstimationOut
    data: DataWindowOut


class PortfolioOut(ResponseModel):
    id: str
    name: str
    description: str | None
    dataset_id: str
    weights: dict[str, float]
    spec: dict[str, Any] | None
    summary: dict[str, Any] | None
    created_at: dt.datetime
    updated_at: dt.datetime


class TokenOut(ResponseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: dt.datetime
    user_id: str
    email: str


class MeOut(ResponseModel):
    user_id: str
    email: str | None


class MetaOut(ResponseModel):
    version: str
    environment: str
    auth_mode: str
    supabase_url: str | None
    live_data_available: bool
    methodology_version: str


class ErrorBody(ResponseModel):
    type: str
    message: str
    details: Any | None = None


class ErrorOut(ResponseModel):
    error: ErrorBody
