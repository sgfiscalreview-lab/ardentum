"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";

import type { ConstraintsIn, EstimationSettings, ObjectiveIn, UniverseSelection } from "./api/types";
import { decodeShare, SHARE_PREFIX } from "./share";

/** A set of weights the user is working with (from the optimiser, a saved portfolio, ...). */
export interface WorkingPortfolio {
  name: string;
  datasetId: string;
  weights: Record<string, number>;
  source: "optimiser" | "saved" | "equal_weight" | "manual";
  savedId?: string;
  spec?: Record<string, unknown>;
}

export type PageKey = "analytics" | "optimise" | "frontier" | "frontier_cvar" | "esg" | "simulate" | "backtest" | "compare";

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
    currency_hedged: false,
  },
  estimation: {
    mean_estimator: "historical",
    covariance_estimator: "ledoit_wolf",
    risk_free_rate: 0.02,
  },
  objective: { objective: "max_sharpe", cvar_confidence: 0.95 },
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

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

const isStringList = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");

/**
 * Rebuilds saved settings on top of the current defaults, so fields added since they were
 * saved get their default values and malformed parts fall back instead of crashing a page.
 * Returns null when the data is not a workspace of this version.
 */
export function restoreState(raw: unknown): WorkspaceState | null {
  if (!isRecord(raw) || raw.version !== STATE_VERSION) return null;
  const d = DEFAULT_STATE;
  const universe = { ...d.universe, ...(isRecord(raw.universe) ? raw.universe : {}) } as UniverseSelection;
  if (typeof universe.dataset_id !== "string" || !isStringList(universe.tickers) || universe.tickers.length === 0) {
    return { ...d };
  }
  const constraints = { ...d.constraints, ...(isRecord(raw.constraints) ? raw.constraints : {}) } as ConstraintsIn;
  if (!isRecord(constraints.asset_bounds)) constraints.asset_bounds = {};
  if (!Array.isArray(constraints.sector_limits)) constraints.sector_limits = [];
  if (!isStringList(constraints.excluded_assets)) constraints.excluded_assets = [];
  if (!isStringList(constraints.excluded_sectors)) constraints.excluded_sectors = [];
  const working = isRecord(raw.working) && isRecord(raw.working.weights) ? (raw.working as unknown as WorkingPortfolio) : null;
  return {
    universe,
    estimation: { ...d.estimation, ...(isRecord(raw.estimation) ? raw.estimation : {}) } as EstimationSettings,
    objective: { ...d.objective, ...(isRecord(raw.objective) ? raw.objective : {}) } as ObjectiveIn,
    constraints,
    working,
    requests: isRecord(raw.requests) ? (raw.requests as WorkspaceState["requests"]) : {},
    version: STATE_VERSION,
  };
}

const PAGE_KEYS: readonly PageKey[] = ["analytics", "optimise", "frontier", "frontier_cvar", "esg", "simulate", "backtest", "compare"];
const SHARE_VERSION = 1;

/** What a shareable link carries: the settings, the working portfolio and the given pages' calculations. */
export function sharePayload(state: WorkspaceState, pages: string[]): Record<string, unknown> {
  const requests: Record<string, unknown> = {};
  for (const k of pages) if (state.requests[k as PageKey] !== undefined) requests[k] = state.requests[k as PageKey];
  return {
    v: SHARE_VERSION,
    universe: state.universe,
    estimation: state.estimation,
    objective: state.objective,
    constraints: state.constraints,
    working: state.working,
    requests,
  };
}

/** Workspace settings from a shared link, or null when it is not a valid link of this version. */
export function stateFromShare(payload: unknown): WorkspaceState | null {
  if (!isRecord(payload) || payload.v !== SHARE_VERSION) return null;
  const u = payload.universe;
  if (!isRecord(u) || typeof u.dataset_id !== "string" || !isStringList(u.tickers) || u.tickers.length === 0) return null;
  const requests: Partial<Record<PageKey, unknown>> = {};
  if (isRecord(payload.requests)) {
    for (const k of PAGE_KEYS) if (isRecord(payload.requests[k])) requests[k] = payload.requests[k];
  }
  return restoreState({ ...payload, requests, version: STATE_VERSION });
}

/** After a shared link was opened: what to offer the visitor. */
export type SharedLink = { status: "loaded"; previous: WorkspaceState } | { status: "unreadable" };

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
  /** Set when this page was opened from a shared link. */
  shared: SharedLink | null;
  /** Keep the shared settings (or acknowledge an unreadable link). */
  dismissShared: () => void;
  /** Return to the settings this browser had before the shared link replaced them. */
  restoreBeforeShare: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, DEFAULT_STATE);
  const [hydrated, setHydrated] = useReducer(() => true, false);
  const [shared, setShared] = useState<SharedLink | null>(null);
  // The address's fragment as first seen: it is removed from the address bar once read.
  const fragment = useRef<string | null>(null);
  const latest = useRef(state);
  useEffect(() => {
    latest.current = state;
  });

  // A link opened in a tab already showing this site only changes the fragment.
  useEffect(() => {
    const onHashChange = () => {
      const f = window.location.hash;
      if (!f.startsWith(SHARE_PREFIX)) return;
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
      const previous = latest.current;
      decodeShare(f)
        .then((payload) => {
          const incoming = stateFromShare(payload);
          if (!incoming) throw new Error("not a shared workspace");
          dispatch({ type: "hydrate", value: incoming });
          setShared({ status: "loaded", previous });
        })
        .catch(() => setShared({ status: "unreadable" }));
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    let local: WorkspaceState | null = null;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) local = restoreState(JSON.parse(raw));
      if (local) dispatch({ type: "hydrate", value: local });
    } catch {
      /* corrupted or unavailable storage: start from defaults */
    }
    if (fragment.current === null) {
      fragment.current = window.location.hash;
      if (fragment.current.startsWith(SHARE_PREFIX)) {
        // A reload should not apply the link again, and the address bar stays readable.
        window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
      }
    }
    if (!fragment.current.startsWith(SHARE_PREFIX)) {
      setHydrated();
      return;
    }
    // Results wait until the shared settings are in place (hydrated stays false until then).
    let cancelled = false;
    decodeShare(fragment.current)
      .then((payload) => {
        const incoming = stateFromShare(payload);
        if (!incoming) throw new Error("not a shared workspace");
        if (cancelled) return;
        dispatch({ type: "hydrate", value: incoming });
        setShared({ status: "loaded", previous: local ?? DEFAULT_STATE });
      })
      .catch(() => {
        if (!cancelled) setShared({ status: "unreadable" });
      })
      .finally(() => {
        if (!cancelled) setHydrated();
      });
    return () => {
      cancelled = true;
    };
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
  const dismissShared = useCallback(() => setShared(null), []);
  const restoreBeforeShare = useCallback(() => {
    if (shared?.status === "loaded") dispatch({ type: "hydrate", value: shared.previous });
    setShared(null);
  }, [shared]);

  const value = useMemo(
    () => ({
      state,
      hydrated,
      setUniverse,
      setEstimation,
      setObjective,
      setConstraints,
      setWorking,
      submit,
      reset,
      shared,
      dismissShared,
      restoreBeforeShare,
    }),
    [state, hydrated, setUniverse, setEstimation, setObjective, setConstraints, setWorking, submit, reset, shared, dismissShared, restoreBeforeShare],
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
