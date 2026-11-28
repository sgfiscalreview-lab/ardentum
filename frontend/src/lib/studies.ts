import fs from "node:fs";
import path from "node:path";

/**
 * The research notes' data: the recorded output of the studies in /research, written by
 * the "Research studies" workflow from the real public data. Read at build time only
 * (the pages are statically generated). Nothing here is computed: the notes only format
 * these numbers, and a unit test checks that each claim in their text still holds.
 */
const RESULTS_DIR =
  process.env.RESULTS_DIR ?? path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "research", "results");

function read<T>(...parts: string[]): T {
  return JSON.parse(fs.readFileSync(path.join(RESULTS_DIR, ...parts), "utf8")) as T;
}

// ------------------------------------------------------------------ the notes

export interface StudyMeta {
  slug: string;
  number: number;
  title: string;
  short: string;
  summary: string;
  keywords: string[];
  jel: string[];
}

export const STUDIES: StudyMeta[] = [
  {
    slug: "one-over-n",
    number: 1,
    title: "Optimal versus naive diversification revisited: US industry portfolios since 1970",
    short: "Optimal versus naive diversification revisited",
    summary:
      "Does any optimised portfolio beat simply splitting money equally? A walk-forward test of five optimised strategies against 1/N on 12 US industries, including the two decades since the original study.",
    keywords: ["portfolio choice", "estimation error", "1/N", "minimum variance", "Sharpe ratio test"],
    jel: ["G11", "C58"],
  },
  {
    slug: "currency-hedging",
    number: 2,
    title: "Should a European investor hedge the dollar? Currency risk in US equities, 1999 to present",
    short: "Should a European investor hedge the dollar?",
    summary:
      "For euro and sterling investors in US shares, full currency hedging barely lowers risk, because the dollar tends to rise when shares fall. Evidence from 13 US equity portfolios and four crises, including one in which the dollar fell.",
    keywords: ["currency hedging", "international diversification", "safe-haven currency", "hedge ratio"],
    jel: ["G11", "G15", "F31"],
  },
  {
    slug: "promised-versus-realised",
    number: 3,
    title: "The optimiser's promise: in-sample and out-of-sample Sharpe ratios of mean-variance portfolios",
    short: "The optimiser's promise",
    summary:
      "Maximum-Sharpe portfolios promise far more than they deliver. Measuring the gap at every year end since 1969, and how much shrinkage estimators close it.",
    keywords: ["mean-variance optimisation", "estimation error", "shrinkage", "out-of-sample performance"],
    jel: ["G11", "C13"],
  },
];

export function getStudy(slug: string): StudyMeta {
  const s = STUDIES.find((x) => x.slug === slug);
  if (!s) throw new Error(`Unknown study ${slug}`);
  return s;
}

// ------------------------------------------------------------------ shared

export interface RunMetadata {
  industries_sample: [string, string];
  fx_sample: Record<"EUR" | "GBP", [string, string]>;
  runtime_seconds: number;
  sources: string[];
}

export const runMetadata = (): RunMetadata => read<RunMetadata>("run_metadata.json");

/** Kenneth French's names for the 12 industry portfolios (the studies use upper-case codes). */
export const INDUSTRY: Record<string, string> = {
  "US market": "US market",
  NODUR: "Consumer non-durables",
  DURBL: "Consumer durables",
  MANUF: "Manufacturing",
  ENRGY: "Oil, gas and coal",
  CHEMS: "Chemicals",
  BUSEQ: "Business equipment",
  TELCM: "Telecommunications",
  UTILS: "Utilities",
  SHOPS: "Wholesale and retail",
  HLTH: "Healthcare",
  MONEY: "Finance",
  OTHER: "Other",
};

// ------------------------------------------------------------------ study 1

export interface Evaluation {
  months: number;
  mean_excess_annual: number;
  volatility_annual: number;
  sharpe: number;
  sharpe_minus_1n: number;
  p_value_vs_1n: number;
  p_value_vs_1n_robust: number;
  certainty_equivalent: number;
  max_drawdown: number;
}

