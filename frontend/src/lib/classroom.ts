/**
 * The classroom kit: a 45-minute lesson on diversification, estimation error and risk,
 * run on the synthetic demo data with no sign-in. The numbers students should see are in
 * classroom-answers.json, computed by the API and checked by a backend test.
 */
import answers from "./classroom-answers.json";

export const ANSWERS = answers;

export interface Exercise {
  title: string;
  page: string;
  idea: string;
  steps: string[];
  questions: string[];
}

export const EXERCISES: Exercise[] = [
  {
    title: "Why spread your money?",
    page: "/app/analytics",
    idea: "Combining assets that do not move together lowers risk, sometimes below that of the safest single asset.",
    steps: [
      "Open the Analytics page and choose Compute analytics.",
      "In Asset statistics, find the asset with the lowest volatility.",
      "In the correlation matrix, find the pair of assets that move most in opposite directions (the most negative number).",
      "Open the Optimise page, set Objective to Minimum volatility and choose Optimise.",
    ],
    questions: [
      "Which single asset has the lowest volatility, and what is it?",
      "Which two assets have the most negative correlation?",
      "What volatility does the minimum-volatility portfolio reach? Is it higher or lower than the safest single asset? Explain why.",
    ],
  },
  {
    title: "Does the optimiser keep its promise?",
    page: "/app/optimise",
    idea: "An optimiser's result depends on estimates from the past. Tested on data it has not seen, it can do worse than simply splitting money equally.",
    steps: [
      "On the Optimise page, set Objective back to Maximum Sharpe ratio and choose Optimise.",
      "Note the Sharpe ratio and read the box headed Read before relying on this result.",
      "Choose Use as working portfolio.",
      "Open the Backtest page and choose Run backtest with the default settings. Each month it re-optimises using only the previous three years of data.",
    ],
    questions: [
      "What Sharpe ratio did the optimiser promise?",
      "What Sharpe ratio did the backtested strategy actually achieve, and what did the equal-weight benchmark achieve?",
      "Give one reason why the result is so different from the promise.",
    ],
  },
  {
    title: "How sure can we be?",
    page: "/app/simulate",
    idea: "The future is a range, not a number. Over longer horizons the range of outcomes widens, but the chance of ending with a loss usually falls.",
    steps: [
      "Open the Monte Carlo page. Keep the working portfolio and the other settings.",
      "Set Horizon (years) to 1 and choose Simulate. Note the probability of loss and the range of final values.",
      "Set Horizon (years) to 10 and choose Simulate again.",
    ],
    questions: [
      "After 1 year, what is the probability of a loss on $10,000?",
      "After 10 years, what is it now? What are the 5th and 95th percentile final values?",
      "Why does the range get wider while the chance of a loss gets smaller?",
    ],
  },
];

export const EXTENSION = {
  title: "Extension: what does an ESG requirement cost?",
  page: "/app/esg",
  steps: [
    "Open the ESG impact page. In Constraints, open ESG, set Minimum portfolio ESG score to 70 and tick Exclude assets without an ESG score.",
    "Choose Measure ESG impact.",
  ],
  questions: ["How do the Sharpe ratio and the volatility change? Is the cost worth it? There is no single right answer."],
};

export const EXIT_QUESTION =
  "In one sentence: why might a simple equal split beat a carefully optimised portfolio?";
