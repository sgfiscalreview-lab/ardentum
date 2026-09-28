"use client";

import { useId, useMemo, useState, type ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { cx, Table, Tabs, Td, Th } from "./ui";

/** Categorical slots in fixed, validated order. Never cycle past eight. */
export const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
] as const;

export function seriesColor(i: number): string {
  return SERIES[Math.min(i, SERIES.length - 1)] ?? SERIES[0];
}

const AXIS = { stroke: "var(--axis)" };
const TICK = { fill: "var(--muted)", fontSize: 11 };

// --------------------------------------------------------------------------- frame & legend

export interface LegendItem {
  label: string;
  color: string;
  kind?: "line" | "rect" | "dot" | "band";
}

export function Legend({ items }: { items: LegendItem[] }) {
  if (items.length < 2) return null;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5">
          <LegendKey color={it.color} kind={it.kind ?? "line"} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

function LegendKey({ color, kind }: { color: string; kind: NonNullable<LegendItem["kind"]> }) {
  if (kind === "rect") return <span className="inline-block size-2.5 rounded-sm" style={{ background: color }} />;
  if (kind === "dot") return <span className="inline-block size-2 rounded-full" style={{ background: color }} />;
  if (kind === "band")
    return <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color, opacity: 0.35 }} />;
  return <span className="inline-block h-0.5 w-4 rounded" style={{ background: color }} />;
}

