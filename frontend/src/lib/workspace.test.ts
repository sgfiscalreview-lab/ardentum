import { describe, expect, it } from "vitest";

import { DEFAULT_STATE, restoreState } from "./workspace";

describe("restoreState", () => {
  it("fills fields added after the settings were saved", () => {
    const old = { ...DEFAULT_STATE, universe: { dataset_id: "demo", tickers: ["A.SYN"], frequency: "monthly" }, objective: { objective: "min_volatility" } };
    const s = restoreState(JSON.parse(JSON.stringify(old)));
    expect(s?.universe.currency_hedged).toBe(false);
    expect(s?.universe.frequency).toBe("monthly");
    expect(s?.objective).toEqual({ objective: "min_volatility", cvar_confidence: 0.95 });
  });

  it("repairs malformed parts and rejects other versions", () => {
    const s = restoreState({ ...DEFAULT_STATE, constraints: { asset_bounds: null, sector_limits: "x" }, requests: [] });
    expect(s?.constraints.asset_bounds).toEqual({});
    expect(s?.constraints.sector_limits).toEqual([]);
    expect(s?.constraints.max_weight).toBe(DEFAULT_STATE.constraints.max_weight);
    expect(s?.requests).toEqual({});
    expect(restoreState({ ...DEFAULT_STATE, version: 0 })).toBeNull();
    expect(restoreState("junk")).toBeNull();
    expect(restoreState({ ...DEFAULT_STATE, universe: { tickers: [] } })?.universe.tickers).toEqual(DEFAULT_STATE.universe.tickers);
  });
});
