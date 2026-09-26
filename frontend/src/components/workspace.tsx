"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { api, ApiError, unwrap } from "@/lib/api/client";
import type { DataWindowOut, DatasetOut } from "@/lib/api/types";
import { date as fmtDate, ESTIMATOR_LABELS, pct } from "@/lib/format";
import { useWorkspace, type PageKey } from "@/lib/workspace";

import { Badge, Button, Callout, cx, Disclosure, Spinner } from "./ui";

export const STEPS: { href: string; label: string; hint: string }[] = [
  { href: "/app", label: "Universe", hint: "Data, assets, window" },
  { href: "/app/analytics", label: "Analytics", hint: "History, risk, correlation" },
  { href: "/app/optimise", label: "Optimise", hint: "Objective & constraints" },
  { href: "/app/frontier", label: "Frontier", hint: "Risk–return trade-off" },
  { href: "/app/esg", label: "ESG impact", hint: "Cost of ESG constraints" },
  { href: "/app/simulate", label: "Monte Carlo", hint: "Range of outcomes" },
  { href: "/app/backtest", label: "Backtest", hint: "Out-of-sample history" },
  { href: "/app/compare", label: "Compare", hint: "Side by side" },
];

// --------------------------------------------------------------------------- data hooks

export function useDataset(datasetId: string) {
  return useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => unwrap(api.GET("/api/v1/datasets/{dataset_id}", { params: { path: { dataset_id: datasetId } } })),
  });
}

/**
 * Runs a deterministic computation for a workspace page. The last submitted
 * request is persisted in the workspace, so results survive navigation and
 * reloads (served from cache or recomputed identically).
 */
export function useComputation<Req, Res>(page: PageKey, fn: (req: Req, signal?: AbortSignal) => Promise<Res>) {
  const { state, submit, hydrated } = useWorkspace();
  const request = (state.requests[page] ?? null) as Req | null;
  const query = useQuery({
    queryKey: ["compute", page, request],
    queryFn: ({ signal }) => fn(request as Req, signal),
    enabled: hydrated && request !== null,
    placeholderData: keepPreviousData,
  });
  return {
    request,
    data: query.data,
    error: query.error as ApiError | Error | null,
    running: query.isFetching,
    stale: query.isPlaceholderData,
    run: (req: Req) => submit(page, req),
  };
}

// --------------------------------------------------------------------------- layout pieces

