/**
 * Plain-language definitions of the terms Ardentum shows. Each follows the methodology's
 * conventions (docs/methodology) and links to the page with the formulas. `labels` are the
 * exact result labels that link here.
 */
export interface GlossaryEntry {
  id: string;
  term: string;
  definition: string;
  labels?: string[];
  /** Methodology page slug with the formulas. */
  method?: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  {
    id: "annualised-return",
    term: "Annualised (expected) return",
    labels: ["Expected return", "Min-vol return", "Max-Sharpe return", "Min-CVaR return"],
    definition:
      "The average return per period scaled to a year. An expected return is an estimate from the historical window, not a forecast: the average of a few years of returns is very uncertain.",
    method: "returns-and-risk",
  },
  {
    id: "cagr",
    term: "CAGR (compound annual growth rate)",
    labels: ["CAGR", "Median annual growth"],
    definition:
      "The constant yearly growth rate that turns the starting value into the final value. Unlike the average return, it accounts for compounding, so losses weigh more than equal gains.",
    method: "returns-and-risk",
  },
  {
    id: "volatility",
    term: "Volatility",
    labels: ["Volatility", "Expected volatility"],
    definition:
      "The standard deviation of returns, annualised: how widely returns swing around their average. It treats gains and losses alike.",
    method: "returns-and-risk",
  },
  {
    id: "sharpe-ratio",
    term: "Sharpe ratio",
    labels: ["Sharpe ratio", "Max Sharpe ratio", "Min-vol Sharpe"],
    definition:
      "Return above the risk-free rate per unit of volatility. Higher is better, but a ratio estimated from a few years of data has a wide margin of error.",
    method: "returns-and-risk",
  },
  {
    id: "sortino-ratio",
    term: "Sortino ratio",
    definition:
      "Like the Sharpe ratio, but it counts only downside swings (returns below a minimum acceptable return) as risk.",
    method: "returns-and-risk",
  },
  {
    id: "max-drawdown",
    term: "Maximum drawdown",
    labels: ["Max drawdown", "Median max drawdown"],
    definition: "The largest fall from a previous peak in value to a later low, as a share of the peak.",
    method: "returns-and-risk",
  },
  {
    id: "calmar-ratio",
    term: "Calmar ratio",
    definition: "CAGR divided by the size of the maximum drawdown: growth per unit of the worst loss.",
    method: "returns-and-risk",
  },
  {
    id: "var",
    term: "Value at Risk (VaR)",
    labels: ["Terminal VaR 95%"],
    definition:
      "A loss that is exceeded only rarely: 95% VaR is the loss not exceeded in 95% of cases (historical periods, or simulated paths in Monte Carlo). It says nothing about how bad the remaining 5% are.",
    method: "returns-and-risk",
  },
  {
    id: "cvar",
    term: "CVaR (conditional VaR, expected shortfall)",
    labels: ["CVaR 95%", "Highest-return CVaR", "Tail periods"],
    definition:
      "The average loss in the worst periods beyond the VaR, for example the worst 5%. It describes the bad tail rather than just its edge. In Ardentum it is historical and per data period (for example one day).",
    method: "optimisation",
  },
  {
    id: "correlation",
    term: "Correlation",
    definition:
      "How closely two assets move together, from -1 (always opposite) to +1 (always together). Combining assets with low correlation reduces risk; that is diversification.",
    method: "returns-and-risk",
  },
  {
    id: "covariance",
    term: "Covariance matrix",
    definition:
      "The table of every asset's variance and every pair's covariance (correlation times both volatilities). Portfolio risk is computed from it.",
    method: "estimation",
  },
  {
    id: "beta",
    term: "Beta to the portfolio",
    definition:
      "How much an asset tends to move when the portfolio moves by 1%. An asset with a high beta adds more risk to the portfolio than its own volatility suggests.",
    method: "optimisation",
  },
  {
    id: "risk-contribution",
    term: "Risk contribution",
    definition:
      "The share of portfolio volatility that comes from each holding (the Euler decomposition). The shares add up to 100% and depend on weights and correlations, not only on each asset's volatility.",
    method: "returns-and-risk",
  },
  {
    id: "diversification-ratio",
    term: "Diversification ratio",
    labels: ["Diversification ratio"],
    definition:
      "The weighted average of the holdings' volatilities divided by the portfolio's volatility. 1 means no diversification benefit; higher means correlations cancel more risk.",
    method: "returns-and-risk",
  },
  {
    id: "effective-number",
    term: "Effective number of assets",
    labels: ["Effective no. of assets"],
    definition:
      "One divided by the sum of squared weights: how many equally weighted holdings the portfolio's concentration is equivalent to.",
    method: "returns-and-risk",
  },
  {
    id: "risk-free-rate",
    term: "Risk-free rate",
    definition:
      "The return available without risk, such as a short-term government bill. Sharpe ratios measure return above it.",
    method: "returns-and-risk",
  },
  {
    id: "efficient-frontier",
    term: "Efficient frontier",
    definition:
      "The highest expected return available at each level of risk. Portfolios below it take more risk than they need for their return, on the model's estimates.",
    method: "optimisation",
  },
  {
    id: "minimum-variance",
    term: "Minimum-volatility portfolio",
    definition:
      "The least risky portfolio the constraints allow. It ignores expected returns, which makes it less sensitive to estimation error.",
    method: "optimisation",
  },
  {
    id: "tangency",
    term: "Maximum-Sharpe (tangency) portfolio",
    definition:
      "The portfolio with the highest expected Sharpe ratio, where a line from the risk-free rate touches the efficient frontier. It relies heavily on expected returns, the noisiest input.",
    method: "optimisation",
  },
  {
    id: "risk-parity",
    term: "Risk parity (equal risk contribution)",
    definition:
      "A portfolio in which every holding contributes the same share of risk. It uses no expected returns; low-risk assets get large weights.",
    method: "optimisation",
  },
  {
    id: "binding-constraint",
    term: "Binding constraint and shadow price",
    definition:
      "A limit the optimiser has pushed against, such as a maximum weight. Its shadow price is how much the objective would improve per unit of loosening the limit.",
    method: "optimisation",
  },
  {
    id: "kkt",
    term: "KKT (optimality) conditions",
    definition:
      "The mathematical conditions every optimal portfolio satisfies. Ardentum's reasons for holding or leaving out each asset are read from them, so each reason is a checkable fact about the solution.",
    method: "optimisation",
  },
  {
    id: "shrinkage",
    term: "Shrinkage estimators",
    definition:
      "Pulling noisy estimates toward a simpler target: Ledoit-Wolf for the covariance matrix, Bayes-Stein for expected returns. They trade a little bias for much less noise.",
    method: "estimation",
  },
  {
    id: "black-litterman",
    term: "Black-Litterman",
    definition:
      "Starts from the returns implied by market weights and blends in your own views with stated confidence, instead of using historical averages.",
    method: "estimation",
  },
  {
    id: "estimation-window",
    term: "Estimation window",
    definition: "The stretch of history used to estimate expected returns and risk. Results depend on it.",
    method: "estimation",
  },
  {
    id: "monte-carlo",
    term: "Monte Carlo simulation",
    labels: ["Median final value", "Probability of target"],
    definition:
      "Thousands of possible futures generated from the estimated returns, to show the range of outcomes rather than one number. A fixed seed makes it repeatable.",
    method: "simulation",
  },
  {
    id: "bootstrap",
    term: "Bootstrap",
    definition:
      "Simulating by resampling the actual historical returns, which keeps their fat tails. The block bootstrap resamples runs of consecutive periods to keep short-term patterns.",
    method: "simulation",
  },
  {
    id: "walk-forward",
    term: "Walk-forward backtest",
    definition:
      "Replaying history so that each decision uses only the data available at that date, then measuring what happened next. It avoids look-ahead bias.",
    method: "backtesting",
  },
  {
    id: "look-ahead",
    term: "Look-ahead bias",
    definition:
      "Using information in a test that was not available at the time, which makes results look better than anyone could have achieved.",
    method: "backtesting",
  },
  {
    id: "turnover",
    term: "Turnover and costs",
    labels: ["Turnover", "Cost drag"],
    definition:
      "Turnover is how much of the portfolio is traded at rebalances. Each trade costs a number of basis points (hundredths of a percent); the cost drag is the return lost to these costs.",
    method: "backtesting",
  },
  {
    id: "tracking-error",
    term: "Tracking error",
    labels: ["Tracking error (ex ante)", "Tracking error (in-sample)"],
    definition: "The volatility of the difference between a portfolio's return and a benchmark's return.",
    method: "returns-and-risk",
  },
  {
    id: "esg-score",
    term: "ESG score",
    labels: ["ESG score"],
    definition:
      "A 0 to 100 rating of environmental, social and governance practice. Ardentum uses only scores with a named source, averages them by weight, and never fills in a missing score.",
    method: "esg",
  },
  {
    id: "currency-hedging",
    term: "Currency hedging",
    definition:
      "Removing the effect of exchange-rate moves on foreign assets with a forward contract. The hedge earns or pays the interest-rate difference between the two currencies.",
    method: "data",
  },
];

const BY_LABEL = new Map(GLOSSARY.flatMap((e) => (e.labels ?? []).map((l) => [l, e.id] as const)));

/** The glossary anchor for a result label, if it has one. */
export function glossaryIdFor(label: string): string | undefined {
  return BY_LABEL.get(label);
}
