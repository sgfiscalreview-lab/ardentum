import Link from "next/link";

import { WorkedExample } from "@/components/worked-example";
import { buttonClass } from "@/lib/classes";
import SIZES from "@/lib/screenshots.json";

/** The page's one grid: a narrow column that says what a thing is, and the thing itself. */
const GRID = "grid grid-cols-1 gap-x-10 gap-y-5 lg:grid-cols-[17rem_minmax(0,1fr)]";

const SHOTS: { id: keyof typeof SIZES; page: string; href: string; title: string; body: string; alt: string }[] = [
  {
    id: "optimise",
    page: "Optimise",
    href: "/app/optimise",
    title: "What to hold, and why",
    body: "Choose an objective (maximum Sharpe ratio, minimum volatility, a target return or volatility, maximum utility, minimum CVaR or risk parity) and constraints on weights, sectors, tracking error and ESG scores. The result lists the constraints that bind and the reason each asset is or is not held, derived from the optimality conditions.",
    alt: "Optimise page: headline result, expected return, volatility, Sharpe ratio and CVaR, with the weights of the assets held.",
  },
  {
    id: "frontier",
    page: "Frontier",
    href: "/app/frontier",
    title: "What each constraint costs",
    body: "The efficient frontier under your constraints, drawn next to the one without them, with the maximum-Sharpe and minimum-volatility portfolios marked. The gap between the two curves is the price of a constraint in expected return and risk.",
    alt: "Frontier page: two efficient frontiers in risk and return space with the maximum-Sharpe and minimum-volatility portfolios marked.",
  },
  {
    id: "simulate",
    page: "Simulate",
    href: "/app/simulate",
    title: "The range of outcomes the model implies",
    body: "Parametric, bootstrap or block-bootstrap paths from a seed you can reuse, with optional contributions or withdrawals. Results give percentile ranges and the probability of a loss, of reaching a target and of running out of money.",
    alt: "Simulate page: percentile fan chart of simulated portfolio values with summary statistics above it.",
  },
  {
    id: "backtest",
    page: "Backtest",
    href: "/app/backtest",
    title: "How the rule would have done on what was known then",
    body: "The strategy is estimated again at each rebalance from the data available on that date only, with transaction costs, a benchmark, a test of whether the difference from the benchmark could be luck, and attribution of returns to assets and sectors.",
    alt: "Backtest page: growth of the strategy and its benchmark over time, drawdowns and summary statistics.",
  },
];

/**
 * A real screenshot of the results, cut at whole cards and taken on the app's own page
 * background: the cards carry their own corners, borders and shadows, so the picture gets
 * no frame of its own (a frame around them would double every edge).
 */
