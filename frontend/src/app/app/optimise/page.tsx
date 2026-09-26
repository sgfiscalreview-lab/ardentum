"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { BarList, ChartFrame, DataTable } from "@/components/charts";
import { ConstraintsPanel, ObjectivePanel, StatusBadge } from "@/components/forms";
import { Button, Callout, Card, Checkbox, EmptyState, Field, Input, Stat, Table, Td, Th } from "@/components/ui";
import {
  DataNotes,
  ErrorCallout,
  EstimationNote,
  ExportMenu,
  PageHeader,
  RunBar,
  Running,
  SyntheticBanner,
  toCsv,
  useComputation,
  useDataset,
} from "@/components/workspace";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { OptimiseRequest, OptimiseResponse } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { num, OBJECTIVE_LABELS, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

export default function OptimisePage() {
  const { state, setObjective, setConstraints, setWorking } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const [stability, setStability] = useState(false);
  const { data, error, running, run, request } = useComputation<OptimiseRequest, OptimiseResponse>("optimise", (req) =>
    unwrap(api.POST("/api/v1/optimise", { body: req })),
  );

  const submit = () =>
    run({
      universe: state.universe,
      estimation: state.estimation,
      objective: state.objective,
      constraints: state.constraints,
      stability_resamples: stability ? 40 : 0,
      seed: stability ? 12345 : null,
    });

  return (
    <>
      <PageHeader
        title="Optimise"
        description="Mean–variance optimisation under explicit constraints. The model's reasoning — binding constraints, risk contributions and why each asset is or is not held — is shown with every result."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Objective">
            <ObjectivePanel value={state.objective} onChange={setObjective} />
          </Card>
          <Card title="Constraints">
            <ConstraintsPanel value={state.constraints} onChange={setConstraints} assets={ds.data?.assets ?? []} tickers={state.universe.tickers} />
          </Card>
          <Card>
            <div className="space-y-3">
              <Checkbox
                checked={stability}
                onChange={setStability}
                label="Test weight stability"
                hint="Re-optimises on 40 bootstrap resamples of the history to show how much the weights depend on estimation noise (slower)."
              />
              <RunBar running={running} label="Optimise" onRun={submit} disabled={state.universe.tickers.length < 2} note={state.universe.tickers.length < 2 ? "Select at least 2 assets." : undefined} />
            </div>
          </Card>
        </aside>

        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data ? (
            <EmptyState title="No optimisation yet">
              Choose an objective and constraints, then run the optimiser. Results are deterministic: the same inputs always give the same portfolio.
            </EmptyState>
          ) : (
            <Running running={running}>
              <Results data={data} request={request} onUse={() => {
                setWorking({
                  name: `${OBJECTIVE_LABELS[data.result.objective] ?? data.result.objective} (optimised)`,
                  datasetId: data.data.dataset_id,
                  weights: Object.fromEntries(data.result.holdings.filter((h) => Math.abs(h.weight) > 1e-9).map((h) => [h.ticker, h.weight])),
                  source: "optimiser",
                  spec: request as unknown as Record<string, unknown>,
                });
              }} usingNow={state.working?.source === "optimiser"} rf={state.estimation.risk_free_rate ?? 0} />
            </Running>
          )}
        </div>
      </div>
    </>
  );
}