/** Chart container with title, legend and a chart/table toggle (the accessible twin). */
export function ChartFrame({
  title,
  subtitle,
  legend,
  table,
  children,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  legend?: LegendItem[];
  table?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cx("rounded-lg border border-line bg-surface", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3">
        <div className="min-w-0">
          <h3 id={headingId} className="text-sm font-semibold text-ink">
            {title}
          </h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {table && (
            <Tabs
              label="View"
              value={view}
              onChange={setView}
              items={[
                { value: "chart", label: "Chart" },
                { value: "table", label: "Table" },
              ]}
            />
          )}
        </div>
      </header>
      {legend && view === "chart" && (
        <div className="px-4 pt-2">
          <Legend items={legend} />
        </div>
      )}
      <div className="px-2 pb-3 pt-2">
        {view === "chart" || !table ? children : <div className="max-h-96 overflow-auto px-2">{table}</div>}
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------- tooltip

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

function TooltipBox({ title, rows }: { title?: string; rows: TooltipRow[] }) {
  return (
    <div className="min-w-40 rounded-sm border border-line-strong bg-surface px-3 py-2 text-xs">
      {title && <p className="mb-1 font-medium text-ink-2">{title}</p>}
      <ul className="space-y-0.5">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-ink-2">
              {r.color && <span className="inline-block h-0.5 w-3 rounded" style={{ background: r.color }} />}
              {r.label}
            </span>
            <span className="font-semibold text-ink tabular">{r.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------- time series

export interface Series {
  key: string;
  name: string;
  values: number[];
  color?: string;
}

function yearTick(d: string): string {
  return d.slice(0, 4);
}

export function TimeSeriesChart({
  dates,
  series,
  yFormat,
  height = 280,
  area = false,
  baseline,
  xFormat = yearTick,
}: {
  dates: string[];
  series: Series[];
  yFormat: (v: number) => string;
  height?: number;
  area?: boolean;
  baseline?: number;
  xFormat?: (d: string) => string;
}) {
  const data = useMemo(
    () =>
      dates.map((d, i) => {
        const row: Record<string, number | string> = { date: d };
        for (const s of series) {
          const v = s.values[i];
          if (v !== undefined) row[s.key] = v;
        }
        return row;
      }),
    [dates, series],
  );
  const Chart = area ? ComposedChart : LineChart;
  // One tick per calendar year (first date in each year) for multi-year series.
  const yearTicks = useMemo(() => {
    if (xFormat !== yearTick || dates.length < 2) return undefined;
    const seen = new Set<string>();
    const out: string[] = [];
    for (const d of dates) {
      const y = d.slice(0, 4);
      if (!seen.has(y)) {
        seen.add(y);
        out.push(d);
      }
    }
    return out.length >= 3 ? out.slice(1) : undefined;
  }, [dates, xFormat]);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="date" ticks={yearTicks} tickFormatter={xFormat} minTickGap={32} axisLine={AXIS} tickLine={false} tick={TICK} />
        <YAxis tickFormatter={yFormat} width={60} axisLine={false} tickLine={false} tick={TICK} domain={["auto", "auto"]} />
        {baseline !== undefined && (
          <Line dataKey={() => baseline} stroke="var(--axis)" strokeWidth={1} dot={false} isAnimationActive={false} activeDot={false} legendType="none" />
        )}
        <Tooltip
          isAnimationActive={false}
          cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={String(label)}
                rows={series.map((s, i) => {
                  const p = payload.find((x) => x.dataKey === s.key);
                  return {
                    label: s.name,
                    value: p && typeof p.value === "number" ? yFormat(p.value) : "n/a",
                    color: s.color ?? seriesColor(i),
                  };
                })}
              />
            ) : null
          }
        />
        {series.map((s, i) =>
          area ? (
            <Area
              key={s.key}
              dataKey={s.key}
              name={s.name}
              type="linear"
              stroke={s.color ?? seriesColor(i)}
              fill={s.color ?? seriesColor(i)}
              fillOpacity={0.1}
              strokeWidth={2}
              isAnimationActive={false}
              dot={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
            />
          ) : (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.name}
              type="linear"
              stroke={s.color ?? seriesColor(i)}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
            />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------- fan chart

export function FanChart({
  times,
  percentiles,
  format,
  height = 320,
  target,
}: {
  times: number[];
  percentiles: Record<string, number[]>;
  format: (v: number) => string;
  height?: number;
  target?: number | null;
}) {
  const data = useMemo(
    () =>
      times.map((t, i) => {
        const g = (k: string) => percentiles[k]?.[i] ?? Number.NaN;
        return {
          t,
          outer: [g("p05"), g("p95")] as [number, number],
          inner: [g("p25"), g("p75")] as [number, number],
          p50: g("p50"),
          p05: g("p05"),
          p25: g("p25"),
          p75: g("p75"),
          p95: g("p95"),
        };
      }),
    [times, percentiles],
  );
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="t"
          type="number"
          domain={[0, "dataMax"]}
          tickFormatter={(v: number) => `${v.toFixed(0)}y`}
          axisLine={AXIS}
          tickLine={false}
          tick={TICK}
          allowDecimals={false}
        />
        <YAxis tickFormatter={format} width={68} axisLine={false} tickLine={false} tick={TICK} />
        <Tooltip
          isAnimationActive={false}
          cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
          content={({ active, payload }) => {
            const row = payload?.[0]?.payload as (typeof data)[number] | undefined;
            if (!active || !row) return null;
            return (
              <TooltipBox
                title={`Year ${row.t.toFixed(2)}`}
                rows={[
                  { label: "95th percentile", value: format(row.p95) },
                  { label: "75th percentile", value: format(row.p75) },
                  { label: "Median", value: format(row.p50), color: "var(--series-1)" },
                  { label: "25th percentile", value: format(row.p25) },
                  { label: "5th percentile", value: format(row.p05) },
                ]}
              />
            );
          }}
        />
        <Area dataKey="outer" stroke="none" fill="var(--series-1)" fillOpacity={0.1} isAnimationActive={false} activeDot={false} />
        <Area dataKey="inner" stroke="none" fill="var(--series-1)" fillOpacity={0.22} isAnimationActive={false} activeDot={false} />
        <Line dataKey="p50" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} />
        {target ? (
          <Line dataKey={() => target} stroke="var(--ink-2)" strokeWidth={1} dot={false} isAnimationActive={false} activeDot={false} />
        ) : null}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------- frontier

/** Round axis bounds and ticks at 1/2/5 x 10^k steps. */
export function niceAxis(lo: number, hi: number, target = 6): { min: number; max: number; ticks: number[] } {
  const span = hi - lo || Math.abs(hi) || 1;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  const min = Math.floor(lo / step) * step;
  const max = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let v = min; v <= max + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return { min, max, ticks };
}

export interface FrontierSeries {
  name: string;
  points: { x: number; y: number }[];
  color: string;
}

export interface MarkerPoint {
  name: string;
  x: number;
  y: number;
  color: string;
  shape: "circle" | "diamond" | "square";
  size?: number;
  detail?: string;
}

function Marker(props: { cx?: number; cy?: number; fill?: string; payload?: MarkerPoint }) {
  const { cx: x = 0, cy: y = 0, payload } = props;
  const color = payload?.color ?? props.fill ?? "var(--series-1)";
  const s = payload?.size ?? 5;
  // Transparent 24px hit area around every marker (the mark itself stays small).
  const hit = <circle cx={x} cy={y} r={12} fill="transparent" />;
  if (payload?.shape === "diamond")
    return (
      <g>
        {hit}
        <path d={`M${x} ${y - s - 2} L${x + s + 2} ${y} L${x} ${y + s + 2} L${x - s - 2} ${y} Z`} fill={color} stroke="var(--surface)" strokeWidth={2} />
      </g>
    );
  if (payload?.shape === "square")
    return (
      <g>
        {hit}
        <rect x={x - s} y={y - s} width={2 * s} height={2 * s} rx={1.5} fill={color} stroke="var(--surface)" strokeWidth={2} />
      </g>
    );
  return (
    <g>
      {hit}
      <circle cx={x} cy={y} r={s - 1} fill={color} stroke="var(--surface)" strokeWidth={2} />
    </g>
  );
}

/** Risk measure on the x axis: annualised volatility by default, or e.g. one-period CVaR. */
export interface RiskAxis {
  name: string;
  label: string;
}

const VOLATILITY_AXIS: RiskAxis = { name: "Volatility", label: "Expected volatility (annualised)" };

export function FrontierChart({
  lines,
  markers,
  height = 380,
  xAxis = VOLATILITY_AXIS,
}: {
  lines: FrontierSeries[];
  markers: MarkerPoint[];
  height?: number;
  xAxis?: RiskAxis;
}) {
  const all = [...lines.flatMap((l) => l.points), ...markers];
  const xs = niceAxis(0, Math.max(...all.map((p) => p.x)));
  // Small risk values (e.g. daily CVaR of 1 to 3%) need a decimal on the ticks.
  const xStep = (xs.ticks[1] ?? xs.max) - (xs.ticks[0] ?? xs.min);
  const xDecimals = xStep > 0 && xStep < 0.01 ? 1 : 0;
  const ys = niceAxis(Math.min(0, ...all.map((p) => p.y)), Math.max(...all.map((p) => p.y)));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 24, bottom: 16, left: 4 }}>
        <CartesianGrid />
        <XAxis
          type="number"
          dataKey="x"
          name={xAxis.name}
          domain={[xs.min, xs.max]}
          ticks={xs.ticks}
          tickFormatter={(v: number) => `${(v * 100).toFixed(xDecimals)}%`}
          axisLine={AXIS}
          tickLine={false}
          tick={TICK}
          label={{ value: xAxis.label, position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="Return"
          domain={[ys.min, ys.max]}
          ticks={ys.ticks}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          width={48}
          axisLine={false}
          tickLine={false}
          tick={TICK}
        />
        <ZAxis range={[64, 64]} />
        <Tooltip
          isAnimationActive={false}
          cursor={false}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as (MarkerPoint & { series?: string }) | undefined;
            if (!active || !p) return null;
            return (
              <TooltipBox
                title={p.name ?? p.series}
                rows={[
                  { label: "Expected return", value: `${(p.y * 100).toFixed(2)}%` },
                  { label: xAxis.name, value: `${(p.x * 100).toFixed(2)}%` },
                  ...(p.detail ? [{ label: "Note", value: p.detail }] : []),
                ]}
              />
            );
          }}
        />
        {lines.map((l) => (
          <Scatter
            key={l.name}
            name={l.name}
            data={l.points.map((p) => ({ ...p, name: l.name }))}
            line={{ stroke: l.color, strokeWidth: 2 }}
            lineType="joint"
            shape={() => <g />}
            isAnimationActive={false}
          />
        ))}
        <Scatter name="Markers" data={markers} shape={<Marker />} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------- bar lists (HTML)

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  display: string;
  sub?: ReactNode;
  color?: string;
  muted?: boolean;
}

/** Horizontal bars with the value at the tip; supports negative values (diverging from 0). */
export function BarList({ rows, max, ariaLabel }: { rows: BarRow[]; max?: number; ariaLabel: string }) {
  const hasNeg = rows.some((r) => r.value < 0);
  const m = max ?? Math.max(1e-12, ...rows.map((r) => Math.abs(r.value)));
  return (
    <ul aria-label={ariaLabel} className="space-y-1.5">
      {rows.map((r) => {
        const frac = Math.min(1, Math.abs(r.value) / m);
        const color = r.color ?? (r.value < 0 ? "var(--diverge-neg)" : "var(--series-1)");
        return (
          <li key={r.key} className="grid grid-cols-[minmax(6rem,11rem)_1fr_4.5rem] items-center gap-3 text-sm">
            <div className="min-w-0 truncate text-ink" title={typeof r.label === "string" ? r.label : undefined}>
              {r.label}
              {r.sub && <span className="block truncate text-[11px] text-muted">{r.sub}</span>}
            </div>
            <div className="relative h-4" aria-hidden>
              {hasNeg && <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--axis)]" />}
              <div
                className={cx("absolute inset-y-0.5", r.muted && "opacity-40")}
                style={
                  hasNeg
                    ? r.value >= 0
                      ? { left: "50%", width: `${frac * 50}%`, background: color, borderRadius: "0 1px 1px 0" }
                      : { right: "50%", width: `${frac * 50}%`, background: color, borderRadius: "1px 0 0 1px" }
                    : { left: 0, width: `${frac * 100}%`, background: color, borderRadius: "0 1px 1px 0" }
                }
              />
            </div>
            <span className="text-right text-xs font-medium text-ink tabular">{r.display}</span>
          </li>
        );
      })}
    </ul>
  );
}

// --------------------------------------------------------------------------- heatmap

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const c = a.map((x, i) => Math.round(x + (b[i]! - x) * t));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

/** Diverging colour for a correlation in [-1, 1]: brick (negative), neutral (0), navy (positive). */
export function correlationColor(v: number, dark: boolean): string {
  const mid: [number, number, number] = dark ? [46, 48, 53] : [233, 230, 223];
  const pos: [number, number, number] = dark ? [111, 157, 208] : [47, 95, 147];
  const neg: [number, number, number] = dark ? [207, 111, 95] : [168, 72, 58];
  const t = Math.min(1, Math.abs(v));
  return v >= 0 ? mix(mid, pos, t) : mix(mid, neg, t);
}

export function Heatmap({ labels, matrix, dark }: { labels: string[]; matrix: number[][]; dark: boolean }) {
  const [hover, setHover] = useState<{ i: number; j: number } | null>(null);
  const n = labels.length;
  const hv = hover ? matrix[hover.i]?.[hover.j] : undefined;
  return (
    <div className="overflow-x-auto">
      <p className="mb-2 h-4 text-xs text-ink-2" aria-live="polite">
        {hover && hv !== undefined ? (
          <>
            {labels[hover.i]} × {labels[hover.j]}: <span className="font-semibold text-ink tabular">{hv.toFixed(2)}</span>
          </>
        ) : (
          "Hover a cell for the exact correlation."
        )}
      </p>
      <div
        className="inline-grid gap-[2px]"
        style={{ gridTemplateColumns: `7.5rem repeat(${n}, minmax(1.9rem, 1fr))` }}
        role="grid"
        aria-label="Correlation matrix"
      >
        <div />
        {labels.map((l) => (
          <div key={l} className="flex h-16 items-end justify-center pb-1" aria-hidden>
            <span className="rotate-180 whitespace-nowrap text-[10px] leading-none text-ink-2" style={{ writingMode: "vertical-rl" }}>
              {l.replace(".SYN", "")}
            </span>
          </div>
        ))}
        {labels.map((row, i) => (
          <div key={row} className="contents" role="row">
            <div className="truncate pr-2 text-right text-[11px] leading-7 text-ink-2">{row.replace(".SYN", "")}</div>
            {labels.map((col, j) => {
              const v = matrix[i]?.[j] ?? 0;
              return (
                <button
                  type="button"
                  role="gridcell"
                  key={col}
                  aria-label={`${row} and ${col}: ${v.toFixed(2)}`}
                  onMouseEnter={() => setHover({ i, j })}
                  onFocus={() => setHover({ i, j })}
                  onMouseLeave={() => setHover(null)}
                  className="h-7 rounded-sm outline-offset-0 hover:ring-2 hover:ring-[var(--ink-2)]"
                  style={{ background: correlationColor(v, dark) }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-end gap-px text-[10px] text-ink-2" aria-hidden>
        {[-1, -0.5, 0, 0.5, 1].map((v) => (
          <span key={v} className="flex w-9 flex-col items-center gap-1">
            <span className="block h-2.5 w-full" style={{ background: correlationColor(v, dark) }} />
            <span className="tabular">{v > 0 ? `+${v}` : v === 0 ? "0" : `−${Math.abs(v)}`}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- histogram

export function Histogram({
  edges,
  counts,
  format,
  height = 220,
  marker,
}: {
  edges: number[];
  counts: number[];
  format: (v: number) => string;
  height?: number;
  marker?: number | null;
}) {
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  const data = counts.map((c, i) => ({
    mid: ((edges[i] ?? 0) + (edges[i + 1] ?? 0)) / 2,
    lo: edges[i] ?? 0,
    hi: edges[i + 1] ?? 0,
    share: c / total,
    count: c,
    above: marker != null ? (edges[i] ?? 0) >= marker : false,
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 4 }} barCategoryGap={2}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="mid" tickFormatter={format} minTickGap={40} axisLine={AXIS} tickLine={false} tick={TICK} />
        <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} width={44} axisLine={false} tickLine={false} tick={TICK} />
        <Tooltip
          isAnimationActive={false}
          cursor={{ fill: "var(--surface-2)" }}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
            if (!active || !p) return null;
            return (
              <TooltipBox
                title={`${format(p.lo)} – ${format(p.hi)}`}
                rows={[
                  { label: "Share of paths", value: `${(p.share * 100).toFixed(1)}%` },
                  { label: "Paths", value: p.count.toLocaleString() },
                ]}
              />
            );
          }}
        />
        <Bar dataKey="share" fill="var(--series-1)" radius={[1, 1, 0, 0]} isAnimationActive={false} maxBarSize={24} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------- generic table

export function DataTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string; align?: "left" | "right" }[];
  rows: Record<string, ReactNode>[];
}) {
  return (
    <Table>
      <thead>
        <tr>
          {columns.map((c) => (
            <Th key={c.key} align={c.align}>
              {c.label}
            </Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {columns.map((c) => (
              <Td key={c.key} align={c.align}>
                {r[c.key]}
              </Td>
            ))}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
