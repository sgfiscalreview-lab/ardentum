"use client";

import { BarList, ChartFrame, DataTable, TimeSeriesChart } from "@/components/charts";
import { ConstraintsPanel, ObjectivePanel } from "@/components/forms";
import { Callout, Card, EmptyState, Stat, Table, Td, Th } from "@/components/ui";
import {
  DataNotes,
  ErrorCallout,
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
import type { EsgImpactRequest, EsgImpactResponse, PortfolioResultOut } from "@/lib/api/types";
import { num, pct, signedNum, signedPct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

export default function EsgPage() {
  const { state, setObjective, setConstraints } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const c = state.constraints;
  const hasEsg = c.min_esg_score != null || (c.esg_tilt ?? 0) > 0 || (c.excluded_sectors ?? []).length > 0 || !!c.exclude_unscored_assets;
  const { data, error, running, run } = useComputation<EsgImpactRequest, EsgImpactResponse>("esg", (req, signal) =>
    runJob("esg_impact", req, signal),
  );
  return (
    <>
      <PageHeader
        title="ESG impact"
        description="ESG settings change the optimisation itself. This page solves the same problem with and without them and reports the difference in return, risk, Sharpe ratio, composition and tracking error."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Objective">
            <ObjectivePanel value={state.objective} onChange={setObjective} />
          </Card>
          <Card title="Constraints" subtitle="The baseline keeps every non-ESG constraint; ESG settings are the minimum score, tilt, sector exclusions and exclusion of unscored assets.">
            <ConstraintsPanel value={c} onChange={setConstraints} assets={ds.data?.assets ?? []} tickers={state.universe.tickers} />
          </Card>
          <Card>
            <RunBar
              running={running}
              label="Measure ESG impact"
              disabled={!hasEsg}
              note={!hasEsg ? "Set at least one ESG constraint first." : undefined}
              onRun={() => run({ universe: state.universe, estimation: state.estimation, objective: state.objective, constraints: c })}
            />
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data && running ? (
            <ResultsSkeleton />
          ) : !data ? (
            <EmptyState title="No comparison yet">
              Add an ESG constraint (for example a minimum portfolio score of 60, or excluding Energy), then measure its effect.
            </EmptyState>
          ) : (
            <Running running={running}>
              <Impact data={data} />
            </Running>
          )}
        </div>
      </div>
    </>
  );
}

function Impact({ data }: { data: EsgImpactResponse }) {
  const b = data.baseline;
  const e = data.esg;
  const frontier = data.esg_frontier.filter((p) => p.feasible && p.sharpe_ratio != null);
  const csv = () =>
    toCsv([
      ["ticker", "sector", "esg_score", "baseline_weight", "esg_weight", "change"],
      ...data.weight_changes.map((w) => [w.ticker, w.sector, w.esg_score, w.baseline_weight, w.esg_weight, w.change]),
    ]);
  return (
    <div className="space-y-4">
      <Card
        title="Effect of the ESG settings"
        subtitle="ESG portfolio minus baseline portfolio. Same objective, estimates and non-ESG constraints."
        actions={<ExportMenu name="ardentum-esg-impact" json={data} csv={csv} />}
      >
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-6">
          <Stat label="ESG score" value={e.esg_score == null ? "n/a" : num(e.esg_score, 1)} sub={`${signedNum(data.delta_esg_score, 1)} vs baseline`} />
          <Stat label="Expected return" value={pct(e.expected_return)} sub={`${signedPct(data.delta_expected_return)} vs baseline`} tone={data.delta_expected_return < -1e-6 ? "critical" : undefined} />
          <Stat label="Volatility" value={pct(e.volatility)} sub={`${signedPct(data.delta_volatility)} vs baseline`} tone={data.delta_volatility > 1e-6 ? "critical" : undefined} />
          <Stat label="Sharpe ratio" value={num(e.sharpe_ratio)} sub={`${signedNum(data.delta_sharpe_ratio)} vs baseline`} tone={(data.delta_sharpe_ratio ?? 0) < -1e-6 ? "critical" : undefined} />
          <Stat label="Tracking error (ex ante)" value={pct(data.ex_ante_tracking_error)} sub="vs baseline, annual" help="√((w_esg − w_base)ᵀ Σ (w_esg − w_base))" />
          <Stat label="Tracking error (in-sample)" value={pct(data.ex_post_tracking_error)} sub="realised on the window" help={data.ex_post_tracking_error_note} />
        </div>
        <p className="mt-3 text-xs text-ink-2">
          A constraint can never improve the objective it is added to, so for a maximum-Sharpe objective the Sharpe change is ≤ 0 by construction. Its size is the estimated cost of the ESG requirement under these inputs.
        </p>
      </Card>

      {[...e.warnings].length > 0 && (
        <Callout tone="warning">
          <ul className="list-disc pl-4">
            {e.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}

      <div className="grid gap-4 2xl:grid-cols-2">
        <ChartFrame
          title="Weight changes"
          subtitle="ESG weight minus baseline weight. Blue: increased; red: reduced."
          table={
            <DataTable
              columns={[
                { key: "t", label: "Asset" },
                { key: "e", label: "ESG", align: "right" },
                { key: "b", label: "Baseline", align: "right" },
                { key: "n", label: "ESG portfolio", align: "right" },
                { key: "c", label: "Change", align: "right" },
              ]}
              rows={data.weight_changes.map((w) => ({ t: w.ticker, e: w.esg_score == null ? "n/a" : num(w.esg_score, 0), b: pct(w.baseline_weight, 1), n: pct(w.esg_weight, 1), c: signedPct(w.change, 1) }))}
            />
          }
        >
          <div className="px-2">
            <BarList
              ariaLabel="Weight changes"
              rows={data.weight_changes.map((w) => ({
                key: w.ticker,
                label: w.ticker,
                sub: `ESG ${w.esg_score == null ? "n/a" : w.esg_score.toFixed(0)} · ${w.sector ?? ""}`,
                value: w.change,
                display: signedPct(w.change, 1),
                color: w.change >= 0 ? "var(--diverge-pos)" : "var(--diverge-neg)",
              }))}
            />
          </div>
        </ChartFrame>
        <ChartFrame
          title="ESG-efficient frontier"
          subtitle="Best achievable Sharpe ratio as the minimum portfolio ESG score rises (Pedersen, Fitzgibbons & Pomorski 2021)."
          table={
            <DataTable
              columns={[
                { key: "m", label: "Min ESG", align: "right" },
                { key: "s", label: "Max Sharpe", align: "right" },
                { key: "r", label: "Return", align: "right" },
                { key: "v", label: "Volatility", align: "right" },
              ]}
              rows={data.esg_frontier.map((p) => ({ m: num(p.min_esg_score, 1), s: p.feasible ? num(p.sharpe_ratio) : "infeasible", r: pct(p.expected_return), v: pct(p.volatility) }))}
            />
          }
        >
          {frontier.length > 1 ? (
            <TimeSeriesChart
              dates={frontier.map((p) => p.min_esg_score.toFixed(1))}
              xFormat={(d) => d}
              series={[{ key: "s", name: "Maximum Sharpe ratio", values: frontier.map((p) => p.sharpe_ratio ?? Number.NaN), color: "var(--series-3)" }]}
              yFormat={(v) => v.toFixed(2)}
              height={240}
            />
          ) : (
            <p className="px-2 text-sm text-ink-2">Not enough feasible ESG levels to draw the curve.</p>
          )}
          <p className="px-2 text-[11px] text-muted">Horizontal axis: minimum portfolio ESG score. Levels above the best-scoring asset are infeasible.</p>
        </ChartFrame>
      </div>

      <Card title="Sector exposure" bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <Th>Sector</Th>
              <Th align="right">Baseline</Th>
              <Th align="right">ESG</Th>
              <Th align="right">Change</Th>
            </tr>
          </thead>
          <tbody>
            {data.sector_changes.map((s) => (
              <tr key={String(s.sector)}>
                <Td>{String(s.sector)}</Td>
                <Td align="right">{pct(Number(s.baseline), 1)}</Td>
                <Td align="right">{pct(Number(s.esg), 1)}</Td>
                <Td align="right">{signedPct(Number(s.change), 1)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Summary title="Baseline (no ESG settings)" r={b} />
        <Summary title="With ESG settings" r={e} />
      </div>

      <Callout tone="info" title="About the ESG data">
        <ul className="list-disc pl-4">
          {data.esg_data_notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </Callout>
      <DataNotes data={data.data} />
    </div>
  );
}

function Summary({ title, r }: { title: string; r: PortfolioResultOut }) {
  return (
    <Card title={title}>
      <dl className="grid grid-cols-2 gap-y-1 text-sm">
        <dt className="text-ink-2">Expected return</dt>
        <dd className="text-right tabular">{pct(r.expected_return)}</dd>
        <dt className="text-ink-2">Volatility</dt>
        <dd className="text-right tabular">{pct(r.volatility)}</dd>
        <dt className="text-ink-2">Sharpe</dt>
        <dd className="text-right tabular">{num(r.sharpe_ratio)}</dd>
        <dt className="text-ink-2">ESG score</dt>
        <dd className="text-right tabular">{r.esg_score == null ? "n/a" : num(r.esg_score, 1)}</dd>
        <dt className="text-ink-2">Effective no. of assets</dt>
        <dd className="text-right tabular">{num(r.effective_number_of_assets, 1)}</dd>
      </dl>
    </Card>
  );
}
