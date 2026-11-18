"use client";

import { m } from "motion/react";
import { useState } from "react";

import { pct } from "@/lib/format";
import EXAMPLE from "@/lib/landing-example.json";

import { Badge, buttonClass, Segmented } from "./ui";

type Case = (typeof EXAMPLE.cases)[number];

const LIMITS = EXAMPLE.cases.map((c) => String(c.limit));
const limitLabel = (limit: number) => (limit >= 1 ? "No limit" : pct(limit, 0));

/** The fictional company's name; the ticker beside it carries the synthetic suffix. */
const plainName = (name: string) => name.replace(/ \(synthetic\)$/, "").replace(/^Synthetic /, "");

/**
 * One real optimisation, set out as an answer with its working: each asset's weight next
 * to the reason the engine gives for it. The results were recorded from the running app
 * (scripts/capture-example.mjs), one for each limit, so choosing a limit shows how the
 * answer and its reasons change. Numbers are only formatted here.
 */
export function WorkedExample() {
  const [limit, setLimit] = useState("0.3");
  const shown: Case = EXAMPLE.cases.find((c) => String(c.limit) === limit) ?? EXAMPLE.cases[0]!;
  // The engine's sentence: the ratio, a colon, then the figures it is worked out from.
  const colon = shown.sharpe_statement.indexOf(":");
  const answer = shown.sharpe_statement.slice(0, colon);
  const working = shown.sharpe_statement.slice(colon);

  return (
    <section aria-labelledby="worked" className="mt-16 sm:mt-20">
      <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
        <div className="max-w-xl">
          <h2 id="worked" className="type-title-1 text-ink">
            One answer, with its working
          </h2>
          <p className="mt-2 text-subheadline leading-relaxed text-ink-2">
            Eight assets from the demo data, weighted for the highest expected Sharpe ratio. Change the most one asset may take, and the reasons change with the weights.
          </p>
          <p className="mt-2.5">
            <Badge tone="synthetic" title="Every asset and price in this example is fictional.">
              {EXAMPLE.source}
            </Badge>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-footnote font-medium text-ink-2">Maximum weight of one asset</span>
          <Segmented label="Maximum weight of one asset" value={limit} onChange={setLimit} items={LIMITS.map((v) => ({ value: v, label: limitLabel(Number(v)) }))} />
        </div>
      </div>

      <p aria-live="polite" className="mt-8 border-t border-line-strong pt-5 text-ink-2">
        <span className="type-title-2 text-ink">{answer}</span>
        <span className="text-subheadline">{working}</span>
      </p>

      <ul className="mt-5">
        {shown.holdings.map((h) => (
          <li
            key={h.ticker}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-1.5 border-t border-line py-3.5 lg:grid-cols-[15rem_minmax(0,16rem)_3.75rem_minmax(0,1fr)] lg:gap-x-6"
          >
            <div className="min-w-0">
              <span className="block truncate font-semibold tracking-[-0.008em] text-ink">{plainName(h.name)}</span>
              <span className="block truncate text-caption1 text-muted">
                {h.ticker}, {h.sector}
              </span>
            </div>
            <span className="text-right font-semibold tabular-nums text-ink lg:order-3">{pct(h.weight, 1)}</span>
            <Bar weight={h.weight} limit={shown.limit} />
            <p className="col-span-2 max-w-[68ch] text-footnote leading-relaxed text-ink-2 lg:order-4 lg:col-span-1 lg:text-subheadline">{h.reason}</p>
          </li>
        ))}
      </ul>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-5 border-t border-line-strong pt-5 text-footnote leading-relaxed lg:grid-cols-[15rem_minmax(0,1fr)]">
        <dt className="font-semibold text-ink">Read before relying on this result</dt>
        <dd className="max-w-[80ch] space-y-1.5 text-ink-2">
          {shown.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </dd>
        <dt className="font-semibold text-ink">Estimated from</dt>
        <dd className="max-w-[80ch] space-y-1.5 text-ink-2">
          {shown.assumptions.map((a) => (
            <p key={a}>{a}</p>
          ))}
        </dd>
      </dl>

      <p className="mt-6">
        {/* A full page load, so the workspace starts from the settings in the link. */}
        <a href={shown.href} className={buttonClass("secondary", "md")}>
          Open this result in the workspace
        </a>
      </p>
    </section>
  );
}

/**
 * A weight as a bar on a scale from nothing to the whole portfolio, with the limit drawn
 * as a line the bar may reach but not pass. Only transforms change, on a spring.
 */
function Bar({ weight, limit }: { weight: number; limit: number }) {
  const w = Math.min(1, Math.max(0, weight));
  return (
    <div aria-hidden className="relative col-span-2 h-3 overflow-hidden rounded-[3px] bg-surface-2 lg:order-2 lg:col-span-1 lg:mt-[0.4rem] lg:self-start">
      <m.div initial={false} animate={{ x: `${(w - 1) * 100}%` }} className="absolute inset-0 bg-[var(--series-1)]" />
      {limit < 1 && <m.div initial={false} animate={{ x: `${limit * 100}%` }} className="absolute inset-y-0 left-0 w-full border-l border-ink/55" />}
    </div>
  );
}
