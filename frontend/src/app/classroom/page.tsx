import type { Metadata } from "next";
import Link from "next/link";

import { ANSWERS, EXERCISES } from "@/lib/classroom";
import { date, money, num, pct } from "@/lib/format";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = { title: "Classroom" };

const link = "underline underline-offset-2";
const a = ANSWERS;

const PLAN = [
  { time: "0 to 5 min", activity: "Hook", notes: "Ask: would you put all your savings into one company? Take a quick show of hands, then say the lesson tests that instinct with numbers." },
  { time: "5 to 15 min", activity: `Exercise 1: ${EXERCISES[0]?.title}`, notes: "Students find the safest single asset, then a portfolio that is safer still. Ask why that is possible." },
  { time: "15 to 30 min", activity: `Exercise 2: ${EXERCISES[1]?.title}`, notes: "The core of the lesson. Pause the class after the backtest and compare answers." },
  { time: "30 to 40 min", activity: `Exercise 3: ${EXERCISES[2]?.title}`, notes: "Link the widening range to uncertainty, and the falling chance of a loss to time in the market." },
  { time: "40 to 45 min", activity: "Exit question", notes: "One sentence each. Fast finishers try the ESG extension." },
];

const KEY = [
  {
    title: EXERCISES[0]?.title,
    points: [
      `The safest single asset is ${a.lowest_single_asset_volatility.ticker} (a government bond index), with a volatility of ${pct(a.lowest_single_asset_volatility.value, 1)} a year.`,
      `The most negative correlation is between ${a.lowest_correlation.assets.join(" and ")}: ${num(a.lowest_correlation.value)}.`,
      `The minimum-volatility portfolio reaches ${pct(a.min_volatility_portfolio, 1)}, below every single asset, because assets that move in opposite directions partly cancel each other out.`,
    ],
  },
  {
    title: EXERCISES[1]?.title,
    points: [
      `The optimiser promises a Sharpe ratio of ${num(a.max_sharpe_promised)}.`,
      `Re-optimised every month from ${date(a.backtest.evaluation[0])} to ${date(a.backtest.evaluation[1])}, the strategy achieved a Sharpe ratio of ${num(a.backtest.strategy_sharpe)} (growth of ${pct(a.backtest.strategy_cagr, 1)} a year). Simply holding equal weights achieved ${num(a.backtest.equal_weight_sharpe)} (${pct(a.backtest.equal_weight_cagr, 1)} a year).`,
      `Reasons: the optimiser treats past averages as if they were the future, and it trades a lot (about ${num(a.backtest.annual_turnover, 1)} times the portfolio's value each year), which costs money. Research on real data finds the same: equal weights are hard to beat.`,
    ],
  },
  {
    title: EXERCISES[2]?.title,
    points: [
      `After 1 year, the chance of a loss is about ${pct(a.monte_carlo.one_year.probability_of_loss, 0)}; 90% of outcomes lie between ${money(a.monte_carlo.one_year.p05)} and ${money(a.monte_carlo.one_year.p95)}.`,
      `After 10 years, it is about ${pct(a.monte_carlo.ten_years.probability_of_loss, 0)}; 90% of outcomes lie between ${money(a.monte_carlo.ten_years.p05)} and ${money(a.monte_carlo.ten_years.p95)} (median ${money(a.monte_carlo.ten_years.p50)}).`,
      "The range widens because uncertainty compounds over time; the chance of a loss falls because the expected growth builds up faster than the typical swing. This assumes the estimates are right, which exercise 2 questions.",
    ],
  },
  {
    title: "Extension (ESG)",
    points: [
      `Requiring an ESG score of at least 70 lowers the Sharpe ratio from ${num(a.esg.baseline_sharpe)} to ${num(a.esg.esg_sharpe)} and raises volatility from ${pct(a.esg.baseline_volatility, 0)} to ${pct(a.esg.esg_volatility, 0)}, on these invented assets. Whether that is worth it is a values question, which makes it a good discussion.`,
    ],
  },
];

