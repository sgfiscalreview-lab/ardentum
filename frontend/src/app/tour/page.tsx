import type { Metadata } from "next";
import Link from "next/link";

import { TOUR, tourHref } from "@/lib/tour";

export const metadata: Metadata = { title: "Guided tour" };

export default function TourPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Guided tour</p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">Ardentum in eight steps</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        About fifteen minutes, from choosing data to testing a portfolio out of sample. It runs on the synthetic demo universe, so nothing needs signing in and nothing you do is saved. Each step opens the page with a short note at the top saying what to try and what to look for.
      </p>
      <div className="mt-6">
        <Link href={tourHref(1)} className="inline-flex h-10 items-center rounded-sm bg-accent px-5 text-sm font-medium text-on-accent hover:bg-accent-hover">
          Start the tour
        </Link>
      </div>
      <ol className="mt-8 divide-y divide-[var(--border)] rounded-lg border border-line bg-surface">
        {TOUR.map((step, i) => (
          <li key={step.href} className="flex gap-4 px-5 py-4">
            <span className="w-6 shrink-0 pt-0.5 text-sm text-muted tabular">{i + 1}</span>
            <div className="min-w-0">
              <h2 className="font-medium text-ink">
                <Link href={tourHref(i + 1)} className="underline-offset-2 hover:underline">
                  {step.title}
                </Link>
              </h2>
              <p className="mt-1 text-sm text-ink-2">{step.about}</p>
              <p className="mt-2 text-sm text-ink-2">
                <span className="font-medium text-ink">Try: </span>
                {step.tryThis}
              </p>
              <p className="mt-1 text-sm text-ink-2">
                <span className="font-medium text-ink">Look for: </span>
                {step.lookFor}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-6 text-sm text-ink-2">
        Afterwards, the <Link href="/research" className="underline underline-offset-2">methodology</Link> explains every formula and how each calculation is checked. Sign in to upload your own prices and save portfolios.
      </p>
    </main>
  );
}