function Screenshot({ id, alt }: { id: keyof typeof SIZES; alt: string }) {
  const { width, height } = SIZES[id];
  return (
    <figure className="-m-2 min-w-0">
      {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
      <img src={`/screenshots/${id}-light.png`} alt={alt} width={width} height={height} loading="lazy" className="only-light block h-auto w-full" />
      {/* eslint-disable-next-line @next/next/no-img-element -- static export serves plain files */}
      <img src={`/screenshots/${id}-dark.png`} alt={alt} width={width} height={height} loading="lazy" className="only-dark h-auto w-full" />
    </figure>
  );
}

const TEXT_LINK = "text-accent-ink underline underline-offset-2";

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-4 pb-10 pt-14 sm:pt-20">
      <section className="max-w-3xl">
        <h1 className="type-display text-ink">Portfolio analysis that shows its working.</h1>
        <p className="mt-6 text-[1.1875rem] leading-relaxed tracking-[-0.006em] text-ink-2 sm:text-xl">
          Ardentum builds, optimises, simulates and backtests investment portfolios. Every result arrives with the data, estimators, constraints and assumptions behind it, so you can check a number before you rely on it.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link href="/app" className={buttonClass("primary", "lg")}>
            Open the workspace
          </Link>
          <Link href="/tour" className={buttonClass("secondary", "lg")}>
            Take the guided tour
          </Link>
        </div>
        <p className="mt-4 text-sm text-muted">Free, and there is nothing to install. The demo data needs no account.</p>
      </section>

      <WorkedExample />

      <section aria-labelledby="product" className="mt-24 sm:mt-28">
        <div className={GRID}>
          <h2 id="product" className="type-title-1 text-ink">
            The pages behind it
          </h2>
          <p className="max-w-2xl text-subheadline leading-relaxed text-ink-2 lg:pt-1.5">
            Pictures of the application itself, running on the synthetic demo data. Each page answers one question and shows what the answer rests on.
          </p>
        </div>
        <div className="mt-12 space-y-20">
          {SHOTS.map((s) => (
            <article key={s.id} className={GRID}>
              <div className="lg:sticky lg:top-20 lg:self-start">
                <h3 className="type-title-2 text-ink">{s.title}</h3>
                <p className="mt-3 text-subheadline leading-relaxed text-ink-2">{s.body}</p>
                <p className="mt-3 text-subheadline">
                  <Link href={s.href} className={TEXT_LINK}>
                    Open {s.page}
                  </Link>
                </p>
              </div>
              <Screenshot id={s.id} alt={s.alt} />
            </article>
          ))}
        </div>
        <div className={`${GRID} mt-16`}>
          <h3 className="type-headline text-ink lg:pt-0.5">Also in the workspace</h3>
          <p className="max-w-2xl text-subheadline leading-relaxed text-ink-2">
            <Link href="/app/crises" className={TEXT_LINK}>
              Crisis replay
            </Link>{" "}
            through seven crashes since 1929,{" "}
            <Link href="/app/factors" className={TEXT_LINK}>
              factor exposure
            </Link>{" "}
            from the Fama-French model, a{" "}
            <Link href="/app/trades" className={TEXT_LINK}>
              trade list
            </Link>{" "}
            from what you hold to a target, side-by-side{" "}
            <Link href="/app/compare" className={TEXT_LINK}>
              comparison
            </Link>{" "}
            of portfolios, and the{" "}
            <Link href="/app/esg" className={TEXT_LINK}>
              cost of an ESG constraint
            </Link>
            .
          </p>
        </div>
      </section>

      <section aria-labelledby="basis" className={`${GRID} mt-24 border-t border-line pt-12`}>
        <h2 id="basis" className="type-title-1 text-ink">
          What the numbers rest on
        </h2>
        <dl className="max-w-2xl space-y-6 text-subheadline leading-relaxed">
          <div>
            <dt className="font-semibold text-ink">Data</dt>
            <dd className="mt-1 text-ink-2">
              Kenneth French US industry portfolios back to 1926, European Central Bank exchange rates, Treasury-bill rates, open company disclosures from WikiRate, or your own CSV files. Every result names its source, window and number of observations.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Methods</dt>
            <dd className="mt-1 text-ink-2">
              Ledoit–Wolf and Bayes–Stein estimation, Black–Litterman views, convex optimisation with every constraint checked again after solving, the stationary bootstrap and Brinson–Fachler attribution. The{" "}
              <Link href="/research" className={TEXT_LINK}>
                Research
              </Link>{" "}
              section gives each formula with its references.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Checks</dt>
            <dd className="mt-1 text-ink-2">
              The engine is tested against closed-form results, SciPy, PyPortfolioOpt and brute-force search. Problems with no solution and metrics that are undefined are reported with the reason and are never approximated.
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="limits" className={`${GRID} mt-16 border-t border-line pt-12`}>
        <h2 id="limits" className="type-title-1 text-ink">
          What it cannot tell you
        </h2>
        <div className="max-w-2xl space-y-3 text-subheadline leading-relaxed text-ink-2">
          <p>Expected returns estimated from history carry large errors, and an optimiser amplifies them. Minimum-volatility and minimum-CVaR objectives, shrinkage estimators and the weight-stability test exist for that reason.</p>
          <p>The built-in real data covers US industry portfolios. Individual securities need your own data or a licensed price feed.</p>
          <p>Simulations and backtests describe the stated model and the past. They cannot tell you what markets will do.</p>
        </div>
      </section>

      <section aria-labelledby="start" className={`${GRID} mt-16 border-t border-line pt-12`}>
        <h2 id="start" className="type-title-1 text-ink">
          Try it on your own question
        </h2>
        <div className="max-w-2xl">
          <p className="text-subheadline leading-relaxed text-ink-2">
            The workspace opens on synthetic demo data, labelled as such on every page, and switches to real US industry data at any time.{" "}
            <Link href="/app#examples" className={TEXT_LINK}>
              Start from an example
            </Link>{" "}
            to see a finished result in one click. Sign in with Google or GitHub to upload your own prices and save portfolios.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/app" className={buttonClass("primary", "lg")}>
              Open the workspace
            </Link>
            <Link href="/research" className={buttonClass("ghost", "lg")}>
              Read the methodology
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
