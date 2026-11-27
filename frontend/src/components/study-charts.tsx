"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { num, pct, signedNum, signedPct } from "@/lib/format";

import { ChartFrame, DataTable, niceAxis, seriesColor, TooltipBox } from "./charts";

/**
 * The figures of the research notes. They draw recorded study output only: every value
 * arrives computed, and these components choose axes and format numbers.
 */

const AXIS = { stroke: "var(--axis)" };
const TICK = { fill: "var(--muted)", fontSize: "0.6875rem" };
const LABEL = { fill: "var(--muted)", fontSize: "0.6875rem" };

type Kind = "ratio" | "pct" | "signedRatio" | "signedPct" | "hedge";

function fmt(kind: Kind, v: number, digits?: number): string {
  if (kind === "pct") return pct(v, digits ?? 1);
  if (kind === "signedPct") return signedPct(v, digits ?? 1);
  if (kind === "signedRatio") return signedNum(v, digits ?? 2);
  return num(v, digits ?? 2);
}

// ------------------------------------------------------------------ growth of $1 (log scale)

export function GrowthChart({
  title,
  note,
  dates,
  series,
}: {
  title: string;
  note: string;
  dates: string[];
  series: { name: string; values: number[] }[];
}) {
  const data = useMemo(
    () =>
      dates.map((d, i) => {
        const row: Record<string, number | string> = { date: d };
        series.forEach((s, j) => (row[`s${j}`] = s.values[i] ?? Number.NaN));
        return row;
      }),
    [dates, series],
  );
  const all = series.flatMap((s) => s.values).filter((v) => v > 0);
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const ticks = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000].filter((t) => t >= lo / 1.5 && t <= hi * 1.5);
  const decades = dates.filter((d) => d.endsWith("-01-31") && Number(d.slice(0, 4)) % 10 === 0);
  const yearEnds = dates.map((d, i) => [d, i] as const).filter(([d]) => d.slice(5, 7) === "12");
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={series.map((s, i) => ({ label: s.name, color: seriesColor(i) }))}
      table={
        <DataTable
          columns={[{ key: "date", label: "Year end" }, ...series.map((s, i) => ({ key: `s${i}`, label: s.name, align: "right" as const }))]}
          rows={yearEnds.map(([d, i]) => {
            const row: Record<string, string> = { date: d.slice(0, 4) };
            series.forEach((s, j) => (row[`s${j}`] = `$${num(s.values[i], 2)}`));
            return row;
          })}
        />
      }
    >
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="date" ticks={decades} tickFormatter={(d: string) => d.slice(0, 4)} axisLine={AXIS} tickLine={false} tick={TICK} />
          <YAxis
            scale="log"
            domain={[ticks[0] ?? lo, ticks[ticks.length - 1] ?? hi]}
            ticks={ticks}
            allowDataOverflow
            tickFormatter={(v: number) => `$${v}`}
            width={52}
            axisLine={false}
            tickLine={false}
            tick={TICK}
          />
          <Tooltip
            isAnimationActive={false}
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(label).slice(0, 7)}
                  rows={series.map((s, j) => {
                    const p = payload.find((x) => x.dataKey === `s${j}`);
                    return { label: s.name, value: p && typeof p.value === "number" ? `$${num(p.value, 2)}` : "n/a", color: seriesColor(j) };
                  })}
                />
              ) : null
            }
          />
          {series.map((s, j) => (
            <Line key={s.name} dataKey={`s${j}`} name={s.name} type="linear" stroke={seriesColor(j)} strokeWidth={1.75} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ paired horizontal bars

export function PairedBarChart({
  title,
  note,
  rows,
  names,
  kind,
  axisLabel,
}: {
  title: string;
  note: string;
  rows: { label: string; a: number; b: number }[];
  names: [string, string];
  kind: Kind;
  axisLabel: string;
}) {
  const values = rows.flatMap((r) => [r.a, r.b]);
  const ax = niceAxis(Math.min(0, ...values), Math.max(0, ...values), 5);
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={names.map((n, i) => ({ label: n, color: seriesColor(i), kind: "rect" as const }))}
      table={
        <DataTable
          columns={[
            { key: "label", label: "" },
            { key: "a", label: names[0], align: "right" },
            { key: "b", label: names[1], align: "right" },
          ]}
          rows={rows.map((r) => ({ label: r.label, a: fmt(kind, r.a), b: fmt(kind, r.b) }))}
        />
      }
    >
      <ResponsiveContainer width="100%" height={rows.length * 44 + 56}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 20, bottom: 18, left: 4 }} barGap={2} barCategoryGap="22%">
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            domain={[ax.min, ax.max]}
            ticks={ax.ticks}
            tickFormatter={(v: number) => fmt(kind, v, kind.includes("Pct") || kind === "pct" ? 0 : 2)}
            axisLine={AXIS}
            tickLine={false}
            tick={TICK}
            label={{ value: axisLabel, position: "insideBottom", offset: -12, ...LABEL }}
          />
          <YAxis type="category" dataKey="label" width={164} axisLine={false} tickLine={false} tick={{ ...TICK, fill: "var(--ink-2)" }} interval={0} />
          <ReferenceLine x={0} stroke="var(--ink-2)" strokeWidth={1} />
          <Tooltip
            isAnimationActive={false}
            cursor={{ fill: "var(--surface-2)" }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(label)}
                  rows={payload.map((p, i) => ({ label: names[i] ?? "", value: fmt(kind, Number(p.value)), color: seriesColor(i) }))}
                />
              ) : null
            }
          />
          <Bar dataKey="a" name={names[0]} fill={seriesColor(0)} isAnimationActive={false} radius={1} />
          <Bar dataKey="b" name={names[1]} fill={seriesColor(1)} isAnimationActive={false} radius={1} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ lines over years

