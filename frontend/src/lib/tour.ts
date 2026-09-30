/**
 * The guided tour: eight stops through the workspace on the synthetic demo data, no
 * sign-in needed. Used by the /tour page and by the tour bar shown inside the workspace
 * when a page is opened with ?tour=<step>.
 */
export interface TourStep {
  href: string;
  title: string;
  /** What the page is for. */
  about: string;
  /** One concrete thing to do. */
  tryThis: string;
  /** What to notice in the result. */
  lookFor: string;
}

export const TOUR: TourStep[] = [
  {
    href: "/app",
    title: "Choose the data",
    about: "Every analysis starts from a universe: a dataset, a set of assets and a date window, plus how expected returns and risk are estimated from it.",
    tryThis: "Keep the synthetic demo universe for now. Open the Dataset list to see the real alternative: US industry portfolios from the Kenneth R. French Data Library, back to 1926.",
    lookFor: "The Estimation card: expected returns (historical, Bayes-Stein or Black-Litterman) and covariance (sample or Ledoit-Wolf shrinkage). These choices change every result that follows.",
  },
  {
    href: "/app/analytics",
    title: "Look at the history",
    about: "Before optimising anything, see how each asset behaved: growth, volatility, drawdowns and how the assets move together.",
    tryThis: "Choose Compute analytics.",
    lookFor: "The correlation matrix. Assets that move together add little diversification; the optimiser will use the ones that do not.",
  },
  {
    href: "/app/optimise",
    title: "Optimise a portfolio",
    about: "Pick an objective and constraints, and the optimiser finds the weights. The result explains itself: which constraints bind and why each asset is or is not held.",
    tryThis: "Keep Maximum Sharpe ratio with a 30% cap per asset and choose Optimise. Then choose Use as working portfolio so the next steps use it.",
    lookFor: "The box headed Read before relying on this result. It states how uncertain the expected-return estimates are, which is why optimised weights can be fragile.",
  },
  {
    href: "/app/frontier",
    title: "See the trade-off",
    about: "The efficient frontier shows the best expected return for each level of risk, with and without your constraints.",
    tryThis: "Choose Trace frontier. Then switch Risk measure to CVaR and trace again.",
    lookFor: "The gap between the constrained and unconstrained frontiers: that is what the constraints cost in expected return, under these estimates.",
  },
  {
    href: "/app/esg",
    title: "Price an ESG constraint",
    about: "Requiring a minimum ESG score changes the portfolio. This page measures by how much, against the same portfolio without the ESG settings.",
    tryThis: "In Constraints, open ESG, set Minimum portfolio ESG score to 70, tick Exclude assets without an ESG score (the demo gold asset has none), and choose Measure ESG impact.",
    lookFor: "The ESG-efficient frontier: the best achievable Sharpe ratio as the required ESG score rises. The demo scores are synthetic; real open scores can be added on the ESG data page.",
  },
  {
    href: "/app/simulate",
    title: "Simulate the future",
    about: "Monte Carlo simulation turns estimates into a range of possible outcomes, with regular contributions or withdrawals if you want them.",
    tryThis: "Keep the working portfolio and choose Simulate. Then switch Method to Block bootstrap and run it again with the same seed.",
    lookFor: "The width of the percentile bands, and that the same seed always gives the same result.",
  },
  {
    href: "/app/backtest",
    title: "Test it honestly",
    about: "A walk-forward backtest rebuilds the portfolio at each rebalance using only the data available on that date, then charges trading costs.",
    tryThis: "Choose Run backtest with the default settings.",
    lookFor: "The strategy against its benchmark after costs. Out of sample, optimised portfolios often do no better than splitting money equally; Ardentum's first research study tests this on US industry data since 1970.",
  },
  {
    href: "/app/compare",
    title: "Compare side by side",
    about: "Put portfolios next to each other on the same data: returns, risk, drawdowns and how their returns are correlated.",
    tryThis: "Choose the working portfolio and the equal-weight portfolio, then Compare.",
    lookFor: "The in-sample warning: portfolios optimised on this window will look better here than they would in the future. The backtest is the fairer test.",
  },
];

/** The tour step for ?tour=<n> on the given page, or null if it does not belong there. */
export function tourStepFor(pathname: string, param: string | null): number | null {
  if (!param || !/^\d+$/.test(param)) return null;
  const n = Number(param);
  if (n < 1 || n > TOUR.length) return null;
  const path = pathname.replace(/\/$/, "") || "/";
  return TOUR[n - 1]?.href === path ? n : null;
}

export function tourHref(step: number): string {
  const s = TOUR[step - 1];
  return s ? `${s.href}?tour=${step}` : "/tour";
}
