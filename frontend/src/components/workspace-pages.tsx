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
    title: "Optimisation",
    body: "Seven objectives, including maximum Sharpe, minimum volatility, minimum CVaR and risk parity, with limits on weights, sectors, tracking error and ESG score.",
    alt: "Optimise page: headline result, expected return, volatility, Sharpe ratio and CVaR, with the weights of the assets held.",
  },
  {
    id: "frontier",
    page: "Frontier",
    href: "/app/frontier",
    title: "Efficient frontier",
    body: "The frontier with and without your constraints, showing what each constraint costs in return.",
    alt: "Frontier page: two efficient frontiers in risk and return space with the maximum-Sharpe and minimum-volatility portfolios marked.",
  },
  {
    id: "simulate",
    page: "Simulate",
    href: "/app/simulate",
    title: "Monte Carlo simulation",
    body: "Parametric and bootstrap simulations with a fixed seed, reporting percentiles and the probability of a loss.",
    alt: "Simulate page: percentile fan chart of simulated portfolio values with summary statistics above it.",
  },
  {
    id: "backtest",
    page: "Backtest",
    href: "/app/backtest",
    title: "Walk-forward backtest",
    body: "Weights re-estimated at each rebalance using only data available at the time, net of transaction costs, against a benchmark.",
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
