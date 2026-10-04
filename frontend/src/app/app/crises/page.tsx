"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { BarList, ChartFrame, DataTable, TimeSeriesChart } from "@/components/charts";
import { PortfolioPicker, resolvePortfolio, useAvailablePortfolios } from "@/components/portfolio-picker";
import { Callout, Card, Checkbox, EmptyState, Field, Input, Select, Table, Td, Th } from "@/components/ui";
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
import { api, runJob, unwrap } from "@/lib/api/client";
import type { EpisodeOut, StressRequest, StressResponse } from "@/lib/api/types";
import { date as fmtDate, duration, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

function recovery(e: EpisodeOut, dataEnd: string): string {
  if (e.trough_date == null) return "did not fall";
  if (e.recovery_date == null || e.recovery_days == null) return `not by ${fmtDate(dataEnd)}`;
  return `${duration(e.recovery_days)} after the low (${fmtDate(e.recovery_date)})`;
}

export default function CrisesPage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const catalogue = useQuery({ queryKey: ["stress", "crises"], queryFn: () => unwrap(api.GET("/api/v1/stress/crises")), staleTime: Infinity });
  const { data, error, running, run, request } = useComputation<StressRequest, StressResponse>("stress", (req, signal) => runJob("stress", req, signal));
  const [pick, setPick] = useState("working");
  const [chosen, setChosen] = useState<string[] | null>(request?.episodes ?? null);
  const [custom, setCustom] = useState(request?.custom != null);
  const [customName, setCustomName] = useState(request?.custom?.name ?? "Your period");
  const [start, setStart] = useState(request?.custom?.start ?? "");
  const [end, setEnd] = useState(request?.custom?.end ?? "");
  const portfolio = resolvePortfolio(options, pick);
  const all = catalogue.data?.map((c) => c.key) ?? [];
  const selected = chosen ?? all;
  const customReady = !custom || (start !== "" && end !== "" && start < end);

  const submit = () => {
    if (!portfolio) return;
    run({
      universe: { ...state.universe, tickers: Object.keys(portfolio.weights) },
      portfolio: { name: portfolio.name, weights: portfolio.weights },
      episodes: chosen,
      custom: custom ? { name: customName.trim() || "Your period", start, end } : null,
    });
  };

  return (
    <>
      <PageHeader
        title="Crisis replay"
        description="What would have happened to a portfolio bought just before past market crashes and then held without trading. Each crisis runs from the US market's high to its low, using real daily returns from the whole history of the data, not just the window on the Universe page."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Portfolio">
            <PortfolioPicker value={pick} onChange={setPick} />
          </Card>
          <Card title="Crises" subtitle="Market high to market low.">
            <div className="space-y-2">
              {catalogue.data?.map((c) => (
                <Checkbox
                  key={c.key}
                  checked={selected.includes(c.key)}
                  onChange={(v) => setChosen(v ? [...selected, c.key] : selected.filter((k) => k !== c.key))}
                  label={c.name}
                  hint={`${fmtDate(c.start)} to ${fmtDate(c.end)}`}
                />
              ))}
              <Checkbox checked={custom} onChange={setCustom} label="Your own dates" hint="Any period the data covers, also on demo data." />
              {custom && (
                <div className="grid grid-cols-2 gap-3 pl-6">
                  <Field label="Name" htmlFor="custom-name" className="col-span-2">
                    <Input id="custom-name" value={customName} maxLength={80} onChange={(e) => setCustomName(e.target.value)} />
                  </Field>
                  <Field label="Bought at the close on" htmlFor="custom-start">
                    <Input id="custom-start" type="date" value={start} max={end || undefined} onChange={(e) => setStart(e.target.value)} />
                  </Field>
                  <Field label="Held until" htmlFor="custom-end">
                    <Input id="custom-end" type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} />
                  </Field>
                </div>
              )}
            </div>
            <div className="mt-4">
              <RunBar
                running={running}
                label="Replay"
                onRun={submit}
                disabled={!portfolio || (selected.length === 0 && !custom) || !customReady}
                note={!customReady ? "Enter a start before the end." : undefined}
              />
            </div>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error ?? catalogue.error} />
          {!data && running ? (
            <ResultsSkeleton />
          ) : !data ? (
            <EmptyState title="No replay yet">
              Pick a portfolio and the crises to replay. The famous crashes need real data: choose US industries on the Universe page.
            </EmptyState>
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

function Results({ data }: { data: StressResponse }) {
  const available = data.episodes.filter((e) => e.available);
  const [focus, setFocus] = useState<string>(available[0]?.key ?? "");
  const current = available.find((e) => e.key === focus) ?? available[0];
  const market = data.benchmark_name ? "Market" : null;
  const csv = () =>
    toCsv([
      ["crisis", "start", "end", "portfolio_return", "market_return", "max_drawdown", "worst_day_return", "worst_day", "low", "back_to_previous_high", "reason"],
      ...data.episodes.map((e) => [
        e.name,
        e.start,
        e.end,
        e.total_return,
        e.benchmark_total_return,
        e.max_drawdown,
        e.worst_day_return,
        e.worst_day,
        e.trough_date,
        e.recovery_date,
        e.reason,
      ]),
    ]);
  return (
    <div className="space-y-4">
      <Card
        title={`${data.portfolio_name} through past crises`}
        subtitle={data.benchmark_name ? `Market: ${data.benchmark_name}` : "This dataset has no market index to compare with."}
        bodyClassName="p-0"
        actions={<ExportMenu name="ardentum-crisis-replay" json={data} csv={csv} />}
      >
        <Table>
          <thead>
            <tr>
              <Th>Crisis</Th>
              <Th align="right">Portfolio</Th>
              {market && <Th align="right">Market</Th>}
              <Th align="right">Largest fall</Th>
              <Th align="right">Worst day</Th>
              <Th>Back to its previous high</Th>
            </tr>
          </thead>
          <tbody>
            {data.episodes.map((e) =>
              e.available ? (
                <tr key={e.key}>
                  <Td>
                    <span className="font-medium text-ink">{e.name}</span>
                    <span className="block text-[11px] text-muted">
                      {fmtDate(e.start)} to {fmtDate(e.end)}
                    </span>
                  </Td>
                  <Td align="right">{pct(e.total_return, 1)}</Td>
                  {market && <Td align="right">{pct(e.benchmark_total_return, 1)}</Td>}
                  <Td align="right">{pct(e.max_drawdown, 1)}</Td>
                  <Td align="right">
                    {pct(e.worst_day_return, 1)}
                    <span className="block text-[11px] text-muted">{fmtDate(e.worst_day)}</span>
                  </Td>
                  <Td className="text-ink-2">{recovery(e, data.data_end)}</Td>
                </tr>
              ) : (
                <tr key={e.key}>
                  <Td>
                    <span className="font-medium text-ink">{e.name}</span>
                    <span className="block text-[11px] text-muted">
                      {fmtDate(e.start)} to {fmtDate(e.end)}
                    </span>
                  </Td>
                  <Td colSpan={market ? 5 : 4} className="text-ink-2">
                    Not available: {e.reason}
                  </Td>
                </tr>
              ),
            )}
          </tbody>
        </Table>
      </Card>
      {current && (
        <EpisodeDetail
          episode={current}
          benchmarkName={data.benchmark_name}
          choices={available.map((e) => ({ key: e.key, name: e.name }))}
          onChoose={setFocus}
        />
      )}
      <Callout tone="info" title="How the replay works">
        <p>{data.method}</p>
        <p className="mt-1 text-[11px] text-muted">{data.source}</p>
      </Callout>
      <DataNotes data={data.data} />
    </div>
  );
}

function EpisodeDetail({
  episode: e,
  benchmarkName,
  choices,
  onChoose,
}: {
  episode: EpisodeOut;
  benchmarkName: string | null;
  choices: { key: string; name: string }[];
  onChoose: (key: string) => void;
}) {
  // Axis labels: years for long periods, months for medium ones, days for a few months.
  const span = e.dates.length;
  const tick =
    span > 400
      ? undefined
      : (d: string) =>
          new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", span > 130 ? { month: "short", year: "numeric", timeZone: "UTC" } : { day: "numeric", month: "short", timeZone: "UTC" });
  const series = [
    { key: "portfolio", name: "Portfolio", values: e.portfolio_path },
    ...(e.benchmark_path ? [{ key: "market", name: benchmarkName ?? "Market", values: e.benchmark_path }] : []),
  ];
  const assets = [...e.assets].sort((a, b) => a.contribution - b.contribution);
  return (
    <>
      <ChartFrame
        title={`Value of 1 invested at the close on ${fmtDate(e.start)}`}
        subtitle={e.summary}
        actions={
          choices.length > 1 ? (
            <Select aria-label="Crisis shown" value={e.key} onChange={(ev) => onChoose(ev.target.value)} className="h-8 text-xs">
              {choices.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.name}
                </option>
              ))}
            </Select>
          ) : undefined
        }
        legend={series.map((s, i) => ({ label: s.name, color: `var(--series-${i + 1})` }))}
        table={
          <DataTable
            columns={[{ key: "d", label: "Date" }, ...series.map((s) => ({ key: s.key, label: s.name, align: "right" as const }))]}
            rows={e.dates
              .filter((_, i) => i % Math.max(1, Math.round(e.dates.length / 40)) === 0 || i === e.dates.length - 1)
              .map((d) => {
                const i = e.dates.indexOf(d);
                return { d: fmtDate(d), ...Object.fromEntries(series.map((s) => [s.key, (s.values[i] ?? NaN).toFixed(3)])) };
              })}
          />
        }
      >
        <TimeSeriesChart
          dates={e.dates}
          series={series}
          yFormat={(v) => v.toFixed(2)}
          baseline={1}
          xFormat={tick}
        />
      </ChartFrame>
      <Card title="What each holding contributed" subtitle="Weight at purchase times the holding's return over the period. The contributions add up to the portfolio's return.">
        <BarList
          ariaLabel="Contribution of each holding"
          rows={assets.map((a) => ({
            key: a.ticker,
            label: a.ticker,
            sub: `${pct(a.weight, 1)} held, returned ${pct(a.total_return, 1)}`,
            value: a.contribution,
            display: pct(a.contribution, 1),
          }))}
        />
      </Card>
    </>
  );
}
