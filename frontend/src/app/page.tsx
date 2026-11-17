import Link from "next/link";

import { WorkedExample } from "@/components/worked-example";
import { WorkspacePages } from "@/components/workspace-pages";
import { buttonClass } from "@/lib/classes";

const TEXT_LINK = "text-accent-ink underline underline-offset-2";

const ALSO: { href: string; label: string }[] = [
  { href: "/app/crises", label: "Crisis replay" },
  { href: "/app/factors", label: "Factor exposure" },
  { href: "/app/trades", label: "Trade lists" },
  { href: "/app/compare", label: "Comparisons" },
  { href: "/app/esg", label: "ESG costs" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-4 pb-12 pt-12 sm:pt-16">
      <div className="grid grid-cols-1 items-start gap-x-14 gap-y-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,31rem)]">
        <section className="lg:pt-12">
          <h1 className="type-display max-w-xl text-ink">Portfolio analysis you can check.</h1>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-ink-2">
            Optimise, simulate and backtest investment portfolios. Each weight comes with its reason, and each number with its source.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/app" className={buttonClass("primary", "lg")}>
              Open the workspace
            </Link>
            <Link href="/tour" className={buttonClass("secondary", "lg")}>
              Take the guided tour
            </Link>
          </div>
          <p className="mt-4 text-footnote text-muted">Free. Nothing to install, and no account for the demo data.</p>
        </section>

        <WorkedExample />
      </div>

      <section aria-labelledby="pages" className="mt-24 sm:mt-28">
        <h2 id="pages" className="type-title-1 mb-6 text-ink">
          Inside the workspace
        </h2>
        <WorkspacePages />
        <p className="mt-10 text-subheadline text-ink-2">
          Also:{" "}
          {ALSO.map((a, i) => (
            <span key={a.href}>
              <Link href={a.href} className={TEXT_LINK}>
                {a.label}
              </Link>
              {i < ALSO.length - 1 ? ", " : "."}
            </span>
          ))}
        </p>
      </section>

      <section aria-labelledby="basis" className="mt-24 border-t border-line pt-12">
        <h2 id="basis" className="type-title-1 text-ink">
          Built to be checked
        </h2>
        <dl className="mt-8 grid grid-cols-1 gap-x-10 gap-y-6 text-subheadline leading-relaxed sm:grid-cols-3">
          <div>
            <dt className="font-semibold text-ink">Data</dt>
            <dd className="mt-1 text-ink-2">US industry returns since 1926, central bank exchange rates, open ESG data or your own files. Every result names its source.</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Methods</dt>
            <dd className="mt-1 text-ink-2">
              Standard, published methods, each written out with its references in the{" "}
              <Link href="/research" className={TEXT_LINK}>
                methodology
              </Link>
              .
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Tests</dt>
            <dd className="mt-1 text-ink-2">Every calculation is tested against a known answer. When a result cannot be computed, it says why.</dd>
          </div>
        </dl>
        <p className="mt-8 max-w-3xl text-footnote leading-relaxed text-muted">
          Estimates from history carry large errors, and backtests describe the past, not the future. The built-in real data covers US industries; single stocks need your own prices. Ardentum is for analysis and learning, not investment advice.
        </p>
      </section>

      <section aria-labelledby="start" className="mt-16 flex flex-wrap items-center justify-between gap-x-10 gap-y-6 border-t border-line pt-10">
        <div>
          <h2 id="start" className="type-title-2 text-ink">
            Try it on your own portfolio
          </h2>
          <p className="mt-1 text-subheadline text-ink-2">Sign in with Google or GitHub to upload prices and save your work.</p>
        </div>
        <Link href="/app" className={buttonClass("primary", "lg")}>
          Open the workspace
        </Link>
      </section>
    </main>
  );
}