export function YearLinesChart({
  title,
  note,
  years,
  series,
  references,
  kind,
  axisLabel,
}: {
  title: string;
  note: string;
  years: string[];
  series: { name: string; values: (number | null)[] }[];
  references: { value: number; label: string; position?: "insideTopRight" | "insideBottomLeft" }[];
  kind: Kind;
  axisLabel: string;
}) {
  const data = years.map((y, i) => {
    const row: Record<string, number | string | null> = { year: y };
    series.forEach((s, j) => (row[`s${j}`] = s.values[i] ?? null));
    return row;
  });
  const values = [...series.flatMap((s) => s.values.filter((v): v is number => v !== null)), ...references.map((r) => r.value)];
  const ax = niceAxis(Math.min(...values), Math.max(...values), 6);
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={series.map((s, i) => ({ label: s.name, color: seriesColor(i) }))}
      table={
        <DataTable
          columns={[{ key: "year", label: "Window ending" }, ...series.map((s, i) => ({ key: `s${i}`, label: s.name, align: "right" as const }))]}
          rows={years.map((y, i) => {
            const row: Record<string, string> = { year: y };
            series.forEach((s, j) => (row[`s${j}`] = s.values[i] === null || s.values[i] === undefined ? "n/a" : fmt(kind, s.values[i] as number)));
            return row;
          })}
        />
      }
    >
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 12, right: 20, bottom: 18, left: 4 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="year" axisLine={AXIS} tickLine={false} tick={TICK} minTickGap={16} label={{ value: "End of five-year window", position: "insideBottom", offset: -12, ...LABEL }} />
          <YAxis
            domain={[ax.min, ax.max]}
            ticks={ax.ticks}
            tickFormatter={(v: number) => fmt(kind, v, 1)}
            width={60}
            axisLine={false}
            tickLine={false}
            tick={TICK}
            label={{ value: axisLabel, angle: -90, position: "insideLeft", offset: 0, ...LABEL, style: { textAnchor: "middle" } }}
          />
          {references.map((r) => (
            <ReferenceLine key={r.value} y={r.value} stroke="var(--ink-2)" strokeDasharray={r.value === 0 ? undefined : "4 3"} label={{ value: r.label, position: r.position ?? "insideTopRight", ...LABEL }} />
          ))}
          <Tooltip
            isAnimationActive={false}
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={`Five years to ${String(label)}`}
                  rows={series.map((s, j) => {
                    const p = payload.find((x) => x.dataKey === `s${j}`);
                    return { label: s.name, value: p && typeof p.value === "number" ? fmt(kind, p.value) : "n/a", color: seriesColor(j) };
                  })}
                />
              ) : null
            }
          />
          {series.map((s, j) => (
            <Line
              key={s.name}
              dataKey={`s${j}`}
              name={s.name}
              type="linear"
              stroke={seriesColor(j)}
              strokeWidth={2}
              dot={{ r: 2.5, fill: seriesColor(j), stroke: "none" }}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ promised, delivered, 1/N

export function PromiseChart({
  title,
  note,
  rows,
}: {
  title: string;
  note: string;
  rows: { label: string; promised: number; delivered: number; low: number; high: number; equal: number }[];
}) {
  const names = ["Promised (average, in sample)", "Delivered (out of sample), 95% interval", "Equal weights (1/N), same months"];
  // The whiskers' lengths either side of the delivered ratio (ErrorBar takes offsets).
  const data = rows.map((r) => ({ ...r, err: [r.delivered - r.low, r.high - r.delivered] }));
  const ax = niceAxis(0, Math.max(...rows.flatMap((r) => [r.promised, r.high, r.equal])), 5);
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={names.map((n, i) => ({ label: n, color: seriesColor(i), kind: "rect" as const }))}
      table={
        <DataTable
          columns={[
            { key: "label", label: "Setting" },
            { key: "promised", label: "Promised", align: "right" },
            { key: "delivered", label: "Delivered", align: "right" },
            { key: "interval", label: "95% interval", align: "right" },
            { key: "equal", label: "1/N", align: "right" },
          ]}
          rows={rows.map((r) => ({
            label: r.label,
            promised: num(r.promised),
            delivered: num(r.delivered),
            interval: `${num(r.low)} to ${num(r.high)}`,
            equal: num(r.equal),
          }))}
        />
      }
    >
      <ResponsiveContainer width="100%" height={rows.length * 86 + 56}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 20, bottom: 18, left: 4 }} barGap={2} barCategoryGap="18%">
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            domain={[ax.min, ax.max]}
            ticks={ax.ticks}
            tickFormatter={(v: number) => num(v, 1)}
            axisLine={AXIS}
            tickLine={false}
            tick={TICK}
            label={{ value: "Annualised Sharpe ratio", position: "insideBottom", offset: -12, ...LABEL }}
          />
          <YAxis type="category" dataKey="label" width={164} axisLine={false} tickLine={false} tick={{ ...TICK, fill: "var(--ink-2)" }} interval={0} />
          <Tooltip
            isAnimationActive={false}
            cursor={{ fill: "var(--surface-2)" }}
            content={({ active, payload, label }) => {
              const r = payload?.[0]?.payload as (typeof data)[number] | undefined;
              return active && r ? (
                <TooltipBox
                  title={String(label)}
                  rows={[
                    { label: "Promised", value: num(r.promised), color: seriesColor(0) },
                    { label: "Delivered", value: `${num(r.delivered)} (${num(r.low)} to ${num(r.high)})`, color: seriesColor(1) },
                    { label: "1/N", value: num(r.equal), color: seriesColor(2) },
                  ]}
                />
              ) : null;
            }}
          />
          <Bar dataKey="promised" fill={seriesColor(0)} isAnimationActive={false} radius={1} />
          <Bar dataKey="delivered" fill={seriesColor(1)} isAnimationActive={false} radius={1}>
            <ErrorBar dataKey="err" direction="x" width={6} strokeWidth={1.5} stroke="var(--ink)" />
          </Bar>
          <Bar dataKey="equal" fill={seriesColor(2)} isAnimationActive={false} radius={1} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ frontier, promised and realised

export function FrontierPairChart({
  title,
  note,
  curves,
}: {
  title: string;
  note: string;
  curves: { name: string; points: [number, number][] }[];
}) {
  const xs = curves.flatMap((c) => c.points.map((p) => p[0]));
  const ys = curves.flatMap((c) => c.points.map((p) => p[1]));
  const xa = niceAxis(Math.min(...xs) * 0.9, Math.max(...xs), 5);
  const ya = niceAxis(Math.min(0, ...ys), Math.max(...ys), 5);
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={curves.map((c, i) => ({ label: c.name, color: seriesColor(i === 0 ? 0 : 3) }))}
      table={
        <DataTable
          columns={[
            { key: "i", label: "Portfolio" },
            ...curves.flatMap((c, i) => [
              { key: `v${i}`, label: `${c.name}: volatility`, align: "right" as const },
              { key: `r${i}`, label: "return", align: "right" as const },
            ]),
          ]}
          rows={(curves[0]?.points ?? []).map((_, k) => {
            const row: Record<string, string> = { i: String(k + 1) };
            curves.forEach((c, i) => {
              row[`v${i}`] = pct(c.points[k]?.[0], 1);
              row[`r${i}`] = pct(c.points[k]?.[1], 1);
            });
            return row;
          })}
        />
      }
    >
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 12, right: 24, bottom: 18, left: 4 }}>
          <CartesianGrid />
          <XAxis
            type="number"
            dataKey="x"
            domain={[xa.min, xa.max]}
            ticks={xa.ticks}
            tickFormatter={(v: number) => pct(v, 0)}
            axisLine={AXIS}
            tickLine={false}
            tick={TICK}
            label={{ value: "Annualised volatility", position: "insideBottom", offset: -12, ...LABEL }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[ya.min, ya.max]}
            ticks={ya.ticks}
            tickFormatter={(v: number) => pct(v, 0)}
            width={60}
            axisLine={false}
            tickLine={false}
            tick={TICK}
            label={{ value: "Annualised return", angle: -90, position: "insideLeft", offset: 0, ...LABEL, style: { textAnchor: "middle" } }}
          />
          <ZAxis range={[28, 28]} />
          <Tooltip
            isAnimationActive={false}
            cursor={false}
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as { x: number; y: number; series: string } | undefined;
              return active && p ? (
                <TooltipBox
                  title={p.series}
                  rows={[
                    { label: "Return", value: pct(p.y, 1) },
                    { label: "Volatility", value: pct(p.x, 1) },
                  ]}
                />
              ) : null;
            }}
          />
          {curves.map((c, i) => (
            <Scatter
              key={c.name}
              name={c.name}
              data={c.points.map(([x, y]) => ({ x, y, series: c.name }))}
              fill={seriesColor(i === 0 ? 0 : 3)}
              line={{ stroke: seriesColor(i === 0 ? 0 : 3), strokeWidth: 2 }}
              lineType="joint"
              isAnimationActive={false}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ------------------------------------------------------------------ each year's promise and outcome

export function PromiseScatterChart({
  title,
  note,
  groups,
}: {
  title: string;
  note: string;
  groups: { name: string; points: { year: number; promised: number; realised: number }[] }[];
}) {
  const xs = groups.flatMap((g) => g.points.map((p) => p.promised));
  const ys = groups.flatMap((g) => g.points.map((p) => p.realised));
  const xa = niceAxis(Math.min(0, ...xs), Math.max(...xs), 5);
  const ya = niceAxis(Math.min(...ys), Math.max(...ys), 6);
  const lo = Math.max(xa.min, ya.min);
  const hi = Math.min(xa.max, ya.max);
  return (
    <ChartFrame
      title={title}
      subtitle={note}
      legend={[...groups.map((g, i) => ({ label: g.name, color: seriesColor(i), kind: "dot" as const })), { label: "Promise kept (45-degree line)", color: "var(--ink-2)" }]}
      table={
        <DataTable
          columns={[
            { key: "year", label: "Formed at end of" },
            ...groups.flatMap((g, i) => [
              { key: `p${i}`, label: `${g.name}: promised`, align: "right" as const },
              { key: `r${i}`, label: "next 12 months", align: "right" as const },
            ]),
          ]}
          rows={(groups[0]?.points ?? []).map((pt) => {
            const row: Record<string, string> = { year: String(pt.year) };
            groups.forEach((g, i) => {
              const m = g.points.find((x) => x.year === pt.year);
              row[`p${i}`] = m ? num(m.promised) : "n/a";
              row[`r${i}`] = m ? num(m.realised) : "n/a";
            });
            return row;
          })}
        />
      }
    >
      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 12, right: 24, bottom: 18, left: 4 }}>
          <CartesianGrid />
          <XAxis
            type="number"
            dataKey="x"
            domain={[xa.min, xa.max]}
            ticks={xa.ticks}
            tickFormatter={(v: number) => num(v, 1)}
            axisLine={AXIS}
            tickLine={false}
            tick={TICK}
            label={{ value: "Promised Sharpe ratio (in sample)", position: "insideBottom", offset: -12, ...LABEL }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[ya.min, ya.max]}
            ticks={ya.ticks}
            tickFormatter={(v: number) => num(v, 1)}
            width={60}
            axisLine={false}
            tickLine={false}
            tick={TICK}
            label={{ value: "Sharpe ratio, next 12 months", angle: -90, position: "insideLeft", offset: 0, ...LABEL, style: { textAnchor: "middle" } }}
          />
          <ZAxis range={[30, 30]} />
          <ReferenceLine
            segment={[
              { x: lo, y: lo },
              { x: hi, y: hi },
            ]}
            stroke="var(--ink-2)"
            strokeDasharray="4 3"
          />
          <ReferenceLine y={0} stroke="var(--axis)" />
          <Tooltip
            isAnimationActive={false}
            cursor={false}
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as { x: number; y: number; year: number; group: string } | undefined;
              return active && p ? (
                <TooltipBox
                  title={`${p.group}, formed end ${p.year}`}
                  rows={[
                    { label: "Promised", value: num(p.x) },
                    { label: "Next 12 months", value: num(p.y) },
                  ]}
                />
              ) : null;
            }}
          />
          {groups.map((g, i) => (
            <Scatter
              key={g.name}
              name={g.name}
              data={g.points.map((p) => ({ x: p.promised, y: p.realised, year: p.year, group: g.name }))}
              fill={seriesColor(i)}
              fillOpacity={0.85}
              isAnimationActive={false}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
