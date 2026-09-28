"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Badge, Button, Callout, Card, EmptyState, Field, Input, NumberInput, Select, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { ErrorCallout, PageHeader, useDataset } from "@/components/workspace";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { CompositePreviewOut, CompositePreviewRequest, EsgTransformIn, OpenCompanyOut, OpenMetricOut, OverlayEntryOut, OverlayPreviewOut } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { num } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

const STATUS: Record<OverlayEntryOut["status"], { label: string; tone: "good" | "warn" | "neutral" }> = {
  scored: { label: "Scored", tone: "good" },
  incomplete: { label: "Incomplete", tone: "warn" },
  no_company: { label: "No match", tone: "warn" },
  no_answer: { label: "No data", tone: "neutral" },
  not_numeric: { label: "Not numeric", tone: "neutral" },
};

const MAX_COMPONENTS = 6;

interface Component {
  metric: OpenMetricOut;
  transform: EsgTransformIn;
  year: number | null;
  weight: number;
}

function describe(t: EsgTransformIn): string {
  const dir = t.higher_is_better ? "higher is better" : "lower is better";
  return t.method === "linear" ? `fixed scale ${t.lower ?? "range"} to ${t.upper ?? "range"}, ${dir}` : `percentile rank, ${dir}`;
}

function asError(e: unknown): Error {
  return e instanceof ApiError || e instanceof Error ? e : new Error(String(e));
}

