import type { UniverseSelection } from "./api/types";
import { DEFAULT_STATE, DEFAULT_TICKERS, equalWeights, type WorkingPortfolio, type WorkspaceState } from "./workspace";

/** The 12 US industry portfolios of the Kenneth French Data Library (dataset "kf12"). */
export const KF12 = ["NODUR", "DURBL", "MANUF", "ENRGY", "CHEMS", "BUSEQ", "TELCM", "UTILS", "SHOPS", "HLTH", "MONEY", "OTHER"];

const BONDS = ["GOVB.SYN", "CORP.SYN"];
const NOT_SHARES = [...BONDS, "GOLD.SYN"];

/** 60% split equally over the demo's shares, 40% over its two bond funds. */
export function balancedWeights(): Record<string, number> {
  const shares = DEFAULT_TICKERS.filter((t) => !NOT_SHARES.includes(t));
  const w: Record<string, number> = {};
  shares.forEach((t, i) => {
    w[t] = i === shares.length - 1 ? 0.6 - (shares.length - 1) * (0.6 / shares.length) : 0.6 / shares.length;
  });
  for (const b of BONDS) w[b] = 0.2;
  return w;
}

export interface Preset {
  key: string;
  title: string;
  description: string;
  real: boolean;
  /** Page that opens with the calculation already set up. */
  href: string;
  build: () => WorkspaceState;
}

const industries = (start: string): UniverseSelection => ({
  dataset_id: "kf12",
  tickers: KF12,
  start,
  end: null,
  frequency: "daily",
  currency_hedged: false,
});

function equalIndustries(): WorkingPortfolio {
  return { name: "Equal weight, 12 US industries", datasetId: "kf12", weights: equalWeights(KF12), source: "equal_weight" };
}

function fresh(universe: UniverseSelection, working: WorkingPortfolio | null): WorkspaceState {
  return { ...DEFAULT_STATE, universe, working, requests: {} };
}

export const PRESETS: Preset[] = [
  {
    key: "balanced",
    title: "Balanced 60/40",
    description: "60% shares and 40% bonds, compared with equal weights. Demo data (synthetic).",
    real: false,
    href: "/app/compare",
    build: () => {
      const working: WorkingPortfolio = { name: "Balanced 60/40", datasetId: "demo", weights: balancedWeights(), source: "manual" };
      const s = fresh(DEFAULT_STATE.universe, working);
      const equal = equalWeights(DEFAULT_TICKERS);
      const tickers = Array.from(new Set([...Object.keys(working.weights), ...Object.keys(equal)]));
      s.requests = {
        compare: {
          universe: { ...s.universe, tickers },
          estimation: s.estimation,
          portfolios: [
            { name: `Working: ${working.name}`, weights: working.weights },
            { name: `Equal weight (${DEFAULT_TICKERS.length} assets)`, weights: equal },
          ],
          rebalance: "monthly",
          transaction_cost_bps: 0,
        },
      };
      return s;
    },
  },
  {
    key: "industries-optimise",
    title: "Lowest-risk mix of US industries",
    description: "The 12 US industries since 1990, optimised for the lowest volatility with at most 30% in each. Real data.",
    real: true,
    href: "/app/optimise",
    build: () => {
      const s = fresh(industries("1990-01-01"), null);
      s.objective = { ...DEFAULT_STATE.objective, objective: "min_volatility" };
      s.requests = {
        optimise: { universe: s.universe, estimation: s.estimation, objective: s.objective, constraints: s.constraints, stability_resamples: 0, seed: null },
      };
      return s;
    },
  },
  {
    key: "industries-crises",
    title: "US industries through past crashes",
    description: "Equal weights in the 12 US industries, bought before each crash since 1929 and held. Real data.",
    real: true,
    href: "/app/crises",
    build: () => {
      const working = equalIndustries();
      const s = fresh(industries("1990-01-01"), working);
      s.requests = {
        stress: { universe: s.universe, portfolio: { name: `Working: ${working.name}`, weights: working.weights }, episodes: null, custom: null },
      };
      return s;
    },
  },
  {
    key: "industries-factors",
    title: "What drives US industries",
    description: "Market, size and value exposure of equal weights in the 12 US industries since 2000. Real data.",
    real: true,
    href: "/app/factors",
    build: () => {
      const working = equalIndustries();
      const s = fresh(industries("2000-01-01"), working);
      s.requests = {
        factors: { universe: s.universe, portfolio: { name: `Working: ${working.name}`, weights: working.weights } },
      };
      return s;
    },
  },
];
