"use client";

import { useState } from "react";

import { BarList } from "@/components/charts";
import { PortfolioPicker, resolvePortfolio, useAvailablePortfolios } from "@/components/portfolio-picker";
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
import type { FactorRequest, FactorResponse } from "@/lib/api/types";
import { date as fmtDate, num, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

const CLEAR = 0.05; // p-value below which a loading is called clear

type Loading = FactorResponse["factors"][number];

/** A plain sentence about a size or value tilt, or nothing when the loading is not clear. */
function tilt(f: Loading | undefined, positive: string, negative: string): string | null {
  if (!f || f.p_value >= CLEAR) return null;
  return f.loading > 0 ? positive : negative;
}

function summary(d: FactorResponse): string {
  const by = Object.fromEntries(d.factors.map((f) => [f.key, f]));
  const m = by.MKT_RF;
  const parts = [
    m ? `For each 1% the US market moved above the risk-free rate, this portfolio moved about ${num(m.loading, 2)}% on average.` : "",
  ];
  const leans = [
    tilt(by.SMB, "towards small companies", "towards large companies"),
    tilt(by.HML, "towards cheap (value) shares", "towards expensive (growth) shares"),
  ].filter(Boolean);
  parts.push(leans.length ? `It leans ${leans.join(" and ")}.` : "It shows no clear lean towards company size or value.");
  parts.push(
    d.alpha_p_value < CLEAR
      ? `Its return not explained by the three factors (alpha) was ${pct(d.alpha, 1)} a year, which is unlikely to be chance alone.`
      : `Its return not explained by the three factors (alpha) was ${pct(d.alpha, 1)} a year, which could be chance.`,
  );
  return parts.join(" ");
}

export default function FactorsPage() {
  const { state } = useWorkspace();
  const ds = useDataset(state.universe.dataset_id);
  const options = useAvailablePortfolios();
  const [pick, setPick] = useState("working");
  const { data, error, running, run } = useComputation<FactorRequest, FactorResponse>("factors", (req, signal) => runJob("factors", req, signal));
  const portfolio = resolvePortfolio(options, pick);

  const submit = () => {
    if (!portfolio) return;
    run({
      universe: { ...state.universe, tickers: Object.keys(portfolio.weights) },
      portfolio: { name: portfolio.name, weights: portfolio.weights },
    });
  };

  return (
    <>
      <PageHeader
        title="Factor exposure"
        description="How much a portfolio moved with the US stock market, with small companies and with cheap (value) shares, estimated from real returns over the window on the Universe page. This is the Fama-French three-factor model."
      />
      <SyntheticBanner dataset={ds.data} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="Portfolio">
            <PortfolioPicker value={pick} onChange={setPick} />
            <div className="mt-4">
              <RunBar running={running} label="Estimate" onRun={submit} disabled={!portfolio} />
            </div>
          </Card>
          <Card title="The three factors">
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="font-medium text-ink">Market</dt>
                <dd className="text-ink-2">The US stock market&apos;s return above the risk-free rate.</dd>
              </div>
              <div>
                <dt className="font-medium text-ink">Size</dt>
                <dd className="text-ink-2">Small companies&apos; shares minus large companies&apos; shares.</dd>
              </div>
              <div>
                <dt className="font-medium text-ink">Value</dt>
                <dd className="text-ink-2">Cheap shares (high book value for their price) minus expensive ones.</dd>
              </div>
            </dl>
          </Card>
        </aside>
        <div className="min-w-0">
          <ErrorCallout error={error} />
          {!data && running ? (
            <ResultsSkeleton />
          ) : !data ? (
            <EmptyState title="No estimate yet">Pick a portfolio and estimate. Factor exposure needs real returns: choose US industries or your own data on the Universe page.</EmptyState>
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

function Results({ data }: { data: FactorResponse }) {
  const csv = () =>
    toCsv([
      ["term", "loading", "std_error", "t_stat", "p_value", "factor_mean_annual", "contribution_annual"],
      ["alpha (annual)", data.alpha, data.alpha_std_error, data.alpha_t_stat, data.alpha_p_value, "", data.alpha],
      ...data.factors.map((f) => [f.name, f.loading, f.std_error, f.t_stat, f.p_value, f.factor_mean, f.contribution]),
    ]);
  const by = Object.fromEntries(data.factors.map((f) => [f.key, f]));
  return (
    <div className="space-y-4">
      <Card
        title={data.portfolio_name}
        subtitle={`${data.observations.toLocaleString()} returns from ${fmtDate(data.first_period)} to ${fmtDate(data.last_period)}`}
        actions={<ExportMenu name="ardentum-factor-exposure" json={data} csv={csv} />}
      >
        <p className="text-sm text-ink">{summary(data)}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-5">
          <Stat label="Market loading" value={num(by.MKT_RF?.loading, 2)} sub={`t-stat ${num(by.MKT_RF?.t_stat, 1)}`} />
          <Stat label="Size loading" value={num(by.SMB?.loading, 2)} sub={`t-stat ${num(by.SMB?.t_stat, 1)}`} />
          <Stat label="Value loading" value={num(by.HML?.loading, 2)} sub={`t-stat ${num(by.HML?.t_stat, 1)}`} />
          <Stat label="Alpha" value={pct(data.alpha, 1)} sub={`a year · t-stat ${num(data.alpha_t_stat, 1)}`} />
          <Stat label="R-squared" value={pct(data.r_squared, 0)} sub="of the ups and downs explained" />
        </div>
      </Card>
      <Card title="Loadings" subtitle="How much the portfolio moved per unit of each factor, with Newey-West standard errors." bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <Th>Factor</Th>
              <Th align="right">Loading</Th>
              <Th align="right">Std. error</Th>
              <Th align="right">t-stat</Th>
              <Th align="right">p-value</Th>
              <Th>Clear?</Th>
            </tr>
          </thead>
          <tbody>
            {data.factors.map((f) => (
              <tr key={f.key}>
                <Td>
                  <span className="font-medium text-ink">{f.name}</span>
                  <span className="block text-[11px] text-muted">{f.description}</span>
                </Td>
                <Td align="right">{num(f.loading, 3)}</Td>
                <Td align="right">{num(f.std_error, 3)}</Td>
                <Td align="right">{num(f.t_stat, 2)}</Td>
                <Td align="right">{num(f.p_value, 3)}</Td>
                <Td className="text-ink-2">{f.p_value < CLEAR ? "yes" : "no"}</Td>
              </tr>
            ))}
            <tr>
              <Td>
                <span className="font-medium text-ink">Alpha (a year)</span>
                <span className="block text-[11px] text-muted">Average return the factors do not explain.</span>
              </Td>
              <Td align="right">{pct(data.alpha, 2)}</Td>
              <Td align="right">{pct(data.alpha_std_error, 2)}</Td>
              <Td align="right">{num(data.alpha_t_stat, 2)}</Td>
              <Td align="right">{num(data.alpha_p_value, 3)}</Td>
              <Td className="text-ink-2">{data.alpha_p_value < CLEAR ? "yes" : "no"}</Td>
            </tr>
          </tbody>
        </Table>
        <p className="px-4 py-2 text-[11px] text-muted">
          &quot;Clear&quot; means a p-value below 5%: a loading this far from zero would rarely appear by chance if the true loading were zero.
        </p>
      </Card>
      <Card
        title="Where the average return came from"
        subtitle={`The portfolio earned ${pct(data.mean_excess_return, 1)} a year above the risk-free rate on average: each factor's loading times its average return, plus alpha.`}
      >
        <BarList
          ariaLabel="Parts of the average return above the risk-free rate"
          rows={[
            ...data.factors.map((f) => ({
              key: f.key,
              label: f.name,
              sub: `${num(f.loading, 2)} × ${pct(f.factor_mean, 1)} a year`,
              value: f.contribution,
              display: pct(f.contribution, 1),
            })),
            { key: "alpha", label: "Alpha", sub: "not explained", value: data.alpha, display: pct(data.alpha, 1) },
          ]}
        />
      </Card>
      <Card title="Each holding" subtitle="The portfolio's loadings are these, weighted by the holdings." bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <Th>Asset</Th>
              <Th align="right">Weight</Th>
              <Th align="right">Market</Th>
              <Th align="right">Size</Th>
              <Th align="right">Value</Th>
              <Th align="right">Alpha</Th>
              <Th align="right">R-squared</Th>
            </tr>
          </thead>
          <tbody>
            {data.assets.map((a) => (
              <tr key={a.ticker}>
                <Td className="font-medium">{a.ticker}</Td>
                <Td align="right">{pct(a.weight, 1)}</Td>
                <Td align="right">{num(a.loadings.MKT_RF, 2)}</Td>
                <Td align="right">{num(a.loadings.SMB, 2)}</Td>
                <Td align="right">{num(a.loadings.HML, 2)}</Td>
                <Td align="right">{pct(a.alpha, 1)}</Td>
                <Td align="right">{pct(a.r_squared, 0)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <Callout tone="info" title="Method">
        <p>{data.method}</p>
        <p className="mt-1">
          Residual volatility {pct(data.residual_volatility, 1)} a year · adjusted R-squared {pct(data.adj_r_squared, 0)} · {data.newey_west_lags} Newey-West lags.
        </p>
        <p className="mt-1 text-[11px] text-muted">{data.factor_source}</p>
      </Callout>
      {data.notes.length > 0 && (
        <Callout tone="warning" title="Notes">
          <ul className="list-disc space-y-0.5 pl-4">
            {data.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Callout>
      )}
      <DataNotes data={data.data} />
    </div>
  );
}
