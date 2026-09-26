"use client";

import type { BlackLittermanIn, ViewIn } from "@/lib/api/types";

import { Button, Field, NumberInput, Select } from "./ui";

const MAX_VIEWS = 20;
export const DEFAULT_BLACK_LITTERMAN: BlackLittermanIn = { prior: "equal_weight", risk_aversion: 2.5, tau: 0.05, views: [] };

type Row = { a: string; b: string | null; q: number; c: number | null };

function toRow(v: ViewIn): Row {
  const entries = Object.entries(v.weights);
  const long = entries.find(([, w]) => w > 0)?.[0] ?? entries[0]?.[0] ?? "";
  const short = entries.find(([, w]) => w < 0)?.[0] ?? null;
  return { a: long, b: short, q: v.expected_return, c: v.confidence ?? null };
}

function toView(r: Row): ViewIn {
  const weights: Record<string, number> = { [r.a]: 1 };
  if (r.b) weights[r.b] = -1;
  return { weights, expected_return: r.q, confidence: r.c };
}

/** Prior, risk aversion and investor views for the Black–Litterman estimator. */
export function BlackLittermanEditor({
  value,
  tickers,
  capsAvailable,
  onChange,
}: {
  value: BlackLittermanIn | null | undefined;
  tickers: string[];
  /** Whether the dataset provides market capitalisations. */
  capsAvailable: boolean;
  onChange: (v: BlackLittermanIn) => void;
}) {
  const bl: BlackLittermanIn = { ...DEFAULT_BLACK_LITTERMAN, ...(value ?? {}) };
  const rows = (bl.views ?? []).map(toRow);
  const setRows = (next: Row[]) => onChange({ ...bl, views: next.map(toView) });
  const update = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-3 rounded-md border border-line p-2.5">
      <Field
        label="Prior (equilibrium) weights"
        htmlFor="bl-prior"
        hint="Returns are first set so that these weights would be optimal; views then move them. Market capitalisations come from the dataset (Ken French industries, or a market_cap column in your upload)."
      >
        <Select id="bl-prior" value={bl.prior === "custom" ? "market_cap" : bl.prior} onChange={(e) => onChange({ ...bl, prior: e.target.value as BlackLittermanIn["prior"] })}>
          <option value="equal_weight">Equal weights</option>
          <option value="market_cap" disabled={!capsAvailable && bl.prior !== "market_cap"}>
            Market capitalisation{capsAvailable ? "" : " (not in this dataset)"}
          </option>
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Risk aversion δ" htmlFor="bl-delta" hint="2.5 is conventional.">
          <NumberInput id="bl-delta" value={bl.risk_aversion ?? 2.5} onChange={(v) => onChange({ ...bl, risk_aversion: v ?? 2.5 })} min={0.1} max={20} />
        </Field>
        <Field label="Uncertainty τ" htmlFor="bl-tau" hint="Typically 0.01–0.1.">
          <NumberInput id="bl-tau" value={bl.tau ?? 0.05} onChange={(v) => onChange({ ...bl, tau: v ?? 0.05 })} min={0.001} max={1} />
        </Field>
      </div>
      <div>
        <p className="mb-1.5 text-xs font-medium text-ink-2">Views ({rows.length})</p>
        {rows.length === 0 && <p className="text-xs text-muted">No views: expected returns are the equilibrium returns.</p>}
        <ul className="space-y-2">
          {rows.map((r, i) => (
            <li key={i} className="space-y-1.5 rounded border border-line bg-surface-2/50 p-2 text-xs">
              <div className="flex items-center gap-1.5">
                <Select aria-label={`View ${i + 1} asset`} className="h-8 text-xs" value={r.a} onChange={(e) => update(i, { a: e.target.value })}>
                  {tickers.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </Select>
                <Select
                  aria-label={`View ${i + 1} type`}
                  className="h-8 text-xs"
                  value={r.b ?? ""}
                  onChange={(e) => update(i, { b: e.target.value || null })}
                >
                  <option value="">returns</option>
                  {tickers
                    .filter((t) => t !== r.a)
                    .map((t) => (
                      <option key={t} value={t}>
                        outperforms {t}
                      </option>
                    ))}
                </Select>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-32 shrink-0">
                  <NumberInput ariaLabel={`View ${i + 1} return`} value={r.q} onChange={(v) => update(i, { q: v ?? 0 })} scale={100} suffix="%/yr" min={-100} max={200} />
                </div>
                <Select
                  aria-label={`View ${i + 1} confidence`}
                  className="h-8 min-w-0 flex-1 text-xs"
                  value={r.c == null ? "" : String(r.c)}
                  onChange={(e) => update(i, { c: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">Default</option>
                  <option value="0.25">25% sure</option>
                  <option value="0.5">50% sure</option>
                  <option value="0.75">75% sure</option>
                  <option value="1">Certain</option>
                </Select>
                <Button size="sm" variant="ghost" aria-label={`Remove view ${i + 1}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  ×
                </Button>
              </div>
            </li>
          ))}
        </ul>
        <Button
          size="sm"
          variant="secondary"
          className="mt-2"
          disabled={tickers.length === 0 || rows.length >= MAX_VIEWS}
          onClick={() => setRows([...rows, { a: tickers[0] ?? "", b: null, q: 0.08, c: null }])}
        >
          Add view
        </Button>
      </div>
    </div>
  );
}