export default function ClassroomPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Classroom</p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">Teach with Ardentum</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        A ready-made 45-minute lesson on diversification, estimation error and risk. Students run real portfolio calculations themselves, on invented demo assets, and discover why a simple equal split is hard to beat.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/classroom/worksheet" className="inline-flex h-10 items-center rounded-sm bg-accent px-5 text-sm font-medium text-on-accent hover:bg-accent-hover">
          Open the student worksheet
        </Link>
        <Link href="/tour" className="inline-flex h-10 items-center rounded-sm border border-line-strong bg-surface px-5 text-sm font-medium text-ink hover:bg-surface-2">
          Try the guided tour first
        </Link>
      </div>

      <dl className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[
          ["Length", "45 minutes, three exercises and an exit question"],
          ["For", "Ages 14 to 18 in economics, mathematics or business; no finance knowledge needed"],
          ["Needs", "A browser on a laptop, tablet or phone, one per student or pair; no sign-in, install or cost"],
          ["Data", "Fourteen invented assets (names end in .SYN), labelled as such on every page"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-sm border border-line bg-surface px-4 py-3">
            <dt className="text-xs text-ink-2">{k}</dt>
            <dd className="mt-1 text-sm text-ink">{v}</dd>
          </div>
        ))}
      </dl>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Students will be able to</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
          <li>explain why combining assets can reduce risk, using correlation;</li>
          <li>tell the difference between an estimate from past data and what happens next;</li>
          <li>read a range of simulated outcomes and say what it does and does not mean.</li>
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Before the lesson</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
          <li>Open the site about five minutes before class: the free server can take up to a minute to wake up after a quiet period.</li>
          <li>Print the worksheet or share its link. It works on screen too.</li>
          <li>
            Students should start from the default settings so their numbers match the answers below: a new private window works, or the button on the{" "}
            <Link href="/cookies" className={link}>
              Cookie Policy
            </Link>{" "}
            page that clears saved settings.
          </li>
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Lesson plan</h2>
        <div className="mt-3 overflow-x-auto" tabIndex={0}>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["Time", "Activity", "Notes"].map((h) => (
                  <th key={h} scope="col" className="border-b border-line px-2 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PLAN.map((r) => (
                <tr key={r.time}>
                  <td className="whitespace-nowrap border-b border-line px-2 py-2 align-top text-ink">{r.time}</td>
                  <td className="border-b border-line px-2 py-2 align-top text-ink">{r.activity}</td>
                  <td className="border-b border-line px-2 py-2 align-top text-ink-2">{r.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Answers</h2>
        <p className="mt-1 text-sm text-ink-2">With the default settings. The calculations are deterministic, so every student who follows the steps sees the same numbers.</p>
        {KEY.map((k) => (
          <div key={k.title} className="mt-4">
            <h3 className="text-sm font-semibold text-ink">{k.title}</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-2">
              {k.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Common misconceptions</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
          <li>&quot;A higher promised Sharpe ratio means a better portfolio.&quot; It means a better portfolio if the estimates are right, and they rarely are.</li>
          <li>&quot;Volatility means losing money.&quot; It measures how much returns swing, up as well as down.</li>
          <li>&quot;The simulation predicts the future.&quot; It shows what could happen if the assumptions hold.</li>
          <li>&quot;So optimisation is useless.&quot; It is sensitive to its inputs. Methods that need fewer estimates, such as minimum volatility, tend to hold up better.</li>
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">Going further</h2>
        <p className="mt-2 text-sm text-ink-2">
          The <Link href="/research" className={link}>methodology</Link> explains every calculation. The guided tour covers the rest of the workspace.
          {LEGAL.contactEmail && (
            <>
              {" "}If you use Ardentum with a class, a short note to{" "}
              <a href={`mailto:${LEGAL.contactEmail}`} className={link}>
                {LEGAL.contactEmail}
              </a>{" "}
              helps improve it.
            </>
          )}
        </p>
      </section>
    </main>
  );
}
