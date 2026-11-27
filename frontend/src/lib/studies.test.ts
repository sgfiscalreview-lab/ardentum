import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { REFERENCES } from "./study-references";
import { currencyHedging, oneOverN, oneOverNGrowth, PROMISE_SETTINGS, promisedVersusRealised, promiseRecords, STUDIES } from "./studies";

// The research notes state conclusions in words around numbers drawn from the recorded
// study output. The studies are rerun whenever their code changes, so these checks make a
// rerun that overturns a stated conclusion fail here, before the text can mislead.

const ALPHA = 0.05;

describe("note 1: optimal versus naive diversification", () => {
  const r = oneOverN();
  const settings = Object.keys(r);
  const optimised = (s: string) => Object.keys(r[s]!).filter((n) => !n.startsWith("1/N"));
  const main = r["window 120m, costs 50bp"]!;

  it("covers the four specifications and six strategies the text describes", () => {
    expect(settings).toEqual(["window 60m, costs 0bp", "window 60m, costs 50bp", "window 120m, costs 0bp", "window 120m, costs 50bp"]);
    for (const s of settings) expect(Object.keys(r[s]!)).toHaveLength(6);
  });

  it("no optimised strategy differs significantly from 1/N in any specification, by either test", () => {
    for (const s of settings)
      for (const n of optimised(s)) {
        const f = r[s]![n]!.full;
        expect(f.p_value_vs_1n, `${s} ${n}`).toBeGreaterThan(ALPHA);
        expect(f.p_value_vs_1n_robust, `${s} ${n}`).toBeGreaterThan(ALPHA);
      }
  });

  it("minimum variance beats 1/N in every specification, with smaller drawdowns", () => {
    for (const s of settings)
      for (const n of ["Minimum variance (sample)", "Minimum variance (shrinkage)"]) {
        expect(r[s]![n]!.full.sharpe_minus_1n, `${s} ${n}`).toBeGreaterThan(0);
        expect(r[s]![n]!.full.max_drawdown).toBeGreaterThan(r[s]!["1/N (equal weight)"]!.full.max_drawdown);
      }
  });

  it("maximum Sharpe trails 1/N once costs are charged, and before 2005 in every specification", () => {
    for (const s of settings)
      for (const n of ["Maximum Sharpe (sample)", "Maximum Sharpe (shrinkage)"]) {
        if (s.endsWith("50bp")) expect(r[s]![n]!.full.sharpe_minus_1n, `${s} ${n}`).toBeLessThan(0);
        expect(r[s]![n]!["1970-2004"].sharpe_minus_1n, `${s} ${n}`).toBeLessThan(0);
      }
  });

  it("since 2005 the maximum-Sharpe gap has all but closed and minimum variance keeps a small lead (main specification)", () => {
    for (const n of ["Maximum Sharpe (sample)", "Maximum Sharpe (shrinkage)"]) expect(Math.abs(main[n]!["2005-latest"].sharpe_minus_1n)).toBeLessThan(0.05);
    for (const n of ["Minimum variance (sample)", "Minimum variance (shrinkage)"]) expect(main[n]!["2005-latest"].sharpe_minus_1n).toBeGreaterThan(0);
  });

  it("no subperiod difference is significant (main specification)", () => {
    for (const n of optimised("window 120m, costs 50bp"))
      for (const period of ["1970-2004", "2005-latest"] as const) expect(main[n]![period].p_value_vs_1n_robust).toBeGreaterThan(ALPHA);
  });

  it("a longer window lowers turnover for every optimised strategy, and maximum Sharpe trades most", () => {
    for (const n of optimised("window 60m, costs 0bp"))
      expect(r["window 120m, costs 0bp"]![n]!.annual_turnover).toBeLessThan(r["window 60m, costs 0bp"]![n]!.annual_turnover);
    const turnover = optimised("window 120m, costs 50bp").map((n) => [n, main[n]!.annual_turnover] as const);
    const top2 = [...turnover].sort((a, b) => b[1] - a[1]).slice(0, 2).map((x) => x[0]);
    expect(top2.sort()).toEqual(["Maximum Sharpe (sample)", "Maximum Sharpe (shrinkage)"]);
  });

  it("minimum variance lost substantially less than 1/N in 2008, and every strategy fell in the Covid crash", () => {
    const base = main["1/N (equal weight)"]!.crisis_returns;
    for (const n of ["Minimum variance (sample)", "Minimum variance (shrinkage)"])
      expect(main[n]!.crisis_returns["2008 financial crisis"]).toBeGreaterThan(base["2008 financial crisis"]! + 0.05);
    for (const n of Object.keys(main)) expect(main[n]!.crisis_returns["2020 Covid crash"]).toBeLessThan(-0.1);
  });

  it("records the growth of $1 for every strategy, starting in January 1970", () => {
    const g = oneOverNGrowth();
    expect(g.dates[0]).toBe("1970-01-31");
    expect(Object.keys(g.wealth).sort()).toEqual(Object.keys(main).sort());
    for (const v of Object.values(g.wealth)) expect(v).toHaveLength(g.dates.length);
  });
});