export default function EsgDataPage() {
  const { state, setUniverse } = useWorkspace();
  const u = state.universe;
  const ds = useDataset(u.dataset_id);
  const { status } = useAuth();
  const qc = useQueryClient();

  const [q, setQ] = useState("");
  const [metrics, setMetrics] = useState<OpenMetricOut[] | null>(null);
  const [metric, setMetric] = useState<OpenMetricOut | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [transform, setTransform] = useState<EsgTransformIn>({ method: "percentile", higher_is_better: true, lower: null, upper: null });
  const [overrides, setOverrides] = useState<Record<string, OpenCompanyOut>>({});
  const [preview, setPreview] = useState<OverlayPreviewOut | null>(null);
  const [components, setComponents] = useState<Component[]>([]);
  const [composite, setComposite] = useState<CompositePreviewOut | null>(null);
  const [mode, setMode] = useState<"single" | "composite">("single");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const overlays = useQuery({
    queryKey: ["esg-overlays"],
    queryFn: () => unwrap(api.GET("/api/v1/esg/overlays")),
    enabled: status === "signed_in",
  });

  const unsupported = ds.data && (ds.data.is_synthetic || u.dataset_id === "kf12" || u.dataset_id === "kf49");

  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(asError(e));
    } finally {
      setBusy(null);
    }
  };

  const search = () =>
    act("search", async () => {
      setMetrics(await unwrap(api.GET("/api/v1/esg/open/metrics", { params: { query: { q, limit: 20 } } })));
    });

  const runPreview = (ov = overrides) =>
    act("preview", async () => {
      if (!metric) return;
      setSaved(null);
      const res = await unwrap(
        api.POST("/api/v1/esg/open/preview", {
          body: {
            dataset_id: u.dataset_id,
            tickers: u.tickers,
            metric_id: metric.id,
            year,
            transform,
            company_overrides: Object.fromEntries(Object.entries(ov).map(([t, c]) => [t, c.id])),
          },
        }),
      );
      setPreview(res);
      setMode("single");
      if (!name) setName(`${metric.title}`.slice(0, 120));
    });

  const compositeBody = (ov: Record<string, OpenCompanyOut>): CompositePreviewRequest => ({
    dataset_id: u.dataset_id,
    tickers: u.tickers,
    components: components.map((c) => ({ metric_id: c.metric.id, weight: c.weight, year: c.year, transform: c.transform })),
    company_overrides: Object.fromEntries(Object.entries(ov).map(([t, c]) => [t, c.id])),
  });

  const runComposite = (ov = overrides) =>
    act("composite", async () => {
      if (components.length < 2) return;
      setSaved(null);
      setComposite(await unwrap(api.POST("/api/v1/esg/open/composite-preview", { body: compositeBody(ov) })));
      setMode("composite");
      setName(`Composite: ${components.map((c) => c.metric.title).join(" + ")}`.slice(0, 120));
    });

  const addComponent = () => {
    if (!metric || components.some((c) => c.metric.id === metric.id) || components.length >= MAX_COMPONENTS) return;
    setComponents([...components, { metric, transform, year, weight: 1 }]);
  };

  const activeScored = mode === "composite" ? (composite?.scored ?? null) : (preview?.scored ?? null);

  const pickCompany = (ticker: string, c: OpenCompanyOut) => {
    const next = { ...overrides, [ticker]: c };
    setOverrides(next);
    if (mode === "composite") runComposite(next);
    else runPreview(next);
  };

  const save = () =>
    act("save", async () => {
      let body;
      if (mode === "composite") {
        if (!composite) return;
        body = { name: name.trim() || "Composite ESG score", composite: compositeBody(overrides) };
      } else {
        if (!metric || !preview) return;
        body = {
          name: name.trim() || metric.title,
          preview: {
            dataset_id: u.dataset_id,
            tickers: u.tickers,
            metric_id: metric.id,
            year,
            transform,
            company_overrides: Object.fromEntries(Object.entries(overrides).map(([t, c]) => [t, c.id])),
          },
        };
      }
      const res = await unwrap(api.POST("/api/v1/esg/overlays", { body }));
      await qc.invalidateQueries({ queryKey: ["esg-overlays"] });
      setUniverse({ esg_overlay_id: res.id });
      setSaved(`Saved “${res.name}” and applied it to the workspace (${res.scored} of ${res.entries.length} assets scored).`);
    });

  return (
    <>
      <PageHeader
        title="Open ESG data"
        description="Build ESG scores for your assets from WikiRate, a free, community-researched database of company disclosures (CC BY 4.0). Every score links to its source answer; assets without data stay unscored."
      />
      {unsupported && (
        <Callout tone="info" title="Choose a dataset of real companies">
          {ds.data?.is_synthetic
            ? "The demo assets are fictional, so real companies' data cannot be matched to them."
            : "Industry portfolios are not companies, so company-level ESG data does not apply."}{" "}
          <Link href="/app" className="underline underline-offset-2">
            Upload your own prices
          </Link>{" "}
          with an <code>isin</code> column for automatic matching.
        </Callout>
      )}
      <ErrorCallout error={error} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card title="1. Metric" subtitle="Search WikiRate, e.g. “scope 1”, “water”, “women”, “fines”.">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (q.trim().length >= 2) search();
              }}
            >
              <Input aria-label="Search metrics" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search metrics" />
              <Button type="submit" busy={busy === "search"} disabled={q.trim().length < 2}>
                Search
              </Button>
            </form>
            {metrics && (
              <ul className="mt-3 max-h-80 space-y-1.5 overflow-y-auto">
                {metrics.length === 0 && <li className="text-xs text-muted">No metrics found.</li>}
                {metrics.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      disabled={!m.numeric}
                      onClick={() => {
                        setMetric(m);
                        setPreview(null);
                        setTransform((t) => ({ ...t, lower: null, upper: null }));
                      }}
                      aria-pressed={metric?.id === m.id}
                      className={`w-full rounded-md border p-2 text-left text-xs disabled:opacity-60 ${metric?.id === m.id ? "border-accent bg-accent-wash" : "border-line hover:bg-surface-2"}`}
                    >
                      <span className="block font-medium text-ink">{m.title}</span>
                      <span className="block text-muted">
                        {m.designer} · {m.value_type ?? "n/a"}
                        {m.unit ? ` (${m.unit})` : ""}
                        {m.answers != null ? ` · ${m.answers.toLocaleString()} answers` : ""}
                      </span>
                      {!m.numeric && <span className="block text-muted">Not numeric: cannot become a score.</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="2. Scoring">
            <div className="space-y-3">
              <Field label="Direction" htmlFor="dir" hint="For emissions, fines or accidents, lower values are better.">
                <Select id="dir" value={transform.higher_is_better ? "higher" : "lower"} onChange={(e) => setTransform({ ...transform, higher_is_better: e.target.value === "higher" })}>
                  <option value="higher">Higher values are better</option>
                  <option value="lower">Lower values are better</option>
                </Select>
              </Field>
              <Field
                label="Scale"
                htmlFor="method"
                hint={
                  transform.method === "percentile"
                    ? "Rank among your matched companies: best 100, worst 0. Relative only: it changes if the group changes."
                    : "Fixed scale: the raw value mapped to 0 and to 100 (clipped outside). Comparable across groups."
                }
              >
                <Select id="method" value={transform.method} onChange={(e) => setTransform({ ...transform, method: e.target.value as EsgTransformIn["method"] })}>
                  <option value="percentile">Percentile rank</option>
                  <option value="linear">Fixed linear scale</option>
                </Select>
              </Field>
              {transform.method === "linear" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Value scored 0" htmlFor="lo">
                    <NumberInput id="lo" value={transform.lower ?? null} onChange={(v) => setTransform({ ...transform, lower: v })} allowEmpty placeholder={metric?.range ?? "min"} />
                  </Field>
                  <Field label="Value scored 100" htmlFor="hi">
                    <NumberInput id="hi" value={transform.upper ?? null} onChange={(v) => setTransform({ ...transform, upper: v })} allowEmpty placeholder={metric?.range ?? "max"} />
                  </Field>
                </div>
              )}
              <Field label="Latest year up to (optional)" htmlFor="year" hint="Use each company's most recent answer up to this year.">
                <NumberInput id="year" value={year} onChange={(v) => setYear(v == null ? null : Math.round(v))} allowEmpty placeholder="Latest" min={1990} max={2100} />
              </Field>
              <Button variant="primary" onClick={() => runPreview()} busy={busy === "preview"} disabled={!metric || !!unsupported || u.tickers.length === 0}>
                {metric ? `Preview scores for ${u.tickers.length} assets` : "Choose a metric first"}
              </Button>
              <Button
                variant="secondary"
                onClick={addComponent}
                disabled={!metric || components.some((c) => c.metric.id === metric?.id) || components.length >= MAX_COMPONENTS}
              >
                Add to composite
              </Button>
            </div>
          </Card>

          {components.length > 0 && (
            <Card title="Composite score" subtitle="A weighted average of several metrics' 0–100 scores. An asset needs a score for every metric.">
              <ul className="space-y-2">
                {components.map((c, i) => (
                  <li key={c.metric.id} className="rounded-md border border-line p-2 text-xs">
                    <span className="block font-medium text-ink">{c.metric.title}</span>
                    <span className="block text-muted">
                      {describe(c.transform)}
                      {c.year ? `, up to ${c.year}` : ""}
                    </span>
                    <span className="mt-1.5 flex items-end gap-2">
                      <Field label="Weight" htmlFor={`w-${c.metric.id}`} className="w-24">
                        <NumberInput
                          id={`w-${c.metric.id}`}
                          value={c.weight}
                          min={0.01}
                          max={100}
                          onChange={(v) => setComponents(components.map((x, j) => (j === i ? { ...x, weight: v ?? x.weight } : x)))}
                        />
                      </Field>
                      <Button size="sm" variant="ghost" onClick={() => setComponents(components.filter((_, j) => j !== i))}>
                        Remove
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
              <Button className="mt-3" variant="primary" onClick={() => runComposite()} busy={busy === "composite"} disabled={components.length < 2 || !!unsupported || u.tickers.length === 0}>
                {components.length < 2 ? "Add at least two metrics" : `Preview composite for ${u.tickers.length} assets`}
              </Button>
            </Card>
          )}

          <SavedOverlays
            signedIn={status === "signed_in"}
            items={overlays.data ?? []}
            loading={overlays.isPending && status === "signed_in"}
            activeId={u.esg_overlay_id ?? null}
            datasetId={u.dataset_id}
            onUse={(id) => setUniverse({ esg_overlay_id: id })}
            onDelete={(id) =>
              act("delete", async () => {
                await unwrap(api.DELETE("/api/v1/esg/overlays/{overlay_id}", { params: { path: { overlay_id: id } } }));
                if (u.esg_overlay_id === id) setUniverse({ esg_overlay_id: null });
                await qc.invalidateQueries({ queryKey: ["esg-overlays"] });
              })
            }
          />
        </aside>

        <div className="min-w-0 space-y-4">
          {mode === "composite" && composite ? (
            <CompositeView data={composite} onPick={pickCompany} />
          ) : !preview ? (
            <EmptyState title="No preview yet">
              Pick a metric, choose how values become 0–100 scores, and preview them for the selected assets. Assets are matched automatically by ISIN; others can be matched by hand.
            </EmptyState>
          ) : (
            <>
              {preview.warnings.length > 0 && (
                <Callout tone="warning" title="No scores yet">
                  {preview.warnings.join(" ")}
                </Callout>
              )}
              <Card
                title={preview.metric.title}
                subtitle={`${preview.metric.designer} · ${preview.scored} of ${preview.entries.length} assets scored`}
                bodyClassName="p-0"
              >
                <Table>
                  <thead>
                    <tr>
                      <Th>Asset</Th>
                      <Th>WikiRate company</Th>
                      <Th align="right">Year</Th>
                      <Th align="right">Value</Th>
                      <Th align="right">Score</Th>
                      <Th>Status</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.entries.map((e) => (
                      <tr key={e.ticker}>
                        <Td>
                          <span className="font-medium">{e.ticker}</span>
                          <span className="block text-[11px] text-muted">{e.isin ?? "no ISIN"}</span>
                        </Td>
                        <Td>
                          {e.company ? (
                            <>
                              {e.company}
                              <span className="block text-[11px] text-muted">{e.matched_by === "isin" ? "matched by ISIN" : "chosen by you"}</span>
                            </>
                          ) : (
                            <CompanyPicker ticker={e.ticker} initial={e.asset_name} onPick={(c) => pickCompany(e.ticker, c)} />
                          )}
                        </Td>
                        <Td align="right">{e.year ?? "n/a"}</Td>
                        <Td align="right">
                          {e.raw_value != null ? num(e.raw_value, 2) : "n/a"}
                          {e.answer_url && (
                            <a href={e.answer_url} target="_blank" rel="noreferrer" className="ml-1 text-accent-ink underline underline-offset-2">
                              source
                            </a>
                          )}
                        </Td>
                        <Td align="right" className="font-medium">
                          {e.score != null ? e.score.toFixed(0) : "n/a"}
                        </Td>
                        <Td>
                          <Badge tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Badge>
                          <span className="block text-[11px] text-muted">{e.note}</span>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <p className="px-4 py-2 text-[11px] text-muted">{preview.attribution}</p>
              </Card>
            </>
          )}
          {activeScored !== null && (
            <Card title="3. Save and use">
            {status !== "signed_in" ? (
              <p className="text-sm text-ink-2">
                <Link href="/login?next=/app/esg-data" className="text-accent-ink underline underline-offset-2">
                  Sign in
                </Link>{" "}
                to save these scores and use them in optimisation, ESG constraints and backtests.
              </p>
            ) : (
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Name" htmlFor="ov-name" className="min-w-64 flex-1">
                  <Input id="ov-name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
                </Field>
                <Button variant="primary" onClick={save} busy={busy === "save"} disabled={activeScored === 0}>
                  Save and use in workspace
                </Button>
              </div>
            )}
            {saved && (
              <p className="mt-2 text-sm text-ink-2" role="status">
                {saved}
              </p>
            )}
            <p className="mt-2 text-xs text-muted">
              When used, these scores replace the dataset&apos;s own ESG scores for the selected assets. Unscored assets are never given a value: exclude them explicitly in ESG constraints.
            </p>
          </Card>
          )}
        </div>
      </div>
    </>
  );
}

function CompanyPicker({ ticker, initial, onPick }: { ticker: string; initial: string; onPick: (c: OpenCompanyOut) => void }) {
  const [q, setQ] = useState(initial === ticker ? "" : initial);
  const [results, setResults] = useState<OpenCompanyOut[] | null>(null);
  const [busy, setBusy] = useState(false);
  const find = async () => {
    setBusy(true);
    try {
      setResults(await unwrap(api.GET("/api/v1/esg/open/companies", { params: { query: { q, limit: 8 } } })));
    } catch {
      setResults([]);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        <Input aria-label={`Find company for ${ticker}`} className="h-7 text-xs" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Company name" />
        <Button size="sm" variant="secondary" onClick={find} busy={busy} disabled={q.trim().length < 2}>
          Find
        </Button>
      </div>
      {results && (
        <ul className="space-y-0.5">
          {results.length === 0 && <li className="text-[11px] text-muted">No companies found.</li>}
          {results.map((c) => (
            <li key={c.id}>
              <button type="button" className="text-left text-[11px] text-accent-ink underline underline-offset-2" onClick={() => onPick(c)}>
                {c.name}
                {c.headquarters ? ` (${c.headquarters})` : ""}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SavedOverlays({
  signedIn,
  loading,
  items,
  activeId,
  datasetId,
  onUse,
  onDelete,
}: {
  signedIn: boolean;
  loading: boolean;
  items: { id: string; name: string; dataset_id: string; metric_title: string; scored: number; total: number }[];
  activeId: string | null;
  datasetId: string;
  onUse: (id: string | null) => void;
  onDelete: (id: string) => void;
}) {
  if (!signedIn) return null;
  if (loading) {
    return (
      <Card title="Saved ESG overlays">
        <SkeletonRows rows={3} label="Loading saved overlays" />
      </Card>
    );
  }
  return (
    <Card title="Saved ESG overlays">
      {items.length === 0 ? (
        <p className="text-xs text-muted">None yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((o) => (
            <li key={o.id} className="rounded-md border border-line p-2 text-xs">
              <span className="flex items-center justify-between gap-2">
                <span className="font-medium text-ink">{o.name}</span>
                {o.id === activeId && <Badge tone="accent">In use</Badge>}
              </span>
              <span className="block text-muted">
                {o.metric_title} · {o.scored}/{o.total} scored
              </span>
              <span className="mt-1.5 flex gap-1.5">
                {o.id === activeId ? (
                  <Button size="sm" variant="secondary" onClick={() => onUse(null)}>
                    Stop using
                  </Button>
                ) : (
                  <Button size="sm" variant="secondary" disabled={o.dataset_id !== datasetId} onClick={() => onUse(o.id)} title={o.dataset_id !== datasetId ? "Built for another dataset" : undefined}>
                    Use
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => onDelete(o.id)}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CompositeView({ data, onPick }: { data: CompositePreviewOut; onPick: (ticker: string, c: OpenCompanyOut) => void }) {
  return (
    <>
      {data.warnings.length > 0 && (
        <Callout tone="warning" title="Some metrics could not be scored">
          {data.warnings.join(" ")}
        </Callout>
      )}
      <Card
        title="Composite ESG score"
        subtitle={`${data.components.map((c) => `${c.metric.title} ${(c.weight * 100).toFixed(0)}%`).join(", ")} · ${data.scored} of ${data.entries.length} assets scored`}
        bodyClassName="p-0"
      >
        <Table>
          <thead>
            <tr>
              <Th>Asset</Th>
              <Th>WikiRate company</Th>
              {data.components.map((c) => (
                <Th key={c.metric.id} align="right">
                  <span className="block max-w-40 truncate" title={c.metric.title}>
                    {c.metric.title}
                  </span>
                  <span className="block text-[11px] font-normal text-muted">weight {(c.weight * 100).toFixed(0)}%</span>
                </Th>
              ))}
              <Th align="right">Composite</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((e) => (
              <tr key={e.ticker}>
                <Td>
                  <span className="font-medium">{e.ticker}</span>
                  <span className="block text-[11px] text-muted">{e.isin ?? "no ISIN"}</span>
                </Td>
                <Td>
                  {e.company ? (
                    <>
                      {e.company}
                      <span className="block text-[11px] text-muted">{e.matched_by === "isin" ? "matched by ISIN" : "chosen by you"}</span>
                    </>
                  ) : (
                    <CompanyPicker ticker={e.ticker} initial={e.asset_name} onPick={(c) => onPick(e.ticker, c)} />
                  )}
                </Td>
                {data.components.map((c) => {
                  const part = e.parts?.find((p) => p.metric_id === c.metric.id);
                  return (
                    <Td key={c.metric.id} align="right">
                      {part?.score != null ? part.score.toFixed(0) : "n/a"}
                      {part?.year != null && <span className="block text-[11px] text-muted">{part.year}</span>}
                      {part?.answer_url && (
                        <a href={part.answer_url} target="_blank" rel="noreferrer" className="text-[11px] text-accent-ink underline underline-offset-2">
                          source
                        </a>
                      )}
                    </Td>
                  );
                })}
                <Td align="right" className="font-medium">
                  {e.score != null ? e.score.toFixed(0) : "n/a"}
                </Td>
                <Td>
                  <Badge tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Badge>
                  <span className="block text-[11px] text-muted">{e.note}</span>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
        <p className="px-4 py-2 text-[11px] text-muted">{data.attribution}</p>
      </Card>
    </>
  );
}
