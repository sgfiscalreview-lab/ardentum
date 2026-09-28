"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { BlackLittermanEditor, DEFAULT_BLACK_LITTERMAN } from "@/components/black-litterman";
import { Badge, Button, Callout, Card, Field, Input, NumberInput, Select, Skeleton, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { ErrorCallout, PageHeader, SyntheticBanner, useDataset } from "@/components/workspace";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { AssetOut, EstimationSettings, RiskFreeOut, UniverseSelection } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { date as fmtDate, ESTIMATOR_LABELS, pct } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

/** Currencies with ECB reference rates (conversion source: Frankfurter). */
const ECB_CURRENCIES = [
  "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK", "HKD", "SGD", "CNY",
  "INR", "KRW", "BRL", "MXN", "ZAR", "PLN", "CZK", "HUF", "RON", "BGN", "ISK", "ILS", "TRY", "IDR",
  "MYR", "PHP", "THB",
];

export default function UniversePage() {
  const { state, setUniverse, setEstimation } = useWorkspace();
  const u = state.universe;
  const datasets = useQuery({ queryKey: ["datasets", "list"], queryFn: () => unwrap(api.GET("/api/v1/datasets")) });
  const ds = useDataset(u.dataset_id);
  const [filter, setFilter] = useState("");
  const [sector, setSector] = useState("");

  const assets = useMemo(() => ds.data?.assets ?? [], [ds.data]);
  const visible = assets.filter(
    (a) =>
      (!sector || a.sector === sector) &&
      (!filter || `${a.ticker} ${a.name}`.toLowerCase().includes(filter.toLowerCase())),
  );
  const selected = new Set(u.tickers);
  const toggle = (t: string) =>
    setUniverse({ tickers: selected.has(t) ? u.tickers.filter((x) => x !== t) : [...u.tickers, t] });

  return (
    <>
      <PageHeader
        title="Universe"
        description="Choose the data, the assets and the historical window used to estimate expected returns and risk. Every later step uses these settings."
        actions={
          <Link href="/app/analytics" className="inline-flex h-9 items-center rounded-md bg-accent px-4 text-sm font-medium text-on-accent hover:bg-accent-hover">
            Continue to analytics
          </Link>
        }
      />
      <SyntheticBanner dataset={ds.data} />
      <ErrorCallout error={datasets.error ?? ds.error} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <Card title="Dataset" subtitle="Where prices (and sector/ESG metadata) come from.">
            <div className="grid gap-2 sm:grid-cols-2">
              {datasets.isPending &&
                Array.from({ length: 4 }, (_, i) => (
                  <div key={i} role="status" aria-label="Loading datasets" className="rounded-sm border border-line p-3">
                    <Skeleton className="h-4 w-2/3" />
                    <Skeleton className="mt-2 h-3 w-full" />
                    <Skeleton className="mt-1.5 h-3 w-1/2" />
                  </div>
                ))}
              {datasets.data?.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() =>
                    setUniverse(
                      d.id === u.dataset_id ? { dataset_id: d.id } : { dataset_id: d.id, tickers: [], esg_overlay_id: null },
                    )
                  }
                  aria-pressed={d.id === u.dataset_id}
                  className={`rounded-md border p-3 text-left ${d.id === u.dataset_id ? "border-accent bg-accent-wash" : "border-line hover:bg-surface-2"}`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">{d.name}</span>
                    {d.is_synthetic ? <Badge tone="synthetic">Synthetic</Badge> : d.kind === "provider" ? <Badge tone="accent">Live</Badge> : <Badge>Uploaded</Badge>}
                  </span>
                  <span className="mt-1 line-clamp-2 block text-xs text-ink-2">{d.description}</span>
                  {d.start && (
                    <span className="mt-1 block text-[11px] text-muted">
                      {d.n_assets} assets · {fmtDate(d.start)} – {fmtDate(d.end)}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </Card>

          {ds.data?.kind === "provider" ? (
            <TickerEntry tickers={u.tickers} onChange={(t) => setUniverse({ tickers: t })} />
          ) : (
            <Card
              title={`Assets (${u.tickers.length} selected)`}
              subtitle="Select between 2 and 60 assets. ESG scores show their source; unscored assets can be excluded when ESG constraints are used."
              actions={
                <>
                  <Button size="sm" variant="ghost" onClick={() => setUniverse({ tickers: Array.from(new Set([...u.tickers, ...visible.map((a) => a.ticker)])) })}>
                    Select shown
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setUniverse({ tickers: u.tickers.filter((t) => !visible.some((a) => a.ticker === t)) })}>
                    Clear shown
                  </Button>
                </>
              }
            >
              <div className="mb-3 flex flex-wrap gap-2">
                <Input placeholder="Search ticker or name" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-60" aria-label="Search assets" />
                <Select value={sector} onChange={(e) => setSector(e.target.value)} className="max-w-60" aria-label="Filter by sector">
                  <option value="">All sectors</option>
                  {ds.data?.sectors.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </Select>
              </div>
              {ds.isPending ? <SkeletonRows rows={8} label="Loading assets" /> : <AssetTable assets={visible} selected={selected} onToggle={toggle} />}
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Estimation window">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start" htmlFor="start">
                <Input id="start" type="date" value={u.start ?? ""} min={ds.data?.start ?? undefined} max={u.end ?? undefined} onChange={(e) => setUniverse({ start: e.target.value || null })} />
              </Field>
              <Field label="End" htmlFor="end">
                <Input id="end" type="date" value={u.end ?? ""} min={u.start ?? undefined} max={ds.data?.end ?? undefined} onChange={(e) => setUniverse({ end: e.target.value || null })} />
              </Field>
              <Field label="Return frequency" htmlFor="freq" className="col-span-2" hint="Daily data gives more observations; monthly reduces noise from asynchronous prices.">
                <Select id="freq" value={u.frequency} onChange={(e) => setUniverse({ frequency: e.target.value as "daily" | "weekly" | "monthly" })}>
                  <option value="daily">Daily (252 per year)</option>
                  <option value="weekly">Weekly (52 per year)</option>
                  <option value="monthly">Monthly (12 per year)</option>
                </Select>
              </Field>
            </div>
          </Card>
          <CurrencyCard universe={u} assets={assets} onChange={setUniverse} />
          <EstimationCard value={state.estimation} universe={u} capsAvailable={ds.data?.has_market_caps ?? false} onChange={setEstimation} />
          <UploadCard />
        </div>
      </div>
    </>
  );
}

function AssetTable({ assets, selected, onToggle }: { assets: AssetOut[]; selected: Set<string>; onToggle: (t: string) => void }) {
  return (
    <Table className="max-h-[32rem] overflow-y-auto">
      <thead>
        <tr>
          <Th>
            <span className="sr-only">Selected</span>
          </Th>
          <Th>Ticker</Th>
          <Th>Name</Th>
          <Th>Sector</Th>
          <Th>Class</Th>
          <Th>Ccy</Th>
          <Th align="right">ESG</Th>
        </tr>
      </thead>
      <tbody>
        {assets.map((a) => (
          <tr key={a.ticker} className="hover:bg-surface-2/60">
            <Td>
              <input type="checkbox" className="size-4 accent-[var(--accent)]" checked={selected.has(a.ticker)} onChange={() => onToggle(a.ticker)} aria-label={`Select ${a.ticker}`} />
            </Td>
            <Td className="font-medium whitespace-nowrap">
              {a.ticker}
              {a.is_benchmark && (
                <span className="ml-1.5">
                  <Badge>Index</Badge>
                </span>
              )}
            </Td>
            <Td className="text-ink-2">{a.name}</Td>
            <Td className="text-ink-2 whitespace-nowrap">{a.sector ?? "n/a"}</Td>
            <Td className="text-ink-2">{a.asset_class.replace("_", " ")}</Td>
            <Td className="text-ink-2">{a.currency}</Td>
            <Td align="right" title={a.esg_source ?? "No ESG score available"}>
              {a.esg_score != null ? a.esg_score.toFixed(0) : <span className="text-muted">n/a</span>}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function TickerEntry({ tickers, onChange }: { tickers: string[]; onChange: (t: string[]) => void }) {
  const [text, setText] = useState(tickers.join(", "));
  return (
    <Card title="Tickers" subtitle="Live data: enter US tickers separated by commas. Sector and ESG data are not provided by this source.">
      <div className="flex gap-2">
        <Input value={text} onChange={(e) => setText(e.target.value)} aria-label="Tickers" placeholder="e.g. SPY, TLT, GLD" />
        <Button onClick={() => onChange(Array.from(new Set(text.split(/[\s,]+/).map((t) => t.trim().toUpperCase()).filter(Boolean))))}>Apply</Button>
      </div>
    </Card>
  );
}

function CurrencyCard({ universe, assets, onChange }: { universe: UniverseSelection; assets: AssetOut[]; onChange: (v: Partial<UniverseSelection>) => void }) {
  const chosen = new Set(universe.tickers);
  const currencies = Array.from(new Set(assets.filter((a) => chosen.has(a.ticker)).map((a) => a.currency))).sort();
  const mixed = currencies.length > 1;
  return (
    <Card title="Currency" subtitle="Currency in which returns, risk and values are expressed.">
      <Field
        label="Base currency"
        htmlFor="ccy"
        hint="Prices in other currencies are converted at daily ECB reference rates (via Frankfurter)."
      >
        <Select
          id="ccy"
          value={universe.base_currency ?? ""}
          onChange={(e) => onChange(e.target.value ? { base_currency: e.target.value } : { base_currency: null, currency_hedged: false })}
        >
          <option value="">{mixed ? "Choose a currency…" : `As quoted${currencies[0] ? ` (${currencies[0]})` : ""}`}</option>
          {ECB_CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </Field>
      {mixed && !universe.base_currency && (
        <p className="mt-2 text-xs text-warn" role="status">
          The selected assets are priced in {currencies.join(", ")}; choose a base currency to compare them.
        </p>
      )}
      {universe.base_currency && (
        <Field
          className="mt-3"
          label="Currency risk"
          htmlFor="hedge"
          hint={
            universe.currency_hedged
              ? "Each period the foreign position is sold forward at a rate set by the two currencies' central-bank policy rates (BIS). You keep the local return plus or minus the rate difference; only each period's gain stays exposed to the exchange rate."
              : "Returns include exchange-rate moves, as for an investor who converts and does not hedge."
          }
        >
          <Select id="hedge" value={universe.currency_hedged ? "hedged" : "unhedged"} onChange={(e) => onChange({ currency_hedged: e.target.value === "hedged" })}>
            <option value="unhedged">Unhedged</option>
            <option value="hedged">Hedged to {universe.base_currency}</option>
          </Select>
        </Field>
      )}
    </Card>
  );
}

function RiskFreeFetch({ universe, onChange }: { universe: UniverseSelection; onChange: (v: Partial<EstimationSettings>) => void }) {
  const sources = useQuery({ queryKey: ["risk-free", "sources"], queryFn: () => unwrap(api.GET("/api/v1/risk-free/sources")), staleTime: 3_600_000 });
  const [source, setSource] = useState<"kenfrench_rf" | "fred_dgs3mo">("kenfrench_rf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [last, setLast] = useState<RiskFreeOut | null>(null);
  const fetchRate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await unwrap(api.POST("/api/v1/risk-free", { body: { source, start: universe.start ?? null, end: universe.end ?? null } }));
      setLast(res);
      onChange({ risk_free_rate: res.rate, risk_free_source: res.label });
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2 rounded-md border border-line p-2.5">
      <div className="flex gap-2">
        <Select aria-label="Risk-free source" value={source} onChange={(e) => setSource(e.target.value as typeof source)} className="h-8 text-xs">
          {(sources.data ?? []).map((s) => (
            <option key={s.id} value={s.id} disabled={!s.available}>
              {s.name}
              {s.available ? "" : " (not configured)"}
            </option>
          ))}
        </Select>
        <Button size="sm" variant="secondary" onClick={fetchRate} disabled={busy}>
          {busy ? "Fetching…" : "Use"}
        </Button>
      </div>
      <p className="text-[11px] text-muted">
        Average over the estimation window (last 5 years if none is set), as an effective annual rate.
        {last && ` Retrieved ${fmtDate(last.retrieved_at.slice(0, 10))}${last.stale ? " (cached copy; source unreachable)" : ""}. Source: ${last.source.citation}`}
      </p>
      <ErrorCallout error={error} />
    </div>
  );
}

function EstimationCard({
  value,
  universe,
  capsAvailable,
  onChange,
}: {
  value: EstimationSettings;
  universe: UniverseSelection;
  capsAvailable: boolean;
  onChange: (v: Partial<EstimationSettings>) => void;
}) {
  return (
    <Card title="Estimation" subtitle="How expected returns and risk are estimated from the window.">
      <div className="space-y-3">
        <Field label="Expected returns" htmlFor="mean" hint="Bayes–Stein shrinks noisy sample means toward a common value (Jorion 1986). Black–Litterman starts from market-implied returns and adds your views.">
          <Select
            id="mean"
            value={value.mean_estimator}
            onChange={(e) => {
              const m = e.target.value as EstimationSettings["mean_estimator"];
              onChange(m === "black_litterman" && !value.black_litterman ? { mean_estimator: m, black_litterman: DEFAULT_BLACK_LITTERMAN } : { mean_estimator: m });
            }}
          >
            {(["historical", "bayes_stein", "black_litterman"] as const).map((k) => (
              <option key={k} value={k}>
                {ESTIMATOR_LABELS[k]}
              </option>
            ))}
          </Select>
        </Field>
        {value.mean_estimator === "black_litterman" && (
          <BlackLittermanEditor value={value.black_litterman} tickers={universe.tickers} capsAvailable={capsAvailable} onChange={(bl) => onChange({ black_litterman: bl })} />
        )}
        <Field label="Covariance" htmlFor="cov" hint="Ledoit–Wolf shrinkage reduces estimation error and keeps the matrix well-conditioned.">
          <Select id="cov" value={value.covariance_estimator} onChange={(e) => onChange({ covariance_estimator: e.target.value as EstimationSettings["covariance_estimator"] })}>
            {(["ledoit_wolf", "ledoit_wolf_constant_correlation", "sample"] as const).map((k) => (
              <option key={k} value={k}>
                {ESTIMATOR_LABELS[k]}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Risk-free rate (annual)"
          htmlFor="rf"
          hint={value.risk_free_source ? `${pct(value.risk_free_rate ?? 0)} from ${value.risk_free_source}.` : "Used for Sharpe and Sortino ratios. Enter an assumption or fetch a historical average."}
        >
          <NumberInput id="rf" value={value.risk_free_rate} onChange={(v) => onChange({ risk_free_rate: v ?? 0, risk_free_source: null })} scale={100} suffix="%" min={-5} max={25} />
        </Field>
        <RiskFreeFetch universe={universe} onChange={onChange} />
      </div>
    </Card>
  );
}

function UploadCard() {
  const { status } = useAuth();
  const qc = useQueryClient();
  const { setUniverse } = useWorkspace();
  const [name, setName] = useState("");
  const [prices, setPrices] = useState<File | null>(null);
  const [meta, setMeta] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  if (status !== "signed_in") {
    return (
      <Card title="Your own data">
        <p className="text-sm text-ink-2">
          <Link href="/login?next=/app" className="text-accent-ink underline underline-offset-2">
            Sign in
          </Link>{" "}
          to upload price histories (CSV) with optional sector and ESG metadata.
        </p>
      </Card>
    );
  }
  const submit = async () => {
    if (!prices || !name.trim()) return;
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const form = new FormData();
      form.append("name", name.trim());
      form.append("prices", prices);
      if (meta) form.append("metadata", meta);
      const res = await unwrap(
        api.POST("/api/v1/datasets", {
          // openapi-fetch passes FormData through untouched.
          body: form as unknown as { name: string; prices: string },
          bodySerializer: (b) => b as unknown as FormData,
        }),
      );
      await qc.invalidateQueries({ queryKey: ["datasets"] });
      setOk(`Uploaded “${res.name}” with ${res.assets.length} assets.`);
      setUniverse({ dataset_id: res.id, tickers: res.assets.slice(0, 60).map((a) => a.ticker), start: null, end: null, esg_overlay_id: null });
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Upload your own data" subtitle="CSV of adjusted closes: a date column (YYYY-MM-DD) and one column per ticker, or long format date,ticker,adj_close.">
      <div className="space-y-3">
        <Field label="Dataset name" htmlFor="ds-name">
          <Input id="ds-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </Field>
        <Field label="Prices CSV" htmlFor="ds-prices">
          <input id="ds-prices" type="file" accept=".csv,text/csv" onChange={(e) => setPrices(e.target.files?.[0] ?? null)} className="text-xs text-ink-2" />
        </Field>
        <Field label="Metadata CSV (optional)" htmlFor="ds-meta" hint="Columns: ticker, name, sector, asset_class, currency (ISO code, default USD), isin, market_cap, esg_score, esg_source, esg_as_of. ESG scores require a source.">
          <input id="ds-meta" type="file" accept=".csv,text/csv" onChange={(e) => setMeta(e.target.files?.[0] ?? null)} className="text-xs text-ink-2" />
        </Field>
        {error && <Callout tone="error" title="Upload rejected">{error.message}</Callout>}
        {ok && <Callout tone="success">{ok}</Callout>}
        <p className="text-[11px] text-muted">By uploading you confirm you have the right to use this data. It is visible only to you.</p>
        <Button variant="primary" onClick={() => void submit()} busy={busy} disabled={!prices || !name.trim()}>
          Upload
        </Button>
      </div>
    </Card>
  );
}
