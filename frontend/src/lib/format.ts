/**
 * Number formatting only. No financial calculations belong in the frontend:
 * every value displayed is computed and tested in the backend quant engine.
 */

const DASH = "n/a";

export function pct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  const s = (x * 100).toFixed(digits);
  // Avoid "-0.0%" for tiny negative values that round to zero.
  return `${Number(s) === 0 ? (0).toFixed(digits) : s}%`;
}

export function signedPct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  const s = (Math.abs(x) * 100).toFixed(digits);
  const zero = Number(s) === 0;
  return `${zero ? "" : x > 0 ? "+" : "−"}${s}%`;
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  return x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedNum(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  const s = Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const zero = Number(s.replace(/,/g, "")) === 0;
  return `${zero ? "" : x > 0 ? "+" : "−"}${s}`;
}

export function money(x: number | null | undefined, compact = false): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  return x.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: compact ? 1 : 0,
    notation: compact ? "compact" : "standard",
  });
}

export function date(d: string | null | undefined): string {
  if (!d) return DASH;
  const [y, m, day] = d.slice(0, 10).split("-").map(Number);
  if (!y || !m || !day) return d;
  return new Date(Date.UTC(y, m - 1, day)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** "2026-10" as "Oct 2026". */
export function month(m: string | null | undefined): string {
  if (!m) return DASH;
  const [y, mo] = m.split("-").map(Number);
  if (!y || !mo) return m;
  return new Date(Date.UTC(y, mo - 1, 1)).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function humanise(s: string): string {
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export const OBJECTIVE_LABELS: Record<string, string> = {
  min_volatility: "Minimum volatility",
  max_sharpe: "Maximum Sharpe ratio",
  target_return: "Target return",
  target_volatility: "Target volatility",
  max_utility: "Maximum utility",
  min_cvar: "Minimum CVaR (tail loss)",
};

export const ESTIMATOR_LABELS: Record<string, string> = {
  historical: "Historical mean",
  bayes_stein: "Bayes–Stein shrinkage",
  black_litterman: "Black–Litterman (equilibrium + views)",
  sample: "Sample covariance",
  ledoit_wolf: "Ledoit–Wolf (identity target)",
  ledoit_wolf_constant_correlation: "Ledoit–Wolf (constant correlation)",
};
