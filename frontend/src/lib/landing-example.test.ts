import { describe, expect, it } from "vitest";

import EXAMPLE from "./landing-example.json";
import { decodeShare } from "./share";
import { stateFromShare } from "./workspace";

// The landing page's worked example is recorded from the running app
// (scripts/capture-example.mjs). These checks catch a file edited by hand or cut short.
describe("landing page example", () => {
  it("offers the limits the page shows, the default among them", () => {
    expect(EXAMPLE.cases.map((c) => c.limit)).toEqual([0.2, 0.3, 0.4, 1]);
    expect(EXAMPLE.source).toBe("Synthetic demo data");
  });

  it.each(EXAMPLE.cases)("limit $limit: weights add up, respect the limit and each has a reason", (c) => {
    expect(c.holdings).toHaveLength(8);
    expect(c.holdings.reduce((sum, h) => sum + h.weight, 0)).toBeCloseTo(1, 6);
    for (const h of c.holdings) {
      expect(h.ticker.endsWith(".SYN")).toBe(true);
      expect(h.weight).toBeGreaterThanOrEqual(0);
      expect(h.weight).toBeLessThanOrEqual(c.limit + 1e-6);
      expect(h.reason.length).toBeGreaterThan(20);
      expect(h.reason).not.toContain("—");
    }
    // The sentence shown gives the ratio and the three figures that reproduce it.
    const found = /^Expected Sharpe ratio ([\d.]+): .*\(([\d.]+)% less ([\d.]+)%\), divided by the volatility \(([\d.]+)%\)\.$/.exec(c.sharpe_statement);
    expect(found).not.toBeNull();
    const [shown, ret, rf, vol] = found!.slice(1).map(Number) as [number, number, number, number];
    expect(shown).toBeCloseTo(c.sharpe_ratio, 2);
    expect(Math.abs((ret - rf) / vol - c.sharpe_ratio)).toBeLessThan(0.002);
    expect(c.assumptions.length).toBeGreaterThan(0);
  });

  it.each(EXAMPLE.cases)("limit $limit: its link opens the same settings in the workspace", async (c) => {
    const [path, fragment] = c.href.split("#");
    expect(path).toBe("/app/optimise");
    const state = stateFromShare(await decodeShare("#" + fragment));
    expect(state?.universe.dataset_id).toBe("demo");
    expect(state?.universe.tickers).toEqual(c.holdings.map((h) => h.ticker));
    expect(state?.constraints.max_weight).toBe(c.limit);
    expect(state?.requests.optimise).toBeDefined();
  });
});
