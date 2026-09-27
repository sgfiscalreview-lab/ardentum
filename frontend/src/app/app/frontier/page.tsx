"use client";

import { ChartFrame, DataTable, FrontierChart, type MarkerPoint } from "@/components/charts";
import { ConstraintsPanel } from "@/components/forms";
import { Callout, Card, EmptyState, Stat } from "@/components/ui";
import {
  DataNotes,
  ErrorCallout,
  EstimationNote,
  ExportMenu,
  PageHeader,
  ResultsSkeleton,
  RunBar,
  Running,
  SyntheticBanner,
  toCsv,
  useComputation,
  useDataset,
} from "@/components/workspace";
import { runJob } from "@/lib/api/client";
import type { FrontierRequest, FrontierResponse } from "@/lib/api/types";
import { num, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

export default function FrontierPage() {
  const { state, setConstraints, setWorking } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const { data, error, running, run } = useComputation<FrontierRequest, FrontierResponse>("frontier", (req, signal) =>
    runJob("frontier", req, signal),
  );
  return (
    <>
      <PageHeader
        title="Efficient frontier"
        description="Each point is the lowest-volatility portfolio for a given expected return under your constraints. Portfolios below the curve are dominated; the frontier is an estimate and moves with the inputs."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Constraints" subtitle="Shared with the optimiser.">
            <ConstraintsPanel value={state.constraints} onChange={setConstraints} assets={ds.data?.assets ?? []} tickers={state.universe.tickers} />
          </Card>
          <Card>
            <RunBar
              running={running}
              label="Trace frontier"
              disabled={state.universe.tickers.length < 2}
              onRun={() =>
                run({ universe: state.universe, estimation: state.estimation, constraints: state.constraints, n_points: 30, compare_unconstrained: true })
              }
            />
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data && running ? (
            <ResultsSkeleton />
          ) : !data ? (
            <EmptyState title="No frontier yet">Trace the constrained efficient frontier for the selected assets.</EmptyState>
          ) : (
            <Running running={running}>
              <FrontierView data={data} rf={state.estimation.risk_free_rate ?? 0} onUse={(name, weights) => setWorking({ name, weights, datasetId: data.data.dataset_id, source: "optimiser" })} />
            </Running>
          )}
        </div>
      </div>
    </>
  );
}

