import { balancedWeights, KF12, PRESETS } from "./presets";
import { DEFAULT_TICKERS, restoreState, sharePayload, stateFromShare } from "./workspace";

const sum = (w: Record<string, number>) => Object.values(w).reduce((a, b) => a + b, 0);

describe("starting examples", () => {
  it("60/40 puts 60% in shares and 40% in bonds", () => {
    const w = balancedWeights();
    expect(sum(w)).toBeCloseTo(1, 12);
    expect((w["GOVB.SYN"] ?? 0) + (w["CORP.SYN"] ?? 0)).toBeCloseTo(0.4, 12);
    expect(w["GOLD.SYN"]).toBeUndefined();
    expect(Object.keys(w).every((t) => DEFAULT_TICKERS.includes(t))).toBe(true);
  });

  it("each example opens its page with a calculation ready", () => {
    const page: Record<string, string> = { "/app/compare": "compare", "/app/optimise": "optimise", "/app/crises": "stress", "/app/factors": "factors" };
    for (const p of PRESETS) {
      const s = p.build();
      expect(s.requests[page[p.href] as keyof typeof s.requests]).toBeDefined();
      expect(s.universe.dataset_id).toBe(p.real ? "kf12" : "demo");
      if (s.working) expect(sum(s.working.weights)).toBeCloseTo(1, 12);
      // A saved or shared copy reads back the same.
      expect(restoreState(JSON.parse(JSON.stringify(s)))).toEqual(s);
    }
  });

  it("does not change the defaults it starts from", () => {
    const before = JSON.stringify(PRESETS[1]!.build());
    PRESETS.forEach((p) => p.build());
    expect(JSON.stringify(PRESETS[1]!.build())).toBe(before);
    expect(KF12).toHaveLength(12);
  });

  it("travels in a shared link", () => {
    const s = PRESETS[2]!.build();
    const back = stateFromShare(JSON.parse(JSON.stringify(sharePayload(s, ["stress"]))));
    expect(back?.requests.stress).toEqual(s.requests.stress);
  });
});
