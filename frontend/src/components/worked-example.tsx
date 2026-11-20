"use client";

import { m } from "motion/react";
import { useState } from "react";

import { cx } from "@/lib/classes";
import { num, pct } from "@/lib/format";
import EXAMPLE from "@/lib/landing-example.json";

import { Badge, Segmented } from "./ui";

type Case = (typeof EXAMPLE.cases)[number];

const LIMITS = EXAMPLE.cases.map((c) => String(c.limit));
const limitLabel = (limit: number) => (limit >= 1 ? "None" : pct(limit, 0));
const year = (d: string) => d.slice(0, 4);

/** The fictional company's name; the ticker beside it carries the synthetic suffix. */
const plainName = (name: string) => name.replace(/ \(synthetic\)$/, "").replace(/^Synthetic /, "");

/**
 * One real optimisation, shown as the workspace shows it: the answer, the weights, and the
 * engine's reason for any weight the reader picks. The results were recorded from the
 * running app (scripts/capture-example.mjs), one for each limit, so choosing a limit
 * shows how the answer and its reasons change. Numbers are only formatted here.
 */
export function WorkedExample() {
  const [limit, setLimit] = useState("0.3");
  const shown: Case = EXAMPLE.cases.find((c) => String(c.limit) === limit) ?? EXAMPLE.cases[0]!;
  const [picked, setPicked] = useState(shown.holdings[0]!.ticker);
  const chosen = shown.holdings.find((h) => h.ticker === picked) ?? shown.holdings[0]!;

  return (
    <section aria-labelledby="example" className="min-w-0 rounded-lg border border-line bg-surface elev-1">
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-4">
        <div className="min-w-0">
          <h2 id="example" className="type-headline text-ink">
            Example: maximum Sharpe ratio, 8 assets
          </h2>
          <p className="mt-0.5 text-caption1 text-muted">
            Daily returns, {year(EXAMPLE.start)} to {year(EXAMPLE.end)}
          </p>
        </div>
        <Badge tone="synthetic" title="Every asset and price in this example is fictional.">
          {EXAMPLE.source}
        </Badge>
      </header>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5">
        <span className="text-footnote text-ink-2">Max weight per asset</span>
        <Segmented
          size="xs"
          label="Max weight per asset"
          value={limit}
          onChange={setLimit}
          items={LIMITS.map((v) => ({ value: v, label: limitLabel(Number(v)) }))}
        />
      </div>

      <dl aria-live="polite" className="mx-5 mt-4 grid grid-cols-3 gap-4 border-y border-line py-3.5">
        <Figure label="Sharpe ratio" value={num(shown.sharpe_ratio, 2)} strong />
        <Figure label="Expected return" value={pct(shown.expected_return, 1)} />
        <Figure label="Volatility" value={pct(shown.volatility, 1)} />
      </dl>

      <p className="px-5 pt-3 text-caption1 text-muted">Click an asset to see why it has this weight.</p>
      <ul className="px-2 pt-1.5">
        {shown.holdings.map((h) => {
          const on = h.ticker === chosen.ticker;
          return (
            <li key={h.ticker}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => setPicked(h.ticker)}
                className={cx(
                  "grid w-full grid-cols-[minmax(0,1fr)_3.25rem] items-center gap-x-3 gap-y-1 rounded-xs px-3 py-1.5 text-left sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_3.25rem]",
                  on ? "bg-surface-2" : "hover:bg-surface-2/60",
                )}
              >
                <span className={cx("truncate text-footnote", on ? "font-semibold text-ink" : "text-ink-2")}>{plainName(h.name)}</span>
                <span className={cx("text-right text-footnote tabular-nums sm:order-3", h.weight > 0 ? "font-semibold text-ink" : "text-muted")}>
                  {pct(h.weight, 1)}
                </span>
                <Bar weight={h.weight} limit={shown.limit} />
              </button>
            </li>
          );
        })}
      </ul>

      <div aria-live="polite" className="mx-5 mt-2 border-t border-line pt-3">
        <p className="text-footnote font-semibold text-ink">
          {plainName(chosen.name)} <span className="font-normal text-muted">{chosen.ticker}</span>
        </p>
        <p className="mt-1 min-h-[2.6rem] text-footnote leading-snug text-ink-2">{chosen.reason}</p>
      </div>

      <footer className="mt-3 border-t border-line px-5 py-3">
        {/* A full page load, so the workspace starts from the settings in the link. */}
        <a href={shown.href} className="hit text-footnote font-medium text-accent-ink underline-offset-2 hover:underline">
          Open in workspace
        </a>
      </footer>
    </section>
  );
}

function Figure({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-caption1 text-muted">{label}</dt>
      <dd className={cx("mt-0.5 tabular-nums tracking-[-0.01em]", strong ? "text-xl font-semibold text-ink" : "text-xl text-ink")}>{value}</dd>
    </div>
  );
}

/**
 * A weight as a bar on a scale from nothing to the whole portfolio, with the limit drawn
 * as a line the bar may reach but not pass. Only transforms change, on a spring.
 */
function Bar({ weight, limit }: { weight: number; limit: number }) {
  const w = Math.min(1, Math.max(0, weight));
  return (
    <span aria-hidden className="relative col-span-2 block h-2 overflow-hidden rounded-[2px] bg-surface-3 sm:order-2 sm:col-span-1">
      <m.span initial={false} animate={{ x: `${(w - 1) * 100}%` }} className="absolute inset-0 bg-[var(--series-1)]" />
      {limit < 1 && <m.span initial={false} animate={{ x: `${limit * 100}%` }} className="absolute inset-y-0 left-0 w-full border-l border-ink/55" />}
    </span>
  );
}
