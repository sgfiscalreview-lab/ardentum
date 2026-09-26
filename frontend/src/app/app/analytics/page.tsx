"use client";

import { useState } from "react";

import { ChartFrame, DataTable, Heatmap, seriesColor, TimeSeriesChart } from "@/components/charts";
import { Card, EmptyState, Select, Table, Td, Th } from "@/components/ui";
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
import { api, unwrap } from "@/lib/api/client";
import type { AnalyticsResponse, MetricOut } from "@/lib/api/types";
import { num, pct } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { useWorkspace } from "@/lib/workspace";

type Req = { universe: object; estimation: object; benchmark: string | null };

function metric(m: MetricOut | null | undefined, digits = 2): string {
  return m?.value == null ? "—" : num(m.value, digits);
}

export default function AnalyticsPage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const bench = ds.data?.assets.find((a) => a.is_benchmark)?.ticker ?? null;
  const [benchmark, setBenchmark] = useState<string | null>(bench);
  const { data, error, running, run } = useComputation<Req, AnalyticsResponse>("analytics", (req) =>
    unwrap(api.POST("/api/v1/analytics", { body: req as never })),
  );
  const { isDark } = useTheme();
  const [shown, setShown] = useState<string[] | null>(null);
  const tickers = data?.tickers ?? [];
  const lines = (shown ?? tickers.slice(0, 4)).filter((t) => tickers.includes(t)).slice(0, 8);

  return (
    <>
      <PageHeader
        title="Historical analytics"
        description="Realised statistics for each asset over the estimation window. These are observed historical values, not forecasts."
        actions={
          <RunBar
            running={running}
            label={data ? "Recompute" : "Compute analytics"}
            disabled={state.universe.tickers.length < 1}
            onRun={() => run({ universe: state.universe, estimation: state.estimation, benchmark: benchmark ?? bench })}
          />
        }
      />
      <SyntheticBanner dataset={ds.data} />
      <ErrorCallout error={error} />
      {ds.data && ds.data.assets.some((a) => a.is_benchmark) && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <label htmlFor="bench" className="text-ink-2">
            Benchmark for beta and tracking error
          </label>
          <Select id="bench" className="w-56" value={benchmark ?? ""} onChange={(e) => setBenchmark(e.target.value || null)}>
            <option value="">None</option>
            {ds.data.assets.map((a) => (
              <option key={a.ticker} value={a.ticker}>
                {a.ticker}
              </option>
            ))}
          </Select>
        </div>
      )}
      {!data ? (
        <EmptyState title="No analytics yet">Compute historical statistics for the {state.universe.tickers.length} selected assets.</EmptyState>
      ) : (
        <Running running={running}>
          <div className="space-y-4">
            <Card
              title="Asset statistics"
              subtitle={
                <EstimationNote
                  mean={data.estimation.mean_estimator}
                  cov={data.estimation.covariance_estimator}
                  covShrinkage={data.estimation.covariance_shrinkage}
                  rf={state.estimation.risk_free_rate ?? 0}
                />
              }
              actions={
                <ExportMenu
                  name="ardentum-asset-statistics"
                  json={data}
                  csv={() =>
                    toCsv([
                      ["ticker", "name", "sector", "esg", "cagr", "arith_return", "volatility", "sharpe", "sortino", "max_drawdown", "beta", "var95_1p", "cvar95_1p"],
                      ...data.assets.map((a) => [
                        a.ticker, a.name, a.sector, a.esg_score, a.performance.cagr, a.performance.arithmetic_annual_return,
                        a.performance.annualised_volatility, a.performance.sharpe_ratio.value, a.performance.sortino_ratio.value,
                        a.performance.max_drawdown, a.performance.beta?.value ?? null, a.performance.var_95, a.performance.cvar_95,
                      ]),
                    ])
                  }
                />
              }
              bodyClassName="p-0"
            >
              <Table>
                <thead>
                  <tr>
                    <Th>Asset</Th>
                    <Th align="right">CAGR</Th>
                    <Th align="right">Mean (arith.)</Th>
                    <Th align="right">Volatility</Th>
                    <Th align="right">Sharpe</Th>
                    <Th align="right">Sortino</Th>
                    <Th align="right">Max drawdown</Th>
                    {data.benchmark && <Th align="right">Beta</Th>}
                    <Th align="right">1-period VaR 95%</Th>
                    <Th align="right">ESG</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.assets.map((a) => (
                    <tr key={a.ticker}>
                      <Td>
                        <span className="font-medium text-ink">{a.ticker}</span>
                        <span className="block text-[11px] text-muted">{a.sector ?? "—"}</span>
                      </Td>
                      <Td align="right">{pct(a.performance.cagr)}</Td>
                      <Td align="right">{pct(a.performance.arithmetic_annual_return)}</Td>
                      <Td align="right">{pct(a.performance.annualised_volatility)}</Td>
                      <Td align="right" title={a.performance.sharpe_ratio.reason ?? undefined}>{metric(a.performance.sharpe_ratio)}</Td>
                      <Td align="right" title={a.performance.sortino_ratio.reason ?? undefined}>{metric(a.performance.sortino_ratio)}</Td>
                      <Td align="right">{pct(a.performance.max_drawdown, 1)}</Td>
                      {data.benchmark && <Td align="right">{metric(a.performance.beta)}</Td>}
                      <Td align="right">{pct(a.performance.var_95)}</Td>
                      <Td align="right">{a.esg_score != null ? a.esg_score.toFixed(0) : "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <p className="px-4 py-2 text-[11px] text-muted">
                CAGR is the realised compound growth rate; &ldquo;mean&rdquo; is the annualised arithmetic average used as the expected-return estimate. VaR is the historical one-period loss not exceeded on 95% of {data.data.frequency} observations.
              </p>
            </Card>

            <ChartFrame
              title="Growth of 100"
              subtitle="Total-return index, rebased to 100 at the start of the window (weekly samples)."
              legend={lines.map((t, i) => ({ label: t, color: seriesColor(i) }))}
              actions={
                <Select
                  aria-label="Assets to plot"
                  className="h-8 w-48 text-xs"
                  value=""
                  onChange={(e) => {
                    const t = e.target.value;
                    if (!t) return;
                    setShown(lines.includes(t) ? lines.filter((x) => x !== t) : [...lines, t].slice(-8));
                  }}
                >
                  <option value="">Add/remove series (max 8)…</option>
                  {tickers.map((t) => (
                    <option key={t} value={t}>
                      {lines.includes(t) ? "✓ " : ""}
                      {t}
                    </option>
                  ))}
                </Select>
              }
              table={
                <DataTable
                  columns={[{ key: "date", label: "Date" }, ...lines.map((t) => ({ key: t, label: t, align: "right" as const }))]}
                  rows={data.price_dates.map((d, i) => ({ date: d, ...Object.fromEntries(lines.map((t) => [t, num(data.normalised_prices[t]?.[i], 1)])) }))}
                />
              }
            >
              <TimeSeriesChart
                dates={data.price_dates}
                series={lines.map((t, i) => ({ key: t, name: t, values: data.normalised_prices[t] ?? [], color: seriesColor(i) }))}
                yFormat={(v) => v.toFixed(0)}
              />
            </ChartFrame>

            <ChartFrame
              title="Correlation matrix"
              subtitle="Pearson correlation of returns. Blue: move together; red: move in opposite directions; gray: unrelated."
              table={
                <DataTable
                  columns={[{ key: "t", label: "" }, ...tickers.map((t) => ({ key: t, label: t, align: "right" as const }))]}
                  rows={tickers.map((t, i) => ({ t, ...Object.fromEntries(tickers.map((u, j) => [u, num(data.correlation[i]?.[j], 2)])) }))}
                />
              }
            >
              <div className="px-2">
                <Heatmap labels={tickers} matrix={data.correlation} dark={isDark} />
              </div>
            </ChartFrame>
            <DataNotes data={data.data} />
          </div>
        </Running>
      )}
    </>
  );
}