function FrontierView({ data, rf, onUse }: { data: FrontierResponse; rf: number; onUse: (name: string, w: Record<string, number>) => void }) {
  const ms = data.max_sharpe;
  const mv = data.min_volatility;
  const lines = [
    { name: "Efficient frontier (your constraints)", color: "var(--series-1)", points: data.points.map((p) => ({ x: p.volatility, y: p.expected_return })) },
  ];
  if (data.unconstrained_points) {
    lines.push({ name: "Long-only frontier without constraints", color: "var(--series-3)", points: data.unconstrained_points.map((p) => ({ x: p.volatility, y: p.expected_return })) });
  }
  if (ms) {
    const maxX = Math.max(...data.points.map((p) => p.volatility), ...data.assets.map((a) => a.volatility)) * 1.02;
    const slope = ms.sharpe_ratio ?? 0;
    lines.push({
      name: "Capital market line",
      color: "var(--series-7)",
      points: [
        { x: 0, y: data.risk_free_rate_arithmetic },
        { x: maxX, y: data.risk_free_rate_arithmetic + slope * maxX },
      ],
    });
  }
  const markers: MarkerPoint[] = [
    ...data.assets.map((a) => ({ name: a.ticker, x: a.volatility, y: a.expected_return, color: "var(--ink-2)", shape: "circle" as const, size: 4, detail: a.sector ?? undefined })),
    { name: "Minimum volatility", x: mv.volatility, y: mv.expected_return, color: "var(--series-2)", shape: "square", size: 5 },
  ];
  if (ms) markers.push({ name: "Maximum Sharpe", x: ms.volatility, y: ms.expected_return, color: "var(--series-8)", shape: "diamond", size: 5, detail: `Sharpe ${num(ms.sharpe_ratio)}` });

  const legend = [
    ...lines.map((l) => ({ label: l.name, color: l.color, kind: "line" as const })),
    { label: "Individual assets", color: "var(--ink-2)", kind: "dot" as const },
    { label: "Minimum volatility", color: "var(--series-2)", kind: "rect" as const },
    ...(ms ? [{ label: "Maximum Sharpe", color: "var(--series-8)", kind: "rect" as const }] : []),
  ];
  const csv = () =>
    toCsv([
      ["expected_return", "volatility", "sharpe", "esg_score", ...data.assets.map((a) => a.ticker)],
      ...data.points.map((p) => [p.expected_return, p.volatility, p.sharpe_ratio, p.esg_score, ...data.assets.map((a) => p.weights[a.ticker] ?? 0)]),
    ]);
  return (
    <div className="space-y-4">
      {data.warnings.map((w) => (
        <Callout key={w} tone="warning">
          {w}
        </Callout>
      ))}
      {data.max_sharpe_unavailable_reason && <Callout tone="warning" title="Maximum-Sharpe portfolio undefined">{data.max_sharpe_unavailable_reason}</Callout>}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat label="Min-vol return" value={pct(mv.expected_return)} sub={`volatility ${pct(mv.volatility)}`} />
        <Stat label="Min-vol Sharpe" value={num(mv.sharpe_ratio)} />
        <Stat label="Max-Sharpe return" value={ms ? pct(ms.expected_return) : "n/a"} sub={ms ? `volatility ${pct(ms.volatility)}` : undefined} />
        <Stat label="Max Sharpe ratio" value={ms ? num(ms.sharpe_ratio) : "n/a"} sub={`rf ${pct(rf)}`} />
      </div>
      <ChartFrame
        title="Risk–return space"
        subtitle="Expected (annualised, estimated) return against volatility. The capital market line runs from the risk-free rate through the maximum-Sharpe portfolio."
        legend={legend}
        actions={<ExportMenu name="ardentum-frontier" json={data} csv={csv} />}
        table={
          <DataTable
            columns={[
              { key: "r", label: "Expected return", align: "right" },
              { key: "v", label: "Volatility", align: "right" },
              { key: "s", label: "Sharpe", align: "right" },
              { key: "e", label: "ESG", align: "right" },
            ]}
            rows={data.points.map((p) => ({ r: pct(p.expected_return), v: pct(p.volatility), s: num(p.sharpe_ratio), e: p.esg_score == null ? "n/a" : num(p.esg_score, 1) }))}
          />
        }
      >
        <FrontierChart lines={lines} markers={markers} />
      </ChartFrame>
      <Card title="Key portfolios">
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { label: "Minimum volatility", p: mv },
            ...(ms ? [{ label: "Maximum Sharpe", p: ms }] : []),
          ].map(({ label, p }) => (
            <div key={label} className="rounded-md border border-line p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-ink">{label}</p>
                <button type="button" className="text-xs text-accent-ink underline underline-offset-2" onClick={() => onUse(`${label} (frontier)`, p.weights)}>
                  Use as working portfolio
                </button>
              </div>
              <ul className="mt-2 space-y-0.5 text-xs text-ink-2">
                {Object.entries(p.weights)
                  .filter(([, w]) => Math.abs(w) >= 0.0005)
                  .sort((a, b) => b[1] - a[1])
                  .map(([t, w]) => (
                    <li key={t} className="flex justify-between tabular">
                      <span>{t}</span>
                      <span className="text-ink">{pct(w, 1)}</span>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
      <EstimationNote mean={data.estimation.mean_estimator} cov={data.estimation.covariance_estimator} covShrinkage={data.estimation.covariance_shrinkage} rf={rf} />
      <DataNotes data={data.data} />
    </div>
  );
}
