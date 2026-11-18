// Records the worked example on the landing page: real optimisation results from the
// running app on the synthetic demo data, one for each limit on a single asset's weight.
// Nothing in the file is written by hand; rerun this whenever the engine, the demo data
// or the wording of the explanations changes.
// Usage: start the API (port 8000) and the web app (port 3000), then
//   node scripts/capture-example.mjs
import { writeFileSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = new URL("../src/lib/landing-example.json", import.meta.url).pathname;

// Eight of the demo's assets, one from each kind of holding.
const TICKERS = ["NWS.SYN", "MDC.SYN", "ARB.SYN", "PTR.SYN", "GRD.SYN", "HRV.SYN", "GOVB.SYN", "GOLD.SYN"];
// The most allowed in one asset; 1 is no limit.
const LIMITS = [0.2, 0.3, 0.4, 1];

const universe = { dataset_id: "demo", tickers: TICKERS, start: "2016-01-01", end: "2025-12-31", frequency: "daily", currency_hedged: false };
const estimation = { mean_estimator: "historical", covariance_estimator: "ledoit_wolf", risk_free_rate: 0.02 };
const objective = { objective: "max_sharpe", cvar_confidence: 0.95 };

function constraints(limit) {
  return {
    min_weight: 0,
    max_weight: limit,
    asset_bounds: {},
    sector_limits: [],
    excluded_assets: [],
    excluded_sectors: [],
    min_esg_score: null,
    esg_tilt: 0,
    exclude_unscored_assets: false,
    max_gross_exposure: null,
    tracking_error: null,
  };
}

/** The fragment of a shareable link (src/lib/share.ts): deflate-raw, base64url. */
async function shareFragment(payload) {
  const stream = new Blob([JSON.stringify(payload)]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  const packed = Buffer.from(await new Response(stream).arrayBuffer());
  return "#share=" + packed.toString("base64url");
}

const cases = [];
for (const limit of LIMITS) {
  const request = { universe, estimation, objective, constraints: constraints(limit), stability_resamples: 0, seed: null };
  const res = await fetch(`${BASE}/api/v1/optimise`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`optimise with limit ${limit}: HTTP ${res.status} ${await res.text()}`);
  const out = await res.json();
  const share = { v: 1, universe, estimation, objective, constraints: request.constraints, working: null, requests: { optimise: request } };
  cases.push({
    limit,
    href: "/app/optimise" + (await shareFragment(share)),
    sharpe_ratio: out.result.sharpe_ratio,
    // The engine's own sentence, which gives the ratio with the figures it comes from.
    sharpe_statement: out.explanation.statements.find((t) => t.startsWith("Expected Sharpe ratio")),
    holdings: out.result.holdings.map((h) => ({
      ticker: h.ticker,
      name: h.name,
      sector: h.sector,
      weight: h.weight,
      status: h.status,
      reason: h.reason,
    })),
    warnings: out.explanation.warnings,
    assumptions: out.explanation.assumptions,
  });
  console.log(`limit ${limit}: Sharpe ratio ${out.result.sharpe_ratio.toFixed(2)}`);
}

writeFileSync(OUT, JSON.stringify({ source: "Synthetic demo data", cases }, null, 2) + "\n");
console.log(`saved ${OUT}`);