export function StepNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Workspace steps">
      <ol className="space-y-0.5">
        {STEPS.map((s, i) => {
          const active = pathname === s.href;
          return (
            <li key={s.href}>
              <Link
                href={s.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex items-start gap-2.5 rounded-md px-2 py-1.5",
                  active ? "bg-surface-2" : "hover:bg-surface-2/60",
                )}
              >
                <span
                  className={cx(
                    "mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                    active ? "bg-accent text-white" : "bg-surface-3 text-ink-2",
                  )}
                >
                  {i + 1}
                </span>
                <span className="min-w-0">
                  <span className={cx("block text-sm", active ? "font-medium text-ink" : "text-ink")}>{s.label}</span>
                  <span className="block truncate text-[11px] text-muted">{s.hint}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function MobileStepNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Workspace steps" className="-mx-4 mb-4 overflow-x-auto border-b border-line px-4 lg:hidden">
      <ul className="flex gap-1 pb-2">
        {STEPS.map((s) => (
          <li key={s.href}>
            <Link
              href={s.href}
              aria-current={pathname === s.href ? "page" : undefined}
              className={cx(
                "block whitespace-nowrap rounded-md px-2.5 py-1 text-xs",
                pathname === s.href ? "bg-surface-2 font-medium text-ink" : "text-ink-2",
              )}
            >
              {s.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function UniverseSummary() {
  const { state } = useWorkspace();
  const u = state.universe;
  const ds = useDataset(u.dataset_id);
  return (
    <div className="rounded-md border border-line bg-surface p-3 text-xs">
      <p className="font-medium text-ink">Current universe</p>
      <dl className="mt-2 space-y-1 text-ink-2">
        <div className="flex justify-between gap-2">
          <dt>Dataset</dt>
          <dd className="truncate text-right text-ink">{ds.data?.name ?? u.dataset_id}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Assets</dt>
          <dd className="text-ink tabular">{u.tickers.length}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Window</dt>
          <dd className="text-right text-ink">
            {u.start?.slice(0, 4) ?? "start"}–{u.end?.slice(0, 4) ?? "end"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Frequency</dt>
          <dd className="text-ink">{u.frequency}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Risk-free</dt>
          <dd className="text-ink tabular" title={state.estimation.risk_free_source ?? "Entered by the user"}>
            {pct(state.estimation.risk_free_rate)}
          </dd>
        </div>
        {u.base_currency && (
          <div className="flex justify-between gap-2">
            <dt>Currency</dt>
            <dd className="text-ink">{u.base_currency}</dd>
          </div>
        )}
      </dl>
      {ds.data?.is_synthetic && (
        <div className="mt-2">
          <Badge tone="synthetic" title="Fictional assets generated by a statistical model">
            Synthetic data
          </Badge>
        </div>
      )}
      {state.working && (
        <p className="mt-2 border-t border-line pt-2 text-ink-2">
          Working portfolio: <span className="font-medium text-ink">{state.working.name}</span>
        </p>
      )}
    </div>
  );
}

export function SyntheticBanner({ dataset }: { dataset: DatasetOut | undefined }) {
  if (!dataset?.is_synthetic) return null;
  return (
    <Callout tone="synthetic" title="Synthetic demo data" className="mb-4">
      Every asset, price and ESG score in this dataset is fictional and generated by a documented statistical model.
      Results illustrate the methods; they say nothing about real securities.{" "}
      <Link href="/research/data" className="text-accent-ink underline underline-offset-2">
        How the data is generated
      </Link>
    </Callout>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 max-w-3xl">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        <p className="mt-1 text-sm text-ink-2">{description}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

// --------------------------------------------------------------------------- results chrome

export function RunBar({
  onRun,
  running,
  label = "Run",
  disabled,
  note,
}: {
  onRun: () => void;
  running: boolean;
  label?: string;
  disabled?: boolean;
  note?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary" onClick={onRun} busy={running} disabled={disabled}>
        {label}
      </Button>
      {note && <span className="text-xs text-muted">{note}</span>}
    </div>
  );
}

export function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null;
  const title =
    error instanceof ApiError
      ? {
          infeasible: "No portfolio satisfies these constraints",
          insufficient_data: "Not enough data",
          invalid_input: "Check the inputs",
          validation_error: "Check the inputs",
          unauthorized: "Sign in required",
          not_configured: "Not available on this server",
          network_error: "Connection problem",
          undefined_metric: "Metric undefined",
          rate_limited: "Too many requests",
        }[error.type] ?? "Something went wrong"
      : "Something went wrong";
  return (
    <Callout tone="error" title={title} className="mb-4">
      {error.message}
    </Callout>
  );
}

export function Running({ running, children }: { running: boolean; children: ReactNode }) {
  return (
    <div className={cx("relative transition-opacity", running && "pointer-events-none opacity-60")} aria-busy={running}>
      {running && (
        <div className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink-2">
          <Spinner className="size-3" /> Computing…
        </div>
      )}
      {children}
    </div>
  );
}

export function DataNotes({ data, extra }: { data: DataWindowOut; extra?: string[] }) {
  const p = data.provenance;
  return (
    <Disclosure
      summary={
        <span className="flex flex-wrap items-center gap-2">
          Data &amp; provenance
          {p.is_synthetic && <Badge tone="synthetic">Synthetic</Badge>}
          {data.quality_warnings.length > 0 && <Badge tone="warn">{data.quality_warnings.length} data warning(s)</Badge>}
        </span>
      }
    >
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-2">
        <Row k="Source" v={p.source} />
        <Row k="Adjustment" v={p.adjustment} />
        <Row k="Window" v={`${fmtDate(data.start)} – ${fmtDate(data.end)}`} />
        <Row k="Observations" v={`${data.observations.toLocaleString()} ${data.frequency} returns (${data.periods_per_year}/year)`} />
        <Row k="Currency" v={data.currency} />
        {p.license_note && <Row k="Licence" v={p.license_note} />}
      </dl>
      {[...p.notes, ...data.quality_notes, ...(extra ?? [])].length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-ink-2">
          {[...p.notes, ...data.quality_notes, ...(extra ?? [])].map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {data.quality_warnings.length > 0 && (
        <Callout tone="warning" title="Data-quality warnings" className="mt-3">
          <ul className="list-disc pl-4">
            {data.quality_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}
    </Disclosure>
  );
}

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 text-ink-2">{k}</dt>
      <dd className="min-w-0 text-ink">{v}</dd>
    </div>
  );
}

export function EstimationNote({
  mean,
  cov,
  covShrinkage,
  meanShrinkage,
  rf,
}: {
  mean: string;
  cov: string;
  covShrinkage?: number | null;
  meanShrinkage?: number | null;
  rf: number;
}) {
  return (
    <p className="text-xs text-ink-2">
      Estimated with {ESTIMATOR_LABELS[mean] ?? mean}
      {meanShrinkage != null && ` (shrinkage ${meanShrinkage.toFixed(2)})`} and {ESTIMATOR_LABELS[cov] ?? cov}
      {covShrinkage != null && ` (shrinkage ${covShrinkage.toFixed(2)})`}; risk-free rate {pct(rf)}.
    </p>
  );
}

export function download(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** CSV serialisation with RFC 4180 quoting (no calculations). */
export function toCsv(rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return rows.map((r) => r.map(cell).join(",")).join("\n") + "\n";
}

export function ExportMenu({ name, json, csv }: { name: string; json: unknown; csv?: () => string }) {
  return (
    <div className="flex items-center gap-1">
      {csv && (
        <Button size="sm" variant="ghost" onClick={() => download(`${name}.csv`, csv(), "text/csv")}>
          Export CSV
        </Button>
      )}
      <Button size="sm" variant="ghost" onClick={() => download(`${name}.json`, JSON.stringify(json, null, 2), "application/json")}>
        Export JSON
      </Button>
    </div>
  );
}
