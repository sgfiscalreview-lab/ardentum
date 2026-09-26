"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";

import type { ConstraintsIn, EstimationSettings, ObjectiveIn, UniverseSelection } from "./api/types";

/** A set of weights the user is working with (from the optimiser, a saved portfolio, ...). */
export interface WorkingPortfolio {
  name: string;
  datasetId: string;
  weights: Record<string, number>;
  source: "optimiser" | "saved" | "equal_weight" | "manual";
  savedId?: string;
  spec?: Record<string, unknown>;
}

export type PageKey = "analytics" | "optimise" | "frontier" | "esg" | "simulate" | "backtest" | "compare";

export interface WorkspaceState {
  universe: UniverseSelection;
  estimation: EstimationSettings;
  objective: ObjectiveIn;
  constraints: ConstraintsIn;
  working: WorkingPortfolio | null;
  /** Last submitted request per page; results are re-fetched from cache or recomputed. */
  requests: Partial<Record<PageKey, unknown>>;
  version: number;
}

export const DEFAULT_TICKERS = [
  "NWS.SYN", "CLDR.SYN", "MDC.SYN", "HLX.SYN", "ARB.SYN", "CSP.SYN", "PTR.SYN",
  "SOL.SYN", "GRD.SYN", "HRV.SYN", "FRG.SYN", "GOVB.SYN", "CORP.SYN", "GOLD.SYN",
];

const STATE_VERSION = 1;

export const DEFAULT_STATE: WorkspaceState = {
  universe: {
    dataset_id: "demo",
    tickers: DEFAULT_TICKERS,
    start: "2016-01-01",
    end: "2025-12-31",
    frequency: "daily",
  },
  estimation: {
    mean_estimator: "historical",
    covariance_estimator: "ledoit_wolf",
    risk_free_rate: 0.02,
  },
  objective: { objective: "max_sharpe" },
  constraints: {
    min_weight: 0,
    max_weight: 0.3,
    asset_bounds: {},
    sector_limits: [],
    excluded_assets: [],
    excluded_sectors: [],
    min_esg_score: null,
    esg_tilt: 0,
    exclude_unscored_assets: false,
    max_gross_exposure: null,
    tracking_error: null,
  },
  working: null,
  requests: {},
  version: STATE_VERSION,
};

type Action =
  | { type: "universe"; value: Partial<UniverseSelection> }
  | { type: "estimation"; value: Partial<EstimationSettings> }
  | { type: "objective"; value: ObjectiveIn }
  | { type: "constraints"; value: Partial<ConstraintsIn> }
  | { type: "working"; value: WorkingPortfolio | null }
  | { type: "request"; page: PageKey; value: unknown }
  | { type: "reset" }
  | { type: "hydrate"; value: WorkspaceState };

function reducer(state: WorkspaceState, action: Action): WorkspaceState {
  switch (action.type) {
    case "universe": {
      const universe = { ...state.universe, ...action.value };
      const datasetChanged = universe.dataset_id !== state.universe.dataset_id;
      return {
        ...state,
        universe,
        // Constraints and results that reference assets must not leak across datasets.
        constraints: datasetChanged ? DEFAULT_STATE.constraints : state.constraints,
        working: datasetChanged ? null : state.working,
        requests: datasetChanged ? {} : state.requests,
      };
    }
    case "estimation":
      return { ...state, estimation: { ...state.estimation, ...action.value } };
    case "objective":
      return { ...state, objective: action.value };
    case "constraints":
      return { ...state, constraints: { ...state.constraints, ...action.value } };
    case "working":
      return { ...state, working: action.value };
    case "request":
      return { ...state, requests: { ...state.requests, [action.page]: action.value } };
    case "reset":
      return DEFAULT_STATE;
    case "hydrate":
      return action.value;
  }
}

const STORAGE_KEY = "ardentum.workspace";

interface WorkspaceContextValue {
  state: WorkspaceState;
  hydrated: boolean;
  setUniverse: (v: Partial<UniverseSelection>) => void;
  setEstimation: (v: Partial<EstimationSettings>) => void;
  setObjective: (v: ObjectiveIn) => void;
  setConstraints: (v: Partial<ConstraintsIn>) => void;
  setWorking: (v: WorkingPortfolio | null) => void;
  submit: (page: PageKey, request: unknown) => void;
  reset: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, DEFAULT_STATE);
  const [hydrated, setHydrated] = useReducer(() => true, false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as WorkspaceState;
        if (parsed.version === STATE_VERSION) dispatch({ type: "hydrate", value: parsed });
      }
    } catch {
      /* corrupted or unavailable storage: start from defaults */
    }
    setHydrated();
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* storage full or blocked: state still works in memory */
    }
  }, [state, hydrated]);

  const setUniverse = useCallback((value: Partial<UniverseSelection>) => dispatch({ type: "universe", value }), []);
  const setEstimation = useCallback((value: Partial<EstimationSettings>) => dispatch({ type: "estimation", value }), []);
  const setObjective = useCallback((value: ObjectiveIn) => dispatch({ type: "objective", value }), []);
  const setConstraints = useCallback((value: Partial<ConstraintsIn>) => dispatch({ type: "constraints", value }), []);
  const setWorking = useCallback((value: WorkingPortfolio | null) => dispatch({ type: "working", value }), []);
  const submit = useCallback((page: PageKey, value: unknown) => dispatch({ type: "request", page, value }), []);
  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  const value = useMemo(
    () => ({ state, hydrated, setUniverse, setEstimation, setObjective, setConstraints, setWorking, submit, reset }),
    [state, hydrated, setUniverse, setEstimation, setObjective, setConstraints, setWorking, submit, reset],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}

/** Equal weights over the current selection (a convenience, not a calculation). */
export function equalWeights(tickers: string[]): Record<string, number> {
  const n = tickers.length;
  const w: Record<string, number> = {};
  tickers.forEach((t, i) => {
    // Distribute rounding so the weights sum to exactly one.
    w[t] = i === n - 1 ? 1 - (n - 1) * (1 / n) : 1 / n;
  });
  return w;
}
