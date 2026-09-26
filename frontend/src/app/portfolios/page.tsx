"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useSavedPortfolios } from "@/components/portfolio-picker";
import { Badge, Button, Callout, Card, EmptyState, Table, Td, Th } from "@/components/ui";
import { download, ErrorCallout } from "@/components/workspace";
import { api, unwrap } from "@/lib/api/client";
import type { PortfolioOut } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { date as fmtDate, num, OBJECTIVE_LABELS, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

export default function PortfoliosPage() {
  const { status } = useAuth();
  const saved = useSavedPortfolios();
  const qc = useQueryClient();
  const router = useRouter();
  const { state, setUniverse, setWorking } = useWorkspace();
  const [error, setError] = useState<Error | null>(null);

  if (status === "loading") return null;
  if (status !== "signed_in") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <EmptyState
          title="Sign in to see your saved portfolios"
          action={
            <Link href="/login?next=/portfolios" className="inline-flex h-9 items-center rounded-md bg-accent px-4 text-sm font-medium text-white hover:bg-accent-hover">
              Sign in
            </Link>
          }
        >
          Saved portfolios keep their weights and the exact specification (data window, estimators, objective and constraints) that produced them.
        </EmptyState>
      </main>
    );
  }

  const open = (p: PortfolioOut) => {
    if (p.dataset_id !== state.universe.dataset_id) setUniverse({ dataset_id: p.dataset_id, tickers: Object.keys(p.weights) });
    setWorking({ name: p.name, datasetId: p.dataset_id, weights: p.weights, source: "saved", savedId: p.id, spec: p.spec ?? undefined });
    router.push("/app/simulate");
  };
  const remove = async (p: PortfolioOut) => {
    if (!window.confirm(`Delete “${p.name}”? This cannot be undone.`)) return;
    try {
      await unwrap(api.DELETE("/api/v1/portfolios/{portfolio_id}", { params: { path: { portfolio_id: p.id } } }));
      await qc.invalidateQueries({ queryKey: ["portfolios"] });
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    }
  };
  const exportAs = async (p: PortfolioOut, format: "csv" | "json") => {
    try {
      const res = await api.GET("/api/v1/portfolios/{portfolio_id}/export", {
        params: { path: { portfolio_id: p.id }, query: { format } },
        parseAs: "text",
      });
      if (!res.response.ok || typeof res.data !== "string") throw new Error("Export failed.");
      download(`${p.name.replace(/[^\w-]+/g, "_")}.${format}`, res.data, format === "csv" ? "text/csv" : "application/json");
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-ink">Saved portfolios</h1>
      <p className="mt-1 text-sm text-ink-2">Metrics were computed when the portfolio was saved, on the stated data window.</p>
      <div className="mt-4">
        <ErrorCallout error={error ?? saved.error} />
      </div>
      {saved.data && saved.data.length === 0 ? (
        <EmptyState title="No saved portfolios yet" action={<Link href="/app/optimise" className="text-sm text-accent-ink underline underline-offset-2">Optimise a portfolio</Link>}>
          Save a result from the optimiser to keep it here.
        </EmptyState>
      ) : (
        <Card bodyClassName="p-0">
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Objective</Th>
                <Th align="right">Assets</Th>
                <Th align="right">Exp. return</Th>
                <Th align="right">Volatility</Th>
                <Th align="right">Sharpe</Th>
                <Th>Updated</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {saved.data?.map((p) => {
                const s = (p.summary ?? {}) as Record<string, unknown>;
                return (
                  <tr key={p.id}>
                    <Td>
                      <span className="font-medium text-ink">{p.name}</span>
                      {s.is_synthetic === true && (
                        <span className="ml-2">
                          <Badge tone="synthetic">Synthetic data</Badge>
                        </span>
                      )}
                    </Td>
                    <Td className="text-ink-2">{OBJECTIVE_LABELS[String(s.objective)] ?? "—"}</Td>
                    <Td align="right">{Object.keys(p.weights).length}</Td>
                    <Td align="right">{pct(s.expected_return as number | undefined)}</Td>
                    <Td align="right">{pct(s.volatility as number | undefined)}</Td>
                    <Td align="right">{num(s.sharpe_ratio as number | undefined)}</Td>
                    <Td className="text-ink-2 whitespace-nowrap">{fmtDate(p.updated_at)}</Td>
                    <Td>
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="primary" onClick={() => open(p)}>
                          Open
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => void exportAs(p, "csv")}>
                          CSV
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => void exportAs(p, "json")}>
                          JSON
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => void remove(p)} aria-label={`Delete ${p.name}`}>
                          Delete
                        </Button>
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>
      )}
      <Callout tone="info" className="mt-4">
        Opening a portfolio makes it the working portfolio for simulation, backtesting and comparison.
      </Callout>
    </main>
  );
}
