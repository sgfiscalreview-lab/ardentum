"use client";

import { useQuery } from "@tanstack/react-query";

import { Callout, Card, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { date, month, num } from "@/lib/format";

const LABELS: Record<string, string> = {
  analytics: "Historical analytics",
  optimise: "Optimisations",
  frontier: "Efficient frontiers",
  cvar_frontier: "Mean-CVaR frontiers",
  esg_impact: "ESG impact analyses",
  montecarlo: "Monte Carlo simulations",
  backtest: "Walk-forward backtests",
  compare: "Portfolio comparisons",
  portfolio_saved: "Portfolios saved",
  portfolio_exported: "Saved portfolios exported",
  dataset_uploaded: "Datasets uploaded",
};

export function UsageView() {
  const q = useQuery({ queryKey: ["usage"], queryFn: () => unwrap(api.GET("/api/v1/usage")) });
  if (q.isPending) {
    return (
      <div className="mt-8">
        <SkeletonRows rows={8} label="Loading usage counts" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <Callout tone="error" title="Usage counts are unavailable" className="mt-8">
        {q.error.message}
      </Callout>
    );
  }
  const u = q.data;
  return (
    <div className="mt-8 space-y-6">
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-sm border border-line bg-surface px-4 py-3">
          <dt className="text-xs text-ink-2">Calculations completed</dt>
          <dd className="mt-1 text-2xl font-semibold text-ink tabular">{num(u.total_calculations, 0)}</dd>
        </div>
        <div className="rounded-sm border border-line bg-surface px-4 py-3">
          <dt className="text-xs text-ink-2">Counting since</dt>
          <dd className="mt-1 text-2xl font-semibold text-ink">{date(u.since)}</dd>
        </div>
        <div className="rounded-sm border border-line bg-surface px-4 py-3">
          <dt className="text-xs text-ink-2">Figures as of</dt>
          <dd className="mt-1 text-2xl font-semibold text-ink">{date(u.as_of)}</dd>
        </div>
      </dl>
      <Card title="By kind" subtitle="The last 30 days include today (UTC).">
        <Table>
          <thead>
            <tr>
              <Th>Kind</Th>
              <Th align="right">Last 30 days</Th>
              <Th align="right">Total</Th>
            </tr>
          </thead>
          <tbody>
            {u.events.map((e) => (
              <tr key={e.event}>
                <Td>{LABELS[e.event] ?? e.event}</Td>
                <Td align="right">{num(e.last_30_days, 0)}</Td>
                <Td align="right">{num(e.total, 0)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <Card title="Calculations by month" subtitle="Months are UTC calendar months.">
        {u.months.length === 0 ? (
          <p className="text-sm text-ink-2">No calculations have been counted yet.</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Month</Th>
                <Th align="right">Calculations</Th>
              </tr>
            </thead>
            <tbody>
              {u.months.map((m) => (
                <tr key={m.month}>
                  <Td>{month(m.month)}</Td>
                  <Td align="right">{num(m.calculations, 0)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
