import { date, humanise, money, month, num, pct, signedPct } from "./format";

describe("format", () => {
  it("formats percentages and handles missing values", () => {
    expect(pct(0.1234)).toBe("12.34%");
    expect(pct(null)).toBe("n/a");
    expect(pct(Number.NaN)).toBe("n/a");
    expect(signedPct(0.015)).toBe("+1.50%");
    expect(signedPct(-0.015)).toBe("−1.50%");
    expect(signedPct(0)).toBe("0.00%");
  });
  it("formats numbers, money and dates", () => {
    expect(num(1234.5, 1)).toBe("1,234.5");
    expect(money(10000)).toBe("$10,000");
    expect(date("2024-03-05")).toBe("5 Mar 2024");
    expect(humanise("max_sharpe")).toBe("Max sharpe");
  });
});

describe("pct rounding", () => {
  it("never shows negative zero", () => {
    expect(pct(-1e-7, 1)).toBe("0.0%");
  });
});

import { niceAxis } from "@/components/charts";

describe("niceAxis", () => {
  it("produces round bounds and ticks", () => {
    expect(niceAxis(0, 0.37)).toEqual({ min: 0, max: 0.4, ticks: [0, 0.1, 0.2, 0.3, 0.4] });
    expect(niceAxis(0, 0.2).ticks).toEqual([0, 0.05, 0.1, 0.15, 0.2]);
    const a = niceAxis(-0.013, 0.25);
    expect(a.min).toBeCloseTo(-0.05);
    expect(a.ticks).toContain(0);
  });
});

describe("signed formats", () => {
  it("drop the sign when the rounded value is zero", () => {
    expect(signedPct(-0.00001, 1)).toBe("0.0%");
    expect(signedPct(0.00001, 1)).toBe("0.0%");
  });
  it("formats months", () => {
    expect(month("2026-10")).toBe("Oct 2026");
    expect(month(null)).toBe("n/a");
  });
});
