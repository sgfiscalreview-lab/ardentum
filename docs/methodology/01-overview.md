# Methodology overview

How Ardentum turns price histories into portfolios, and what every number on screen means.

Ardentum follows one pipeline. Each stage has its own document:

1. **Data.** Prices are loaded from a named source, aligned and quality-checked ([Data](/research/data)).
2. **Returns and risk.** Prices become returns; realised statistics are measured ([Returns and risk](/research/returns-and-risk)).
3. **Estimation.** Expected returns and the covariance matrix are *estimated* from a historical window ([Estimation](/research/estimation)).
4. **Optimisation.** A convex mean–variance problem is solved under explicit constraints, verified and explained ([Optimisation](/research/optimisation)).
5. **ESG.** ESG scores enter the optimisation as constraints or a preference; their cost is measured ([ESG methodology](/research/esg)).
6. **Simulation.** The range of future outcomes is simulated with a reproducible seed ([Monte Carlo](/research/simulation)).
7. **Backtesting.** Strategies are replayed through history without look-ahead, and performance is attributed ([Backtesting](/research/backtesting)).

## Observed values versus estimates

| Kind | Examples | How to read it |
|---|---|---|
| **Observed (realised)** | CAGR, realised volatility, maximum drawdown, backtest returns | What actually happened in the sample. Past performance does not predict future results. |
| **Estimated (ex ante)** | expected return, expected volatility, expected Sharpe ratio, efficient frontier | A statistical estimate from a finite sample, with substantial error, especially for expected returns. |
| **Simulated** | Monte Carlo percentiles, probability of loss | A consequence of the simulation model and its assumptions. It makes no forecast. |

## Conventions

- Rates, weights and returns are decimal fractions (0.05 = 5%).
- Annualisation uses 252 trading days, 52 weeks or 12 months per year.
- "Expected return" in optimisation is the **arithmetic** annual mean; "CAGR" is the **geometric** growth rate. The first exceeds the second by roughly $\sigma^2/2$.
- The risk-free rate is an effective annual rate chosen by the user (optionally filled from a public T-bill series; see Data).
- Results are in one currency; mixed-currency universes are converted unhedged at ECB reference rates.
- Every result lists its estimation window, estimators and data source.

## What Ardentum will not do

- Invent data: demo assets are fictional and labelled **synthetic**; ESG scores always carry their source; missing ESG scores are never imputed.
- Approximate silently: an infeasible problem or an undefined metric is reported with the reason.
- Present in-sample results as out-of-sample: comparisons on the estimation window carry an explicit warning.

Ardentum is an analytical tool for education and research. It does not give investment advice.