function Results({
  data,
  request,
  onUse,
  usingNow,
  rf,
}: {
  data: OptimiseResponse;
  request: OptimiseRequest | null;
  onUse: () => void;
  usingNow: boolean;
  rf: number;
}) {
  const r = data.result;
  const ex = data.explanation;
  const held = r.holdings.filter((h) => Math.abs(h.weight) > 1e-9).sort((a, b) => b.weight - a.weight);
  const binding = r.diagnostics.filter((d) => d.binding && d.kind !== "excluded" && d.kind !== "asset_lower");
  const csv = () =>
    toCsv([
      ["ticker", "name", "sector", "weight", "expected_return", "volatility", "risk_contribution_pct", "esg_score", "status", "reason"],
      ...r.holdings.map((h) => [h.ticker, h.name, h.sector, h.weight, h.expected_return, h.volatility, h.risk_contribution_pct, h.esg_score, h.status, h.reason]),
    ]);
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-2">{OBJECTIVE_LABELS[r.objective]}</p>
            <p className="mt-1 text-lg font-semibold text-ink">{ex.headline}</p>
            <p className="mt-1 text-sm text-ink-2">{ex.objective_summary}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant={usingNow ? "secondary" : "primary"} size="sm" onClick={onUse}>
              {usingNow ? "Update working portfolio" : "Use as working portfolio"}
            </Button>
            <SaveButton data={data} request={request} />
            <ExportMenu name="ardentum-optimised-portfolio" json={data} csv={csv} />
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-6">
          <Stat label="Expected return" value={pct(r.expected_return)} sub="annual, arithmetic (estimate)" />
          <Stat label="Expected volatility" value={pct(r.volatility)} sub="annual (estimate)" />
          <Stat label="Sharpe ratio" value={r.sharpe_ratio == null ? "—" : num(r.sharpe_ratio)} sub={`rf ${pct(r.risk_free_rate)}`} />
          <Stat label="ESG score" value={r.esg_score == null ? "—" : num(r.esg_score, 1)} sub={r.esg_score == null ? "not available" : "value-weighted, 0–100"} />
          <Stat label="Effective no. of assets" value={num(r.effective_number_of_assets, 1)} sub={`${held.length} held`} help="Inverse Herfindahl index: 1/Σw²" />
          <Stat label="Diversification ratio" value={r.diversification_ratio == null ? "—" : num(r.diversification_ratio)} sub="Σwσ / σp" />
        </div>
        {r.esg_adjusted_return != null && (
          <p className="mt-2 text-xs text-ink-2">
            ESG-adjusted expected return used by the optimiser: {pct(r.esg_adjusted_return)} (includes the ESG preference; not a forecast).
          </p>
        )}
      </Card>

      {[...r.warnings, ...ex.warnings].length > 0 && (
        <Callout tone="warning" title="Read before relying on this result">
          <ul className="list-disc space-y-0.5 pl-4">
            {[...r.warnings, ...ex.warnings].map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}
      {data.excluded_unscored.length > 0 && (
        <Callout tone="info">Excluded for lacking an ESG score: {data.excluded_unscored.join(", ")}.</Callout>
      )}

      <div className="grid gap-4 2xl:grid-cols-2">
        <ChartFrame
          title="Weights"
          subtitle="Share of portfolio value in each held asset."
          table={<DataTable columns={[{ key: "t", label: "Asset" }, { key: "w", label: "Weight", align: "right" }]} rows={held.map((h) => ({ t: h.ticker, w: pct(h.weight) }))} />}
        >
          <div className="px-2">
            <BarList ariaLabel="Portfolio weights" rows={held.map((h) => ({ key: h.ticker, label: h.ticker, sub: h.sector ?? undefined, value: h.weight, display: pct(h.weight, 1) }))} />
          </div>
        </ChartFrame>
        <ChartFrame
          title="Risk contribution"
          subtitle="Share of portfolio volatility from each asset (Euler decomposition; sums to 100%)."
          table={<DataTable columns={[{ key: "t", label: "Asset" }, { key: "w", label: "Weight", align: "right" }, { key: "r", label: "Risk share", align: "right" }]} rows={held.map((h) => ({ t: h.ticker, w: pct(h.weight, 1), r: pct(h.risk_contribution_pct, 1) }))} />}
        >
          <div className="px-2">
            <BarList
              ariaLabel="Risk contributions"
              rows={[...held].sort((a, b) => b.risk_contribution_pct - a.risk_contribution_pct).map((h) => ({ key: h.ticker, label: h.ticker, sub: `weight ${pct(h.weight, 1)}`, value: h.risk_contribution_pct, display: pct(h.risk_contribution_pct, 1), color: "var(--series-2)" }))}
            />
          </div>
        </ChartFrame>
      </div>

      <Card title="Why each asset is (or is not) held" subtitle="Derived from the optimiser's optimality conditions, not generated text." bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <Th>Asset</Th>
              <Th>Status</Th>
              <Th align="right">Weight</Th>
              <Th align="right">Exp. return</Th>
              <Th align="right">Volatility</Th>
              <Th align="right">β to portfolio</Th>
              {r.objective === "max_sharpe" && <Th align="right">Required return</Th>}
              <Th>Reason</Th>
            </tr>
          </thead>
          <tbody>
            {[...r.holdings].sort((a, b) => b.weight - a.weight).map((h) => (
              <tr key={h.ticker}>
                <Td>
                  <span className="font-medium text-ink">{h.ticker}</span>
                  <span className="block text-[11px] text-muted">{h.sector ?? "—"}</span>
                </Td>
                <Td>
                  <StatusBadge status={h.status} />
                </Td>
                <Td align="right">{pct(h.weight, 1)}</Td>
                <Td align="right">{pct(h.expected_return)}</Td>
                <Td align="right">{pct(h.volatility)}</Td>
                <Td align="right">{num(h.beta_to_portfolio)}</Td>
                {r.objective === "max_sharpe" && <Td align="right">{pct(h.required_return)}</Td>}
                <Td className="min-w-[18rem] text-xs leading-snug text-ink-2">{h.reason}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <div className="grid gap-4 2xl:grid-cols-2">
        <Card title="What the model did">
          <ul className="list-disc space-y-1.5 pl-4 text-sm text-ink">
            {ex.statements.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          {binding.length > 0 && (
            <>
              <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-ink-2">Binding constraints</h3>
              <Table className="mt-1">
                <thead>
                  <tr>
                    <Th>Constraint</Th>
                    <Th align="right">Achieved</Th>
                    <Th align="right">Shadow price</Th>
                  </tr>
                </thead>
                <tbody>
                  {binding.map((d) => (
                    <tr key={d.label}>
                      <Td>{d.label}</Td>
                      <Td align="right">{d.kind === "min_esg" ? num(d.value, 1) : pct(d.value, 2)}</Td>
                      <Td align="right" title={d.shadow_price_unit ? `Marginal change in the objective (${d.shadow_price_unit}) per unit of the bound` : undefined}>
                        {d.shadow_price == null ? "—" : d.shadow_price.toExponential(2)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <p className="mt-1 text-[11px] text-muted">
                A binding constraint is active at the optimum: relaxing it would improve the objective. The shadow price is the marginal improvement per unit of relaxation.
              </p>
            </>
          )}
        </Card>
        <Card title="Assumptions">
          <ul className="list-disc space-y-1.5 pl-4 text-sm text-ink-2">
            {ex.assumptions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-2">
            To see how this approach would have performed out of sample, run a{" "}
            <Link href="/app/backtest" className="text-accent-ink underline underline-offset-2">
              walk-forward backtest
            </Link>
            .
          </p>
          <div className="mt-2">
            <EstimationNote mean={data.estimation.mean_estimator} cov={data.estimation.covariance_estimator} covShrinkage={data.estimation.covariance_shrinkage} meanShrinkage={data.estimation.mean_shrinkage} rf={rf} />
          </div>
        </Card>
      </div>

      {data.stability && data.stability.length > 0 && <Stability data={data} />}
      <DataNotes data={data.data} />
    </div>
  );
}

function Stability({ data }: { data: OptimiseResponse }) {
  const rows = (data.stability ?? []).filter((s) => s.p95 > 1e-6 || s.weight > 1e-6).sort((a, b) => b.weight - a.weight);
  const max = Math.max(...rows.map((s) => s.p95), 1e-9);
  return (
    <ChartFrame
      title="Weight stability under estimation error"
      subtitle={`Bootstrap resampling of the return history (${data.stability_resamples} successful resamples, seed ${data.seed}). Bars show the 5th–95th percentile of each weight; the tick marks the optimised weight.`}
      table={
        <DataTable
          columns={[
            { key: "t", label: "Asset" },
            { key: "w", label: "Optimised", align: "right" },
            { key: "m", label: "Resampled mean", align: "right" },
            { key: "lo", label: "5th pct", align: "right" },
            { key: "hi", label: "95th pct", align: "right" },
            { key: "f", label: "Held in", align: "right" },
          ]}
          rows={rows.map((s) => ({ t: s.ticker, w: pct(s.weight, 1), m: pct(s.mean, 1), lo: pct(s.p05, 1), hi: pct(s.p95, 1), f: pct(s.frequency_held, 0) }))}
        />
      }
    >
      <ul className="space-y-1.5 px-2" aria-label="Weight intervals">
        {rows.map((s) => (
          <li key={s.ticker} className="grid grid-cols-[6rem_1fr_7rem] items-center gap-3 text-sm">
            <span className="truncate text-ink">{s.ticker}</span>
            <div className="relative h-4" aria-hidden>
              <div className="absolute inset-y-1 rounded bg-[var(--series-1)] opacity-30" style={{ left: `${(s.p05 / max) * 100}%`, width: `${Math.max(0.5, ((s.p95 - s.p05) / max) * 100)}%` }} />
              <div className="absolute inset-y-0 w-0.5 bg-[var(--ink)]" style={{ left: `${(s.weight / max) * 100}%` }} />
            </div>
            <span className="text-right text-xs text-ink-2 tabular">
              {pct(s.p05, 0)}–{pct(s.p95, 0)} · held {pct(s.frequency_held, 0)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 px-2 text-[11px] text-muted">
        Wide intervals mean the optimal weights are driven by noise in the estimated inputs. Prefer constraints, shrinkage estimators or minimum-volatility objectives when they are wide.
      </p>
    </ChartFrame>
  );
}

function SaveButton({ data, request }: { data: OptimiseResponse; request: OptimiseRequest | null }) {
  const { status } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  if (status !== "signed_in") {
    return (
      <Link href="/login?next=/app/optimise" className="inline-flex h-8 items-center rounded-md border border-line-strong px-3 text-[13px] font-medium text-ink hover:bg-surface-2">
        Sign in to save
      </Link>
    );
  }
  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = data.result;
      await unwrap(
        api.POST("/api/v1/portfolios", {
          body: {
            name: name.trim(),
            dataset_id: data.data.dataset_id,
            weights: Object.fromEntries(r.holdings.filter((h) => Math.abs(h.weight) > 1e-9).map((h) => [h.ticker, h.weight])),
            spec: request as unknown as Record<string, unknown>,
            summary: {
              objective: r.objective,
              expected_return: r.expected_return,
              volatility: r.volatility,
              sharpe_ratio: r.sharpe_ratio,
              esg_score: r.esg_score,
              estimation_window: [data.data.start, data.data.end],
              is_synthetic: data.data.provenance.is_synthetic,
            },
          },
        }),
      );
      await qc.invalidateQueries({ queryKey: ["portfolios"] });
      setMsg({ tone: "success", text: "Saved." });
      setOpen(false);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError || e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="relative">
      <Button size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        Save
      </Button>
      {msg && <span className={msg.tone === "success" ? "ml-2 text-xs text-good" : "ml-2 text-xs text-critical"}>{msg.text}</span>}
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-md border border-line-strong bg-surface p-3 shadow-lg">
          <Field label="Portfolio name" htmlFor="pf-name">
            <Input id="pf-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus />
          </Field>
          <div className="mt-3 flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="primary" onClick={() => void save()} busy={busy} disabled={!name.trim()}>
              Save portfolio
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