describe("note 2: hedging the dollar", () => {
  const h = currencyHedging();
  const investors = ["euro", "sterling"] as const;

  it("full hedging changes the volatility of the US market by less than 5% for both investors", () => {
    for (const inv of investors) expect(Math.abs(h[inv].assets["US market"]!.risk_change_from_hedging)).toBeLessThan(0.05);
  });

  it("US shares and the dollar are negatively correlated for every portfolio and both investors", () => {
    for (const inv of investors) {
      expect(Object.keys(h[inv].assets)).toHaveLength(13);
      for (const [a, v] of Object.entries(h[inv].assets)) expect(v.corr_us_stocks_vs_dollar, `${inv} ${a}`).toBeLessThan(0);
    }
  });

  it("hedging changed volatility by a few percent at most and lowered the average return everywhere", () => {
    for (const inv of investors)
      for (const [a, v] of Object.entries(h[inv].assets)) {
        expect(Math.abs(v.risk_change_from_hedging), `${inv} ${a}`).toBeLessThan(0.1);
        expect(v.mean_hedged_annual, `${inv} ${a}`).toBeLessThan(v.mean_unhedged_annual);
      }
  });

  it("the risk-minimising hedge ratio for the US market lies between 0 and 1", () => {
    for (const inv of investors) {
      const x = h[inv].assets["US market"]!.min_variance_hedge_ratio;
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(1);
    }
  });

  it("in each crisis the dollar rose and the unhedged investor lost less than the hedged one", () => {
    for (const inv of investors)
      for (const [c, v] of Object.entries(h[inv].crises_us_market)) {
        expect(v.currency, `${inv} ${c}`).toBeGreaterThan(0);
        expect(v.unhedged, `${inv} ${c}`).toBeGreaterThan(v.hedged);
      }
  });

  it("the rolling hedge ratio was near or above one in the mid-2000s and negative for both investors in one run of recent years", () => {
    for (const inv of investors) expect(h[inv].rolling_5y_hedge_ratio_us_market["2005"]).toBeGreaterThan(0.9);
    const years = Object.keys(h.euro.rolling_5y_hedge_ratio_us_market);
    const both = years.filter((y) => investors.every((inv) => (h[inv].rolling_5y_hedge_ratio_us_market[y] ?? 0) < 0)).map(Number);
    expect(both.length).toBeGreaterThan(0);
    expect(both[both.length - 1]! - both[0]!).toBe(both.length - 1); // one unbroken run
    expect(both[0]).toBeGreaterThan(2015);
  });
});

describe("note 3: the optimiser's promise", () => {
  const r = promisedVersusRealised();
  const [s60, k60, s120, k120] = PROMISE_SETTINGS.map((k) => r[k]!);

  it("the promise exceeds what is delivered in every setting", () => {
    for (const k of PROMISE_SETTINGS) expect(r[k]!.mean_promised_sharpe, k).toBeGreaterThan(r[k]!.delivered_sharpe);
  });

  it("with sample estimates less than half the promise is delivered, and the 60-month gap is the wider", () => {
    for (const v of [s60!, s120!]) expect(v.delivered_sharpe).toBeLessThan(v.mean_promised_sharpe / 2);
    expect(s60!.promise_minus_delivered).toBeGreaterThan(s120!.promise_minus_delivered);
  });

  it("shrinkage narrows the gap in both windows", () => {
    expect(k60!.promise_minus_delivered).toBeLessThan(s60!.promise_minus_delivered);
    expect(k120!.promise_minus_delivered).toBeLessThan(s120!.promise_minus_delivered);
  });

  it("the delivered ratio is below equal weights in every setting, never significantly", () => {
    for (const k of PROMISE_SETTINGS) {
      expect(r[k]!.delivered_sharpe, k).toBeLessThan(r[k]!.equal_weight_sharpe_same_months);
      expect(r[k]!.p_value_delivered_vs_equal_weight, k).toBeGreaterThan(ALPHA);
      expect(r[k]!.p_value_delivered_vs_equal_weight_robust, k).toBeGreaterThan(ALPHA);
    }
  });

  it("a year's promise is essentially unrelated to the next year", () => {
    for (const k of PROMISE_SETTINGS) expect(Math.abs(r[k]!.corr_promised_vs_next_12_months), k).toBeLessThan(0.2);
  });

  it("sample estimates never left a year without a portfolio", () => {
    expect(s60!.skipped_no_portfolio_beats_tbill).toBe(0);
    expect(s120!.skipped_no_portfolio_beats_tbill).toBe(0);
  });

  it("every portfolio on the illustrated frontier turned out riskier and less rewarding than promised", () => {
    const il = r.illustration;
    expect(il.realised).toHaveLength(il.promised.length);
    il.promised.forEach(([vol, ret], i) => {
      expect(il.realised[i]![0]).toBeGreaterThan(vol);
      expect(il.realised[i]![1]).toBeLessThan(ret);
    });
  });

  it("records each year's portfolio for both estimators and windows", () => {
    const rec = promiseRecords();
    for (const lookback of [60, 120]) expect(rec.filter((x) => x.lookback === lookback).length).toBeGreaterThan(100);
  });
});

describe("the notes' citations", () => {
  const dir = path.join(process.cwd(), "src", "app", "research", "studies");

  it.each(STUDIES.map((s) => s.slug))("%s cites only listed works and lists only cited ones", (slug) => {
    const src = fs.readFileSync(path.join(dir, slug, "page.tsx"), "utf8");
    const cited = new Set([...src.matchAll(/<Cite k="(\w+)"/g)].map((m) => m[1]!));
    const block = /const REFS: RefKey\[\] = \[([\s\S]*?)\];/.exec(src)?.[1] ?? "";
    const listed = new Set([...block.matchAll(/"(\w+)"/g)].map((m) => m[1]!));
    expect(cited.size).toBeGreaterThan(5);
    expect([...cited].filter((k) => !listed.has(k))).toEqual([]);
    expect([...listed].filter((k) => !cited.has(k))).toEqual([]);
    for (const k of listed) expect(REFERENCES, k).toHaveProperty(k);
  });

  it("uses no em dashes", () => {
    for (const s of STUDIES) expect(fs.readFileSync(path.join(dir, s.slug, "page.tsx"), "utf8")).not.toContain("—");
    for (const ref of Object.values(REFERENCES)) expect(ref.full).not.toContain("—");
  });
});
