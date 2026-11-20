import Link from "next/link";

import { WorkedExample } from "@/components/worked-example";
import { WorkspacePages } from "@/components/workspace-pages";
import { buttonClass } from "@/lib/classes";

const TEXT_LINK = "text-accent-ink underline underline-offset-2";

const ALSO: { href: string; label: string }[] = [
  { href: "/app/crises", label: "crisis replay" },
  { href: "/app/factors", label: "Fama-French factor exposure" },
  { href: "/app/trades", label: "trade lists" },
  { href: "/app/compare", label: "portfolio comparison" },
  { href: "/app/esg", label: "ESG analysis" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-4 pb-12 pt-12 sm:pt-16">
      <div className="grid grid-cols-1 items-start gap-x-14 gap-y-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,31rem)]">
        <section className="lg:pt-12">
          <h1 className="type-display max-w-xl text-ink">Build and test investment portfolios</h1>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-ink-2">
            Mean-variance and CVaR optimisation, Monte Carlo simulation and walk-forward backtests, with the assumptions behind every result listed alongside it.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/app" className={buttonClass("primary", "lg")}>
              Open the workspace
            </Link>
            <Link href="/tour" className={buttonClass("secondary", "lg")}>
              Take the guided tour
            </Link>
          </div>
          <p className="mt-4 text-footnote text-muted">Free to use. The demo data needs no account.</p>
        </section>

        <WorkedExample />
      </div>

      <section aria-labelledby="pages" className="mt-24 sm:mt-28">
        <h2 id="pages" className="type-title-1 mb-6 text-ink">
          The workspace
        </h2>
        <WorkspacePages />
        <p className="mt-10 text-subheadline text-ink-2">
          Also available:{" "}
          {ALSO.map((a, i) => (
            <span key={a.href}>
              <Link href={a.href} className={TEXT_LINK}>
                {a.label}
              </Link>
              {i < ALSO.length - 2 ? ", " : i === ALSO.length - 2 ? " and " : "."}
            </span>
          ))}
        </p>
      </section>

      <section aria-labelledby="basis" className="mt-24 border-t border-line pt-12">
        <h2 id="basis" className="type-title-1 text-ink">
          Methodology
        </h2>
        <dl className="mt-8 grid grid-cols-1 gap-x-10 gap-y-6 text-subheadline leading-relaxed sm:grid-cols-3">
          <div>
            <dt className="font-semibold text-ink">Data</dt>
            <dd className="mt-1 text-ink-2">Kenneth French US industry returns from 1926, ECB exchange rates, WikiRate ESG data, or your own CSV files.</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Methods</dt>
            <dd className="mt-1 text-ink-2">
              Ledoit-Wolf shrinkage, Black-Litterman, convex optimisation and the stationary bootstrap. Formulas and references are in the{" "}
              <Link href="/research" className={TEXT_LINK}>
                methodology pages
              </Link>
              .
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Testing</dt>
            <dd className="mt-1 text-ink-2">Calculations are tested against closed-form solutions and independent libraries such as SciPy and PyPortfolioOpt.</dd>
          </div>
        </dl>
        <p className="mt-8 max-w-3xl text-footnote leading-relaxed text-muted">
          Expected returns estimated from historical data are uncertain, and backtest results do not predict future performance. The built-in data covers US industry portfolios only. Ardentum is an educational tool and does not provide investment advice.
        </p>
      </section>

      <section aria-labelledby="start" className="mt-16 flex flex-wrap items-center justify-between gap-x-10 gap-y-6 border-t border-line pt-10">
        <div>
          <h2 id="start" className="type-title-2 text-ink">
            Get started
          </h2>
          <p className="mt-1 text-subheadline text-ink-2">Sign in with Google or GitHub to upload your own data and save portfolios.</p>
        </div>
        <Link href="/app" className={buttonClass("primary", "lg")}>
          Open the workspace
        </Link>
      </section>
    </main>
  );
}
