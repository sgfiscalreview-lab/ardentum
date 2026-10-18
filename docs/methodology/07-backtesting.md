# Backtesting and attribution

How strategies are replayed through history without look-ahead bias, and how their performance is decomposed.

## Walk-forward procedure

Row $t$ of the return history is the return from the close of day $t-1$ to the close of day $t$.

1. **Rebalance dates** are the last trading day of each month, quarter, half-year or year.
2. At a rebalance date $t$, the strategy receives **only** the trailing estimation window $\{r_{t-L+1},\dots,r_t\}$ (information available at the close of $t$) as a copy, so it cannot reach later data.
3. It re-estimates $\mu$ and $\Sigma$ on that window and re-solves the optimisation problem.
4. New weights are traded at the close of $t$ and earn returns from $t+1$.
5. Between rebalances, weights drift with realised returns.
6. **Transaction costs** of $c$ basis points are charged on turnover $\sum_i |w_i^{\text{target}} - w_i^{\text{drifted}}|$ at each trade, including the initial purchase.

The first rebalance is the first scheduled date with a full estimation window. Performance is measured **only after it** (the evaluation period); earlier data is used solely for estimation. Both periods are shown with every result.

If the optimisation becomes infeasible at some date, the strategy keeps its drifted weights and the event is recorded with the reason.

## How look-ahead bias is ruled out

An automated test runs an optimised strategy, then replaces every return after a cut-off date with an implausibly large value and runs it again. All weights chosen on or before the cut-off, and all returns up to it, must be **bit-identical**; later decisions must change (showing the test has power). A second test asserts that the window handed to the strategy always ends exactly on the decision date.

Inputs that exist only as today's values cannot be used at past decisions. **Black-Litterman market-capitalisation prior weights** use, at each rebalance, the capitalisations of the latest month that had ended (the Ken French files give the number of firms and the average firm size for every month). A dataset with a single, current capitalisation per asset is refused for backtests with that prior, with a suggestion to use equal or custom prior weights. **ESG scores** are used point in time when every score has a date: each rebalance uses the latest score known by then (methodology 05, *Scores over time*). When a score has no date, or was not yet known at the first rebalance, a backtest with ESG constraints or a tilt applies today's scores at every rebalance and says so.

## Is the strategy better than the benchmark?

A higher Sharpe ratio over one history may be luck. The backtest tests whether the strategy's and the benchmark's Sharpe ratios are equal (Ledoit & Wolf, 2008, section 3.1). The difference of the two ratios is a function of the four moments $(\mu_a, \mu_b, g_a, g_b)$; its standard error comes from the delta method with a Newey-West long-run covariance of those moments, so the test allows for fat tails, autocorrelation and the correlation between the two return series, which the Jobson-Korkie test (with Memmel's correction) assumes away. The result is a two-sided p-value, stated in words: below 5%, a difference that large would rarely arise by chance; above it, this history cannot tell the two apart. Ledoit and Wolf prefer a quadratic-spectral kernel with prewhitening or a bootstrap; the Bartlett kernel is a simpler, standard choice. Automated tests check agreement with the Jobson-Korkie-Memmel test for independent normal returns and a rejection rate near 5% for equal true ratios with fat tails and autocorrelation.

On a short history that normal approximation can be poor. When the evaluation has at most 1,000 returns, the backtest also runs Ledoit and Wolf's studentized circular block bootstrap (2008, section 3.2). The paired returns are resampled $M = 999$ times in circular blocks of $b$ periods (Politis & Romano, 1992), with $b = \mathrm{round}(T^{1/3})$; each resample's difference $\hat\Delta^*$ is divided by its own standard error $s^*$, computed from the blocks, and the p-value is

$$
p = \frac{\#\{\,|\hat\Delta^* - \hat\Delta|/s^* \ge |\hat\Delta|/s\,\} + 1}{M + 1}.
$$

The seed is fixed (0 unless the request sets another) and shown with the result, so the same request gives the same p-value. Ledoit and Wolf choose $b$ by a calibration step; the cube-root rule is a simpler, standard choice. Automated tests check that with one-period blocks the standard error equals the HAC one without lags, that the bootstrap and HAC p-values agree on long histories, and a rejection rate near 5% for equal true ratios on short histories with fat tails and autocorrelation. Longer histories skip the bootstrap, and the result says so: there the test above is reliable.

## Performance attribution

**Contribution to return.** In period $t$, asset $i$ contributes $c_{t,i} = w_{t-1,i} r_{t,i}$ using start-of-period weights; contributions sum to the period's gross return. Transaction costs appear as their own line.

**Linking over time** (Cariño, 1999). Arithmetic contributions do not add up to a compounded return. Each period's effects are scaled by $k_t/K$ with

$$
k_t = \frac{\ln(1+R_t)}{R_t},\qquad K = \frac{\ln(1+R)}{R},
$$

($R$ the compounded total return), after which the linked contributions sum **exactly** to the total return. For active returns against a benchmark $B$, $k_t = \frac{\ln(1+R_t)-\ln(1+B_t)}{R_t-B_t}$ and $K$ analogously.

**Sector attribution** (Brinson & Fachler, 1985) against the equal-weight benchmark, per period and sector $j$:

$$
\text{allocation}_j = (w^p_j - w^b_j)(r^b_j - R^b),\quad
\text{selection}_j = w^b_j(r^p_j - r^b_j),\quad
\text{interaction}_j = (w^p_j - w^b_j)(r^p_j - r^b_j),
$$

which sum over sectors to $R^p - R^b$; effects are Cariño-linked across periods. When a sector is absent on one side, its sector return is set equal to the other side's, the standard convention that keeps the identity exact. All identities are automated tests.

## Known limitations and biases

- **Survivorship bias.** The asset list is chosen today; assets that failed or were delisted are absent, which can flatter results.
- **Execution.** Trades are assumed at the closing price used for the decision; costs are linear; no market impact, borrowing costs or cash drag.
- **Backtest overfitting.** Trying many configurations and keeping the best one inflates results (Bailey et al., 2014). Treat a single good backtest with scepticism and prefer robust, simple configurations.
- **Synthetic data.** Backtests on the demo universe illustrate the method only.
