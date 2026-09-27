import Link from "next/link";

const SHOTS = [
  {
    id: "optimise",
    title: "Optimisation with reasons",
    body: "Choose an objective (maximum Sharpe ratio, minimum volatility, a target return or volatility, maximum utility or minimum CVaR) and constraints on weights, sectors, tracking error and ESG scores. The result lists the constraints that bind and why each asset is or is not held, derived from the optimality conditions.",
    alt: "Optimise page: headline result, expected return, volatility, Sharpe ratio and CVaR, with the objective and constraint settings on the left.",
  },
  {
    id: "frontier",
    title: "Efficient frontier",
    body: "The constrained frontier drawn next to the unconstrained one, with the maximum-Sharpe and minimum-volatility portfolios marked, so the cost of each constraint is visible in expected return and risk.",
    alt: "Frontier page: two efficient frontiers in risk and return space with the maximum-Sharpe and minimum-volatility portfolios marked.",
  },
  {
    id: "simulate",
    title: "Monte Carlo simulation",
    body: "Parametric, bootstrap or block-bootstrap paths from a fixed seed, with optional contributions or withdrawals. Results include percentile ranges, the probability of a loss, of reaching a target and of running out of money.",
    alt: "Monte Carlo page: percentile fan chart of simulated portfolio values with summary statistics above it.",
  },
  {
    id: "backtest",
    title: "Walk-forward backtest",
    body: "The strategy is re-estimated at each rebalance using only data available on that date, with transaction costs, a benchmark and attribution of returns to assets and sectors.",
    alt: "Backtest page: growth of the strategy and its benchmark over time, drawdowns and summary statistics.",
  },
];

function Screenshot({ id, alt }: { id: string; alt: string }) {
  return (
    <figure className="min-w-0 border border-line-strong bg-surface">
      {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
      <img src={`/screenshots/${id}-light.png`} alt={alt} width={1224} height={930} loading="lazy" className="only-light block h-auto w-full" />
      {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
      <img src={`/screenshots/${id}-dark.png`} alt={alt} width={1224} height={930} loading="lazy" className="only-dark h-auto w-full" />
    </figure>
  );
}

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-4 pb-8 pt-14">
      <section className="max-w-3xl">
        <h1 className="font-display text-4xl font-semibold leading-tight text-ink sm:text-5xl">Portfolio analysis that shows its working.</h1>
        <p className="mt-5 text-lg leading-relaxed text-ink-2">
          Ardentum builds, optimises, simulates and backtests investment portfolios. Every result comes with its data window, estimators, binding constraints and assumptions, so you can check a number before you rely on it.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/app" className="inline-flex h-10 items-center rounded-sm bg-accent px-5 text-sm font-medium text-on-accent hover:bg-accent-hover">
            Open the workspace
          </Link>
          <Link href="/research" className="inline-flex h-10 items-center rounded-sm border border-line-strong bg-surface px-5 text-sm font-medium text-ink hover:bg-surface-2">
            Read the methodology
          </Link>
        </div>
        <p className="mt-4 max-w-2xl text-sm text-muted">
          The workspace opens on a synthetic demo universe, labelled as such on every page, and can switch to real US industry data at any time. Sign in with Google or GitHub to upload your own prices and save portfolios. The service is free.
        </p>
      </section>

      <section aria-labelledby="product" className="mt-20">
        <h2 id="product" className="font-display text-2xl font-semibold text-ink">
          What it looks like
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-ink-2">Screenshots of the application running on the synthetic demo dataset.</p>
        <div className="mt-8 space-y-14">
          {SHOTS.map((s) => (
            <article key={s.id} className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-10">
              <div>
                <h3 className="text-base font-semibold text-ink">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-2">{s.body}</p>
              </div>
              <Screenshot id={s.id} alt={s.alt} />
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="basis" className="mt-20 border-t border-line pt-10">
        <h2 id="basis" className="font-display text-2xl font-semibold text-ink">
          What the numbers rest on
        </h2>
        <dl className="mt-6 max-w-3xl space-y-6 text-sm leading-relaxed">
          <div>
            <dt className="font-semibold text-ink">Data</dt>
            <dd className="mt-1 text-ink-2">
              Kenneth French US industry portfolios back to 1926, European Central Bank exchange rates, Treasury-bill rates, open company disclosures from WikiRate, or your own CSV files. Every result names its source, window and number of observations.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Methods</dt>
            <dd className="mt-1 text-ink-2">
              Ledoit–Wolf and Bayes–Stein estimation, Black–Litterman views, convex optimisation with every constraint re-checked after solving, the stationary bootstrap and Brinson–Fachler attribution. The{" "}
              <Link href="/research" className="text-accent-ink underline underline-offset-2">
                Research
              </Link>{" "}
              section gives each formula with its references.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Checks</dt>
            <dd className="mt-1 text-ink-2">
              The engine is tested against closed-form results, SciPy, PyPortfolioOpt and brute-force search. Infeasible problems and undefined metrics are reported with a reason and are never approximated.
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="limits" className="mt-16 border-t border-line pt-10">
        <h2 id="limits" className="font-display text-2xl font-semibold text-ink">
          Limits
        </h2>
        <div className="mt-4 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-2">
          <p>Expected returns estimated from history carry large errors, and an optimiser amplifies them. Minimum-volatility and minimum-CVaR objectives, shrinkage estimators and the weight-stability test exist for that reason.</p>
          <p>The built-in real data covers US industry portfolios. Individual securities need your own data or a licensed price feed.</p>
          <p>Simulations and backtests describe the stated model and the past. They cannot tell you what markets will do.</p>
        </div>
      </section>
    </main>
  );
}
