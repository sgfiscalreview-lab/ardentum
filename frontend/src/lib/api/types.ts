import type { components } from "./schema";

type S = components["schemas"];

export type UniverseSelection = S["UniverseSelection"];
export type EstimationSettings = S["EstimationSettings"];
export type BlackLittermanIn = S["BlackLittermanIn"];
export type ViewIn = S["ViewIn"];
export type BlackLittermanOut = S["BlackLittermanOut"];
export type ConstraintsIn = S["ConstraintsIn"];
export type ObjectiveIn = S["ObjectiveIn"];
export type Objective = ObjectiveIn["objective"];
export type SectorLimitIn = S["SectorLimitIn"];

export type DatasetOut = S["DatasetOut"];
export type DatasetSummaryOut = S["DatasetSummaryOut"];
export type AssetOut = S["AssetOut"];
export type DataWindowOut = S["DataWindowOut"];
export type EstimationOut = S["EstimationOut"];
export type PerformanceOut = S["PerformanceOut"];
export type MetricOut = S["MetricOut"];

export type AnalyticsResponse = S["AnalyticsResponse"];
export type OptimiseRequest = S["OptimiseRequest"];
export type OptimiseResponse = S["OptimiseResponse"];
export type PortfolioResultOut = S["PortfolioResultOut"];
export type HoldingOut = S["HoldingOut"];
export type FrontierRequest = S["FrontierRequest"];
export type FrontierResponse = S["FrontierResponse"];
export type FrontierPointOut = S["FrontierPointOut"];
export type CvarFrontierRequest = S["CvarFrontierRequest"];
export type CvarFrontierResponse = S["CvarFrontierResponse"];
export type CvarFrontierPointOut = S["CvarFrontierPointOut"];
export type EsgImpactRequest = S["EsgImpactRequest"];
export type EsgImpactResponse = S["EsgImpactResponse"];
export type MonteCarloRequest = S["MonteCarloRequest"];
export type MonteCarloResponse = S["MonteCarloResponse"];
export type BacktestRequest = S["BacktestRequest"];
export type BacktestResponse = S["BacktestResponse"];
export type CompareRequest = S["CompareRequest"];
export type CompareResponse = S["CompareResponse"];
export type PortfolioIn = S["PortfolioIn"];
export type PortfolioOut = S["PortfolioOut"];
export type MetaOut = S["MetaOut"];
export type RiskFreeOut = S["RiskFreeOut"];
export type RiskFreeSourceOut = S["RiskFreeSourceOut"];
export type TokenOut = S["TokenOut"];

export type OpenMetricOut = S["OpenMetricOut"];
export type OpenCompanyOut = S["OpenCompanyOut"];
export type EsgTransformIn = S["EsgTransformIn"];
export type OverlayPreviewRequest = S["OverlayPreviewRequest"];
export type OverlayPreviewOut = S["OverlayPreviewOut"];
export type OverlayEntryOut = S["OverlayEntryOut"];
export type OverlayOut = S["OverlayOut"];
export type OverlaySummaryOut = S["OverlaySummaryOut"];
export type CompositeComponentIn = S["CompositeComponentIn"];
export type CompositePreviewRequest = S["CompositePreviewRequest"];
export type CompositePreviewOut = S["CompositePreviewOut"];
