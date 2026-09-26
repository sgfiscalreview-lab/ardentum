"use client";

import { useState } from "react";

import { ChartFrame, DataTable, seriesColor, TimeSeriesChart } from "@/components/charts";
import { useAvailablePortfolios } from "@/components/portfolio-picker";
import { Callout, Card, Checkbox, EmptyState, Table, Td, Th } from "@/components/ui";
import {
  DataNotes,
  ErrorCallout,
  ExportMenu,
  PageHeader,
  RunBar,
  Running,
  SyntheticBanner,
  toCsv,
  useComputation,
  useDataset,
} from "@/components/workspace";
import { api, unwrap } from "@/lib/api/client";
import type { CompareRequest, CompareResponse } from "@/lib/api/types";
import { num, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

export default function ComparePage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const [chosen, setChosen] = useState<string[]>(["working", "equal"]);
  const { data, error, running, run } = useComputation<CompareRequest, CompareResponse>("compare", (req) =>
    unwrap(api.POST("/api/v1/compare", { body: req })),
  );
  const selected = options.filter((o) => chosen.includes(o.key)).slice(0, 6);

  const submit = () => {
    const tickers = Array.from(new Set(selected.flatMap((p) => Object.keys(p.weights))));
    run({
      universe: { ...state.universe, tickers },
      estimation: state.estimation,
      portfolios: selected.map((p) => ({ name: p.name, weights: p.weights })),
      rebalance: "monthly",
      transaction_cost_bps: 0,
    });
  };

  return (
    <>
      <PageHeader
        title="Compare portfolios"
        description="Side-by-side estimated (ex-ante) characteristics and historical behaviour of fixed-weight portfolios over the same window."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Portfolios" subtitle="Choose 2–6. Save portfolios from the optimiser to compare more.">
            <div className="space-y-2">
              {options.map((o) => (
                <Checkbox
                  key={o.key}
                  checked={chosen.includes(o.key)}
                  onChange={(v) => setChosen((c) => (v ? [...c, o.key] : c.filter((k) => k !== o.key)))}
                  label={o.name}
                  hint={`${Object.keys(o.weights).length} assets`}
                />
              ))}
            </div>
            <div className="mt-4">
              <RunBar running={running} label="Compare" onRun={submit} disabled={selected.length < 2} note={selected.length < 2 ? "Select at least two." : undefined} />
            </div>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data ? (
            <EmptyState title="Nothing to compare yet">Select at least two portfolios. The working portfolio comes from the optimiser or frontier pages.</EmptyState>
          ) : (
            <Running running={running}>
              <Results data={data} />
            </Running>
          )}
        </div>
      </div>
    </>
  );
}

function Results({ data }: { data: CompareResponse }) {
  const ps = data.portfolios;
  const dates = data.wealth_dates;
  const rows: [string, (p: (typeof ps)[number]) => string][] = [
    ["Expected return (estimate)", (p) => pct(p.expected_return)],
    ["Expected volatility (estimate)", (p) => pct(p.volatility)],
    ["Expected Sharpe (estimate)", (p) => num(p.sharpe_ratio)],
    ["ESG score", (p) => (p.esg_score == null ? "—" : num(p.esg_score, 1))],
    ["Effective no. of assets", (p) => num(p.effective_number_of_assets, 1)],
    ["Top risk contributor", (p) => (p.top_risk_contributors[0] ? `${p.top_risk_contributors[0].name} (${pct(p.top_risk_contributors[0].contribution, 0)})` : "—")],
    ["Historical CAGR", (p) => pct(p.historical.cagr)],
    ["Historical volatility", (p) => pct(p.historical.annualised_volatility)],
    ["Historical Sharpe", (p) => num(p.historical.sharpe_ratio.value)],
    ["Historical Sortino", (p) => num(p.historical.sortino_ratio.value)],
    ["Max drawdown", (p) => pct(p.historical.max_drawdown, 1)],
    ["1-period CVaR 95%", (p) => pct(p.historical.cvar_95)],
  ];
  const csv = () => toCsv([["metric", ...ps.map((p) => p.name)], ...rows.map(([label, f]) => [label, ...ps.map((p) => f(p))])]);
  return (
    <div className="space-y-4">
      <Callout tone="warning" title="In-sample comparison">
        {data.in_sample_warning}
      </Callout>
      <Card title="Side by side" bodyClassName="p-0" actions={<ExportMenu name="ardentum-comparison" json={data} csv={csv} />}>
        <Table>
          <thead>
            <tr>
              <Th>Metric</Th>
              {ps.map((p, i) => (
                <Th key={p.name} align="right">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-3 rounded" style={{ background: seriesColor(i) }} />
                    {p.name}
                  </span>
                </Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, f]) => (
              <tr key={label}>
                <Td>{label}</Td>
                {ps.map((p) => (
                  <Td key={p.name} align="right">
                    {f(p)}
                  </Td>
                ))}
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <ChartFrame
        title="Growth of 100 (rebalanced monthly)"
        legend={ps.map((p, i) => ({ label: p.name, color: seriesColor(i) }))}
        table={
          <DataTable
            columns={[{ key: "d", label: "Date" }, ...ps.map((p) => ({ key: p.name, label: p.name, align: "right" as const }))]}
            rows={dates.filter((_, i) => i % 21 === 0).map((d) => {
              const i = dates.indexOf(d);
              return { d, ...Object.fromEntries(ps.map((p) => [p.name, num((p.wealth[i] ?? Number.NaN) * 100, 1)])) };
            })}
          />
        }
      >
        <TimeSeriesChart dates={dates} series={ps.map((p, i) => ({ key: `s${i}`, name: p.name, values: p.wealth.map((w) => w * 100), color: seriesColor(i) }))} yFormat={(v) => v.toFixed(0)} />
      </ChartFrame>
      <ChartFrame title="Drawdown" legend={ps.map((p, i) => ({ label: p.name, color: seriesColor(i) }))}>
        <TimeSeriesChart dates={dates} series={ps.map((p, i) => ({ key: `s${i}`, name: p.name, values: p.drawdown, color: seriesColor(i) }))} yFormat={(v) => `${(v * 100).toFixed(0)}%`} height={200} />
      </ChartFrame>
      <Card title="Correlation of portfolio returns" bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <Th />
              {ps.map((p) => (
                <Th key={p.name} align="right">
                  {p.name}
                </Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ps.map((p, i) => (
              <tr key={p.name}>
                <Td>{p.name}</Td>
                {ps.map((q, j) => (
                  <Td key={q.name} align="right">
                    {num(data.return_correlation[i]?.[j], 2)}
                  </Td>
                ))}
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <DataNotes data={data.data} />
    </div>
  );
}
