"use client";

import { useState } from "react";

import { ChartFrame, DataTable, FanChart, Histogram } from "@/components/charts";
import { PortfolioPicker, resolvePortfolio, useAvailablePortfolios } from "@/components/portfolio-picker";
import { Callout, Card, EmptyState, Field, NumberInput, Select, Stat } from "@/components/ui";
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
import type { MonteCarloRequest, MonteCarloResponse } from "@/lib/api/types";
import { money, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

const METHOD_HELP: Record<MonteCarloRequest["method"] & string, string> = {
  parametric: "Lognormal returns matched to the portfolio's estimated mean and volatility. Thin tails; ignores volatility clustering.",
  bootstrap: "Resamples historical daily portfolio returns independently. Keeps fat tails; loses serial dependence.",
  block_bootstrap: "Resamples blocks of consecutive history (stationary bootstrap). Keeps fat tails and short-range clustering.",
};

export default function SimulatePage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const [pick, setPick] = useState("working");
  const [method, setMethod] = useState<NonNullable<MonteCarloRequest["method"]>>("parametric");
  const [paths, setPaths] = useState(5000);
  const [years, setYears] = useState(10);
  const [initial, setInitial] = useState(10_000);
  const [target, setTarget] = useState<number | null>(20_000);
  const [seed, setSeed] = useState<number | null>(20260926);
  const [flowKind, setFlowKind] = useState<"none" | "contribute" | "withdraw">("none");
  const [flowAmount, setFlowAmount] = useState(1_200);
  const [flowFreq, setFlowFreq] = useState<1 | 4 | 12>(12);
  const [flowGrowth, setFlowGrowth] = useState(0);
  const { data, error, running, run } = useComputation<MonteCarloRequest, MonteCarloResponse>("simulate", (req) =>
    unwrap(api.POST("/api/v1/montecarlo", { body: req })),
  );
  const portfolio = resolvePortfolio(options, pick);

  const submit = () => {
    if (!portfolio) return;
    const tickers = Object.keys(portfolio.weights);
    run({
      universe: { ...state.universe, tickers },
      estimation: state.estimation,
      weights: portfolio.weights,
      method,
      n_paths: paths,
      horizon_years: years,
      initial_value: initial,
      target_value: target,
      seed,
      mean_block_length: 21,
      annual_cash_flow: flowKind === "none" ? 0 : flowKind === "contribute" ? flowAmount : -flowAmount,
      cash_flows_per_year: flowFreq,
      cash_flow_growth: flowGrowth,
    });
  };

  return (
    <>
      <PageHeader
        title="Monte Carlo simulation"
        description="A range of possible outcomes for a portfolio, not a prediction. Simulations are reproducible: the seed is shown with every result."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Portfolio">
            <PortfolioPicker value={pick} onChange={setPick} />
          </Card>
          <Card title="Simulation">
            <div className="space-y-3">
              <Field label="Method" htmlFor="method" hint={METHOD_HELP[method]}>
                <Select id="method" value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
                  <option value="parametric">Parametric (lognormal)</option>
                  <option value="bootstrap">Historical bootstrap</option>
                  <option value="block_bootstrap">Block bootstrap</option>
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Horizon (years)" htmlFor="years">
                  <NumberInput id="years" value={years} onChange={(v) => setYears(v ?? 10)} min={0.25} max={40} />
                </Field>
                <Field label="Paths" htmlFor="paths">
                  <NumberInput id="paths" value={paths} onChange={(v) => setPaths(Math.round(v ?? 5000))} min={100} max={20000} />
                </Field>
                <Field label="Initial value ($)" htmlFor="initial">
                  <NumberInput id="initial" value={initial} onChange={(v) => setInitial(v ?? 10000)} min={1} max={1e12} />
                </Field>
                <Field label="Target value ($)" htmlFor="target">
                  <NumberInput id="target" value={target} onChange={setTarget} min={1} max={1e13} allowEmpty placeholder="None" />
                </Field>
              </div>
              <Field label="Regular cash flows" htmlFor="flow-kind" hint="Paid at the end of each interval. A path is depleted when it cannot cover a withdrawal.">
                <Select id="flow-kind" value={flowKind} onChange={(e) => setFlowKind(e.target.value as typeof flowKind)}>
                  <option value="none">None</option>
                  <option value="contribute">Contributions</option>
                  <option value="withdraw">Withdrawals</option>
                </Select>
              </Field>
              {flowKind !== "none" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Amount per year ($)" htmlFor="flow-amount">
                    <NumberInput id="flow-amount" value={flowAmount} onChange={(v) => setFlowAmount(Math.abs(v ?? 0))} min={0} max={1e11} />
                  </Field>
                  <Field label="Paid" htmlFor="flow-freq">
                    <Select id="flow-freq" value={flowFreq} onChange={(e) => setFlowFreq(Number(e.target.value) as 1 | 4 | 12)}>
                      <option value={12}>Monthly</option>
                      <option value={4}>Quarterly</option>
                      <option value={1}>Annually</option>
                    </Select>
                  </Field>
                  <Field label="Annual increase" htmlFor="flow-growth" className="col-span-2" hint="E.g. 2% to keep pace with inflation.">
                    <NumberInput id="flow-growth" value={flowGrowth} onChange={(v) => setFlowGrowth(v ?? 0)} scale={100} suffix="%" min={-20} max={20} />
                  </Field>
                </div>
              )}
              <Field label="Random seed" htmlFor="seed" hint="Same seed and inputs ⇒ identical results. Leave empty for a random seed (it will be reported).">
                <NumberInput id="seed" value={seed} onChange={(v) => setSeed(v == null ? null : Math.round(v))} min={0} max={2147483647} allowEmpty placeholder="Random" />
              </Field>
              <RunBar running={running} label="Simulate" onRun={submit} disabled={!portfolio} />
            </div>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data ? (
            <EmptyState title="No simulation yet">Pick a portfolio (optimise one first, or use equal weights) and run the simulation.</EmptyState>
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

function Results({ data }: { data: MonteCarloResponse }) {
  const p = data.terminal_percentiles;
  const csv = () =>
    toCsv([
      ["years", ...Object.keys(data.percentiles), "mean"],
      ...data.times_years.map((t, i) => [t, ...Object.values(data.percentiles).map((v) => v[i]), data.mean_path[i]]),
    ]);
  return (
    <div className="space-y-4">
      <Card
        title={`${data.n_paths.toLocaleString()} simulated paths over ${data.horizon_years} years`}
        subtitle={`Method: ${data.method.replace("_", " ")} · seed ${data.seed} · starting value ${money(data.initial_value)}`}
        actions={<ExportMenu name={`ardentum-monte-carlo-${data.seed}`} json={data} csv={csv} />}
      >
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-6">
          <Stat label="Median final value" value={money(p.p50, true)} sub={`5th–95th: ${money(p.p05, true)} – ${money(p.p95, true)}`} />
          <Stat label="Median annual growth" value={pct(data.cagr_percentiles.p50)} sub={`5th pct ${pct(data.cagr_percentiles.p05)}${data.net_cash_flow === 0 ? "" : " · time-weighted"}`} />
          <Stat
            label="Probability of loss"
            value={pct(data.probability_of_loss, 1)}
            sub={data.net_cash_flow === 0 ? "final value below start" : `final value below start + net flows (${money(data.initial_value + data.net_cash_flow, true)})`}
          />
          {data.probability_of_depletion != null && (
            <Stat
              label="Probability of running out"
              value={pct(data.probability_of_depletion, 1)}
              sub={data.depletion_years_percentiles ? `median after ${(data.depletion_years_percentiles.p50 ?? 0).toFixed(1)} years` : "no path ran out"}
              help="Share of paths whose wealth could not cover a withdrawal before the horizon."
            />
          )}
          <Stat label="Probability of target" value={data.probability_of_target == null ? "—" : pct(data.probability_of_target, 1)} sub={data.target_value ? `≥ ${money(data.target_value)}` : "no target set"} />
          <Stat label="Terminal VaR 95%" value={pct(data.terminal_return_var_95, 1)} sub={`CVaR ${pct(data.terminal_return_cvar_95, 1)}`} help="Loss of initial value exceeded in only 5% of paths; CVaR is the mean loss in that tail." />
          <Stat label="Median max drawdown" value={pct(data.max_drawdown_percentiles.p50, 1)} sub={`5% of paths worse than ${pct(data.max_drawdown_percentiles.p05, 1)}`} />
        </div>
      </Card>
      <ChartFrame
        title="Range of portfolio values"
        subtitle="Median path with the 25th–75th (darker) and 5th–95th (lighter) percentile bands at each point in time."
        legend={[
          { label: "Median", color: "var(--series-1)" },
          { label: "25th–75th percentile", color: "var(--series-1)", kind: "band" },
          { label: "5th–95th percentile", color: "var(--series-1)", kind: "band" },
        ]}
        table={
          <DataTable
            columns={[{ key: "t", label: "Year", align: "right" }, ...["p05", "p25", "p50", "p75", "p95"].map((k) => ({ key: k, label: k.replace("p0", "p").toUpperCase(), align: "right" as const }))]}
            rows={data.times_years.filter((_, i) => i % 12 === 0 || i === data.times_years.length - 1).map((t) => {
              const i = data.times_years.indexOf(t);
              return { t: t.toFixed(1), ...Object.fromEntries(["p05", "p25", "p50", "p75", "p95"].map((k) => [k, money(data.percentiles[k]?.[i])])) };
            })}
          />
        }
      >
        <FanChart times={data.times_years} percentiles={data.percentiles} format={(v) => money(v, true)} target={data.target_value} />
      </ChartFrame>
      <ChartFrame
        title="Distribution of final values"
        subtitle="Share of simulated paths ending in each range."
        table={
          <DataTable
            columns={[{ key: "r", label: "Range" }, { key: "c", label: "Paths", align: "right" }]}
            rows={data.terminal_histogram.counts.map((c, i) => ({ r: `${money(data.terminal_histogram.edges[i])} – ${money(data.terminal_histogram.edges[i + 1])}`, c }))}
          />
        }
      >
        <Histogram edges={data.terminal_histogram.edges} counts={data.terminal_histogram.counts} format={(v) => money(v, true)} marker={data.target_value} />
      </ChartFrame>
      <Callout tone="info" title="Assumptions">
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
