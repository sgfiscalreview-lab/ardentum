import Link from "next/link";

const FEATURES = [
  { title: "Estimate", body: "Historical, Bayes–Stein and Ledoit–Wolf estimators with explicit windows, frequencies and data provenance." },
  { title: "Optimise", body: "Minimum volatility, maximum Sharpe, target return or volatility and utility — with bounds, sector, tracking-error and ESG constraints." },
  { title: "Explain", body: "Why each asset is held or not, which constraints bind, how risk is distributed and how stable the weights are." },
  { title: "Simulate", body: "Seeded Monte Carlo (parametric, bootstrap, block bootstrap) with percentile ranges and drawdown distributions." },
  { title: "Backtest", body: "Walk-forward backtests that only use information available at each rebalance, with costs and attribution." },
  { title: "ESG", body: "Minimum scores, exclusions and preferences that change the optimisation, with their cost in return, risk and Sharpe ratio." },
];

const PRINCIPLES = [
  "Every number is computed by a tested quantitative engine — never in the browser.",
  "Estimates are labelled as estimates; historical results are labelled in-sample or out-of-sample.",
  "Infeasible problems and undefined metrics are reported, never silently approximated.",
  "Demo data is synthetic and says so everywhere. ESG scores always carry their source.",
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-14">
      <section className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Quantitative portfolio analysis</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Build portfolios you can explain.
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-ink-2">
          Ardentum constructs, optimises, simulates, backtests and compares investment portfolios — and shows the
          mathematics, assumptions and limitations behind every result.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/app" className="inline-flex h-10 items-center rounded-md bg-accent px-5 text-sm font-medium text-white hover:bg-accent-hover">
            Open the workspace
          </Link>
          <Link href="/research" className="inline-flex h-10 items-center rounded-md border border-line-strong bg-surface px-5 text-sm font-medium text-ink hover:bg-surface-2">
            Read the methodology
          </Link>
        </div>
        <p className="mt-4 text-xs text-muted">
          The workspace opens with a clearly labelled synthetic demo universe. Sign in to upload your own data and save portfolios.
        </p>
      </section>

      <section aria-labelledby="features" className="mt-16">
        <h2 id="features" className="sr-only">
          Capabilities
        </h2>
        <div className="grid gap-px overflow-hidden rounded-lg border border-line bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-surface p-5">
              <h3 className="text-sm font-semibold text-ink">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="principles" className="mt-16 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <h2 id="principles" className="text-xl font-semibold tracking-tight text-ink">
            Correctness before convenience
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-2">
            Portfolio tools fail quietly: an optimiser that ignores a constraint, a backtest that peeks at the future, a Sharpe ratio on a zero-volatility series. Ardentum is built to fail loudly instead.
          </p>
        </div>
        <ul className="space-y-3">
          {PRINCIPLES.map((p) => (
            <li key={p} className="flex gap-3 text-sm text-ink">
              <span aria-hidden className="mt-1.5 inline-block size-1.5 shrink-0 rounded-full bg-accent" />
              {p}
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-20 border-t border-line pt-6 text-xs leading-relaxed text-muted">
        Ardentum is an analytical tool for education and research. It does not provide investment advice. Model outputs are estimates based on historical data and stated assumptions; past performance does not predict future results.
      </footer>
    </main>
  );
}
