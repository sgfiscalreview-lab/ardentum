"use client";

import Link from "next/link";
import { useState } from "react";

import SIZES from "@/lib/screenshots.json";

import { Tabs } from "./ui";

type Id = keyof typeof SIZES;

const PAGES: { id: Id; page: string; href: string; title: string; body: string; alt: string }[] = [
  {
    id: "optimise",
    page: "Optimise",
    href: "/app/optimise",
    title: "What to hold, and why",
    body: "Pick an objective and your limits. Every asset comes back with the reason for its weight.",
    alt: "Optimise page: headline result, expected return, volatility, Sharpe ratio and CVaR, with the weights of the assets held.",
  },
  {
    id: "frontier",
    page: "Frontier",
    href: "/app/frontier",
    title: "What a constraint costs",
    body: "The efficient frontier with your limits, next to the one without them. The gap is the price in return and risk.",
    alt: "Frontier page: two efficient frontiers in risk and return space with the maximum-Sharpe and minimum-volatility portfolios marked.",
  },
  {
    id: "simulate",
    page: "Simulate",
    href: "/app/simulate",
    title: "The range of outcomes",
    body: "Thousands of paths from a seed you can reuse, with the chance of a loss or of reaching a target.",
    alt: "Simulate page: percentile fan chart of simulated portfolio values with summary statistics above it.",
  },
  {
    id: "backtest",
    page: "Backtest",
    href: "/app/backtest",
    title: "How it would have done",
    body: "Rebuilt at every rebalance from the data known on that date, with costs and a benchmark.",
    alt: "Backtest page: growth of the strategy and its benchmark over time, drawdowns and summary statistics.",
  },
];

/**
 * The four main workspace pages, one at a time: a real screenshot of each (cut at whole
 * cards on the app's own background, so it gets no frame of its own) beside one sentence.
 */
export function WorkspacePages() {
  const [id, setId] = useState<Id>("optimise");
  const shown = PAGES.find((p) => p.id === id) ?? PAGES[0]!;
  const { width, height } = SIZES[shown.id];

  return (
    <div>
      <Tabs label="Workspace pages" value={id} onChange={setId} items={PAGES.map((p) => ({ value: p.id, label: p.page }))} />
      <div role="tabpanel" aria-label={shown.page} className="mt-8 grid grid-cols-1 gap-x-12 gap-y-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <div className="lg:pt-2">
          <h3 className="type-title-2 text-ink">{shown.title}</h3>
          <p className="mt-2 text-subheadline leading-relaxed text-ink-2">{shown.body}</p>
          <p className="mt-4 text-subheadline">
            <Link href={shown.href} className="text-accent-ink underline underline-offset-2">
              Open {shown.page}
            </Link>
          </p>
        </div>
        <figure key={shown.id} className="-m-2 min-w-0">
          {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
          <img src={`/screenshots/${shown.id}-light.png`} alt={shown.alt} width={width} height={height} className="only-light block h-auto w-full" />
          {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
          <img src={`/screenshots/${shown.id}-dark.png`} alt={shown.alt} width={width} height={height} className="only-dark h-auto w-full" />
        </figure>
      </div>
    </div>
  );
}