export interface StrategyResult {
  full: Evaluation;
  "1970-2004": Evaluation;
  "2005-latest": Evaluation;
  annual_turnover: number;
  held_rebalances: number;
  tangency_fallbacks: number;
  crisis_returns: Record<string, number>;
}

/** Setting ("window 120m, costs 50bp") to strategy name to result. */
export type OneOverN = Record<string, Record<string, StrategyResult>>;

export interface Growth {
  setting: string;
  dates: string[];
  wealth: Record<string, number[]>;
}

export const oneOverN = (): OneOverN => read<OneOverN>("1_one_over_n", "results.json");
export const oneOverNGrowth = (): Growth => read<Growth>("1_one_over_n", "growth.json");

// ------------------------------------------------------------------ study 2

export interface HedgeAsset {
  months: number;
  volatility_unhedged: number;
  volatility_hedged: number;
  risk_change_from_hedging: number;
  mean_unhedged_annual: number;
  mean_hedged_annual: number;
  corr_us_stocks_vs_dollar: number;
  min_variance_hedge_ratio: number;
  max_drawdown_unhedged: number;
  max_drawdown_hedged: number;
}

export interface HedgeInvestor {
  assets: Record<string, HedgeAsset>;
  crises_us_market: Record<string, { local_usd: number; unhedged: number; hedged: number; currency: number }>;
  rolling_5y_hedge_ratio_us_market: Record<string, number>;
  sample: [string, string];
}

export type CurrencyHedging = Record<"euro" | "sterling", HedgeInvestor>;

export const currencyHedging = (): CurrencyHedging => read<CurrencyHedging>("2_currency_hedging", "results.json");

// ------------------------------------------------------------------ study 3

export interface PromiseSetting {
  portfolios: number;
  skipped_no_portfolio_beats_tbill: number;
  out_of_sample_months: number;
  mean_promised_sharpe: number;
  delivered_sharpe: number;
  delivered_sharpe_standard_error: number;
  delivered_sharpe_interval_95: [number, number];
  promise_minus_delivered: number;
  gap_in_standard_errors: number;
  equal_weight_sharpe_same_months: number;
  p_value_delivered_vs_equal_weight: number;
  p_value_delivered_vs_equal_weight_robust: number;
  corr_promised_vs_next_12_months: number;
}

export interface PromiseIllustration {
  estimated_on: [string, string];
  realised_on: [string, string];
  /** (volatility, return) pairs along the frontier. */
  promised: [number, number][];
  realised: [number, number][];
}

export type PromisedVersusRealised = Record<string, PromiseSetting> & { illustration: PromiseIllustration };

export interface PromiseRecord {
  lookback: number;
  estimator: string;
  year_end: number;
  promised: number;
  realised_next_12_months: number;
}

export const promisedVersusRealised = (): PromisedVersusRealised =>
  read<PromisedVersusRealised>("3_promised_vs_realised", "results.json");
export const promiseRecords = (): PromiseRecord[] => read<PromiseRecord[]>("3_promised_vs_realised", "portfolios.json");

/** The four estimation settings of study 3, in reading order. */
export const PROMISE_SETTINGS = [
  "Sample estimates, 60m window",
  "Shrinkage (Bayes-Stein + Ledoit-Wolf), 60m window",
  "Sample estimates, 120m window",
  "Shrinkage (Bayes-Stein + Ledoit-Wolf), 120m window",
] as const;

/** "Shrinkage (Bayes-Stein + Ledoit-Wolf), 60m window" -> "Shrinkage, 60-month window". */
export function settingLabel(s: string): string {
  const window = /(\d+)m window/.exec(s)?.[1];
  const kind = s.startsWith("Shrinkage") ? "Shrinkage" : "Sample";
  return `${kind} estimates, ${window}-month window`;
}

/** Month and year, e.g. "August 2026". */
export function monthYear(d: string): string {
  const [y, m] = d.split("-").map(Number);
  if (!y || !m) return d;
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
}
