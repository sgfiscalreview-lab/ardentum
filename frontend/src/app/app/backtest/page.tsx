"use client";

import { useState } from "react";

import { BarList, ChartFrame, DataTable, TimeSeriesChart } from "@/components/charts";
import { PortfolioPicker, resolvePortfolio, useAvailablePortfolios } from "@/components/portfolio-picker";
import { Callout, Card, EmptyState, Field, Input, NumberInput, Select, Stat, Table, Tabs, Td, Th } from "@/components/ui";
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
import { runJob } from "@/lib/api/client";
import type { BacktestRequest, BacktestResponse, PerformanceOut } from "@/lib/api/types";
import { date as fmtDate, num, OBJECTIVE_LABELS, pct, signedPct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

type StrategyKind = "optimised" | "fixed" | "equal_weight";

export default function BacktestPage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const [kind, setKind] = useState<StrategyKind>("optimised");
  const [pick, setPick] = useState("working");
  const [lookback, setLookback] = useState(3);
  const [rebalance, setRebalance] = useState<NonNullable<BacktestRequest["rebalance"]>>("monthly");
  const [costs, setCosts] = useState(10);
  const benchDefault = ds.data?.assets.find((a) => a.is_benchmark)?.ticker;
  const [bench, setBench] = useState<string>("equal_weight");
  const [start, setStart] = useState<string>("");
  const [end, setEnd] = useState<string>("");
  const { data, error, running, run } = useComputation<BacktestRequest, BacktestResponse>("backtest", (req, signal) =>
    runJob("backtest", req, signal),
  );

  const submit = () => {
    const fixed = resolvePortfolio(options, pick);
    const tickers = kind === "fixed" && fixed ? Object.keys(fixed.weights) : state.universe.tickers;
    const strategy: BacktestRequest["strategy"] =
      kind === "optimised"
        ? { type: "optimised", objective: state.objective, constraints: state.constraints }
        : kind === "fixed"
          ? { type: "fixed", weights: fixed?.weights ?? {} }
          : { type: "equal_weight" };
    run({
      universe: { ...state.universe, tickers, start: start || ds.data?.start || null, end: end || ds.data?.end || null },
      estimation: state.estimation,
      strategy,
      lookback_years: lookback,
      rebalance,
      transaction_cost_bps: costs,
      benchmark: bench === "none" ? null : bench === "equal_weight" ? { type: "equal_weight" } : { type: "asset", ticker: bench },
    });
  };

  return (
    <>
      <PageHeader
        title="Walk-forward backtest"
        description="Replays a strategy through history. At each rebalance the model sees only data up to that date, re-estimates inputs, and trades at that day's close. Performance is measured only after the first estimation window."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Strategy">
            <div className="space-y-3">
              <Tabs
                label="Strategy type"
                value={kind}
                onChange={setKind}
                items={[
                  { value: "optimised", label: "Re-optimise" },
                  { value: "fixed", label: "Fixed weights" },
                  { value: "equal_weight", label: "Equal weight" },
                ]}
              />
              {kind === "optimised" && (
                <p className="text-xs text-ink-2">
                  Re-solves <span className="font-medium text-ink">{OBJECTIVE_LABELS[state.objective.objective]}</span> with your current constraints at each rebalance, using only the trailing window. Change them on the Optimise page.
                </p>
              )}
              {kind === "fixed" && <PortfolioPicker value={pick} onChange={setPick} label="Target weights" />}
              {kind === "equal_weight" && <p className="text-xs text-ink-2">Rebalances to equal weights across the {state.universe.tickers.length} selected assets.</p>}
            </div>
          </Card>
          <Card title="Settings">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Backtest start" htmlFor="bt-start" hint="Defaults to dataset start.">
                  <Input id="bt-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
                </Field>
                <Field label="Backtest end" htmlFor="bt-end">
                  <Input id="bt-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
                </Field>
                <Field label="Lookback (years)" htmlFor="lookback" hint="Estimation window at each rebalance.">
                  <NumberInput id="lookback" value={lookback} onChange={(v) => setLookback(v ?? 3)} min={0.25} max={20} />
                </Field>
                <Field label="Costs (bps)" htmlFor="costs" hint="Per unit of turnover.">
                  <NumberInput id="costs" value={costs} onChange={(v) => setCosts(v ?? 0)} min={0} max={500} />
                </Field>
              </div>
              <Field label="Rebalance" htmlFor="rebalance">
                <Select id="rebalance" value={rebalance} onChange={(e) => setRebalance(e.target.value as typeof rebalance)}>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="semiannual">Semi-annually</option>
                  <option value="annual">Annually</option>
                </Select>
              </Field>
              <Field label="Benchmark" htmlFor="bench">
                <Select id="bench" value={bench} onChange={(e) => setBench(e.target.value)}>
                  <option value="equal_weight">Equal weight (same assets)</option>
                  {benchDefault && <option value={benchDefault}>{benchDefault}</option>}
                  {ds.data?.assets.filter((a) => a.ticker !== benchDefault).map((a) => (
                    <option key={a.ticker} value={a.ticker}>
                      {a.ticker}
                    </option>
                  ))}
                  <option value="none">None</option>
                </Select>
              </Field>
              <RunBar running={running} label="Run backtest" onRun={submit} note={kind === "optimised" ? "Re-optimising every period can take a few seconds." : undefined} />
            </div>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data ? (
            <EmptyState title="No backtest yet">Choose a strategy and run it through history.</EmptyState>
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

function PerfRows({ p, b }: { p: PerformanceOut; b: PerformanceOut | null }) {
  const rows: [string, (x: PerformanceOut) => string][] = [
    ["Total return", (x) => pct(x.total_return, 1)],
    ["CAGR", (x) => pct(x.cagr)],
    ["Volatility", (x) => pct(x.annualised_volatility)],
    ["Sharpe ratio", (x) => num(x.sharpe_ratio.value)],
    ["Sortino ratio", (x) => num(x.sortino_ratio.value)],
    ["Max drawdown", (x) => pct(x.max_drawdown, 1)],
    ["Calmar ratio", (x) => num(x.calmar_ratio.value)],
    ["1-period VaR 95%", (x) => pct(x.var_95)],
    ["1-period CVaR 95%", (x) => pct(x.cvar_95)],
    ["Worst period", (x) => pct(x.worst_period)],
    ["Positive periods", (x) => pct(x.positive_periods_fraction, 0)],
  ];
  return (
    <Table>
      <thead>
        <tr>
          <Th>Metric</Th>
          <Th align="right">Strategy</Th>
          {b && <Th align="right">Benchmark</Th>}
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, f]) => (
          <tr key={label}>
            <Td>{label}</Td>
            <Td align="right">{f(p)}</Td>
            {b && <Td align="right">{f(b)}</Td>}
          </tr>
        ))}
        {p.tracking_error != null && (
          <>
            <tr>
              <Td>Tracking error</Td>
              <Td align="right">{pct(p.tracking_error)}</Td>
              {b && <Td align="right">—</Td>}
            </tr>
            <tr>
              <Td>Information ratio</Td>
              <Td align="right">{num(p.information_ratio?.value)}</Td>
              {b && <Td align="right">—</Td>}
            </tr>
            <tr>
              <Td>Beta to benchmark</Td>
              <Td align="right">{num(p.beta?.value)}</Td>
              {b && <Td align="right">1.00</Td>}
            </tr>
          </>
        )}
      </tbody>
    </Table>
  );
}

function Results({ data }: { data: BacktestResponse }) {
  // Wealth starts at 1 on the first rebalance date (the close before the evaluation period).
  const dates = data.wealth_dates;
  const series = [{ key: "p", name: data.strategy, values: data.portfolio.wealth.map((w) => w * 100), color: "var(--series-1)" }];
  if (data.benchmark) series.push({ key: "b", name: data.benchmark.name, values: data.benchmark.wealth.map((w) => w * 100), color: "var(--series-2)" });
  const dd = [{ key: "p", name: data.strategy, values: data.portfolio.drawdown, color: "var(--series-1)" }];
  if (data.benchmark) dd.push({ key: "b", name: data.benchmark.name, values: data.benchmark.drawdown, color: "var(--series-2)" });
  const p = data.performance;
  const excess = data.benchmark_performance ? p.cagr - data.benchmark_performance.cagr : null;
  const csv = () =>
    toCsv([["date", "strategy_wealth", ...(data.benchmark ? ["benchmark_wealth"] : [])], ...dates.map((d, i) => [d, data.portfolio.wealth[i], ...(data.benchmark ? [data.benchmark.wealth[i]] : [])])]);
  return (
    <div className="space-y-4">
      <Card
        title={data.strategy}
        subtitle={
          <>
            Estimation data from {fmtDate(data.estimation_start)}; evaluation {fmtDate(data.evaluation_start)} – {fmtDate(data.evaluation_end)} · {data.rebalance} rebalancing · {data.transaction_cost_bps} bps costs
          </>
        }
        actions={<ExportMenu name="ardentum-backtest" json={data} csv={csv} />}
      >
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-6">
          <Stat label="CAGR" value={pct(p.cagr)} sub={excess == null ? undefined : `${signedPct(excess)} vs benchmark`} />
          <Stat label="Volatility" value={pct(p.annualised_volatility)} />
          <Stat label="Sharpe ratio" value={num(p.sharpe_ratio.value)} />
          <Stat label="Max drawdown" value={pct(p.max_drawdown, 1)} />
          <Stat label="Turnover" value={pct(data.annualised_turnover, 0)} sub="per year (one-way sum)" />
          <Stat label="Cost drag" value={pct(data.total_cost, 2)} sub="of final wealth" />
        </div>
      </Card>
      <ChartFrame
        title="Growth of 100"
        subtitle="Net of transaction costs. Starts at the first rebalance; earlier data was used only for estimation."
        legend={series.map((s) => ({ label: s.name, color: s.color }))}
        table={<DataTable columns={[{ key: "d", label: "Date" }, ...series.map((s) => ({ key: s.key, label: s.name, align: "right" as const }))]} rows={dates.filter((_, i) => i % 21 === 0).map((d) => {
          const i = dates.indexOf(d);
          return { d, ...Object.fromEntries(series.map((s) => [s.key, num(s.values[i], 1)])) };
        })} />}
      >
        <TimeSeriesChart dates={dates} series={series} yFormat={(v) => v.toFixed(0)} />
      </ChartFrame>
      <ChartFrame title="Drawdown" subtitle="Decline from the running peak." legend={dd.map((s) => ({ label: s.name, color: s.color }))}>
        <TimeSeriesChart dates={dates} series={dd} yFormat={(v) => `${(v * 100).toFixed(0)}%`} area height={200} />
      </ChartFrame>
      <div className="grid gap-4 2xl:grid-cols-2">
        <Card title="Performance (evaluation period)" bodyClassName="p-0">
          <PerfRows p={p} b={data.benchmark_performance} />
        </Card>
        <ChartFrame
          title="Contribution to return"
          subtitle="Carino-linked contributions; they sum exactly to the strategy's total net return."
          table={<DataTable columns={[{ key: "n", label: "Asset" }, { key: "c", label: "Contribution", align: "right" }]} rows={data.asset_contributions.map((c) => ({ n: c.name, c: signedPct(c.contribution) }))} />}
        >
          <div className="px-2">
            <BarList ariaLabel="Contribution to return" rows={[...data.asset_contributions].sort((a, b) => b.contribution - a.contribution).map((c) => ({ key: c.name, label: c.name, value: c.contribution, display: signedPct(c.contribution, 1), color: c.contribution >= 0 ? "var(--diverge-pos)" : "var(--diverge-neg)" }))} />
          </div>
        </ChartFrame>
      </div>
      {data.brinson && (
        <Card title="Sector attribution vs. equal-weight benchmark (Brinson–Fachler)" subtitle="Allocation: over/under-weighting sectors. Selection: picking assets within sectors. Linked over time; totals equal the gross active return." bodyClassName="p-0">
          <Table>
            <thead>
              <tr>
                <Th>Sector</Th>
                <Th align="right">Avg. weight</Th>
                <Th align="right">Bench. weight</Th>
                <Th align="right">Allocation</Th>
                <Th align="right">Selection</Th>
                <Th align="right">Interaction</Th>
                <Th align="right">Total</Th>
              </tr>
            </thead>
            <tbody>
              {data.brinson.map((b) => (
                <tr key={b.sector}>
                  <Td>{b.sector}</Td>
                  <Td align="right">{pct(b.portfolio_weight, 1)}</Td>
                  <Td align="right">{pct(b.benchmark_weight, 1)}</Td>
                  <Td align="right">{signedPct(b.allocation)}</Td>
                  <Td align="right">{signedPct(b.selection)}</Td>
                  <Td align="right">{signedPct(b.interaction)}</Td>
                  <Td align="right" className="font-medium">{signedPct(b.total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      <Card title={`Rebalances (${data.events.length})`} bodyClassName="p-0">
        <div className="max-h-80 overflow-y-auto">
          <Table>
            <thead>
              <tr>
                <Th>Date</Th>
                <Th>Estimation window</Th>
                <Th align="right">Turnover</Th>
                <Th align="right">Cost</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {data.events.map((e) => (
                <tr key={e.date}>
                  <Td>{fmtDate(e.date)}</Td>
                  <Td className="text-ink-2">
                    {fmtDate(e.estimation_start)} – {fmtDate(e.estimation_end)}
                  </Td>
                  <Td align="right">{pct(e.turnover, 1)}</Td>
                  <Td align="right">{pct(e.cost, 3)}</Td>
                  <Td className="text-xs text-ink-2">{e.status === "held" ? `Held: ${e.message ?? ""}` : "Rebalanced"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Card>
      <Callout tone="info" title="Assumptions and limitations">
        <ul className="list-disc space-y-0.5 pl-4">
          {data.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </Callout>
      <DataNotes data={data.data} />
    </div>
  );
}
