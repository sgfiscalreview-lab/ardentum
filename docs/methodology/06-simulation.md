# Monte Carlo simulation

How Ardentum simulates the range of future portfolio values, and what the simulation assumes.

## Portfolio dynamics

The portfolio is rebalanced to its target weights every data period (constant mix), so its one-period return is $r_{p,t} = w^\top r_t$ and wealth evolves as $W_{t} = W_{t-1}(1 + r_{p,t})$. Simulation runs at the data frequency (for daily data, 252 steps per year); values are recorded monthly for charts. Maximum drawdown is tracked on every step.

## Methods

**Parametric (lognormal).** Per-period gross returns are i.i.d. lognormal with the same mean and variance as the portfolio's *estimated* arithmetic moments, taken from the same annualised estimates the optimiser uses: $m = w^\top\mu/P$, $v = w^\top\Sigma w/P$. Moment matching gives

$$
\ln(1+r) \sim \mathcal N(a, s^2),\qquad s^2 = \ln\!\left(1 + \frac{v}{(1+m)^2}\right),\qquad a = \ln(1+m) - \tfrac{s^2}{2}.
$$

Then $\mathbb E[W_T] = W_0(1+m)^n$ and the median is $W_0 e^{na}$ exactly; both are verified statistically in tests. The model has thin tails and no volatility clustering.

**Historical bootstrap.** Portfolio returns $w^\top r_t$ from the history are resampled independently with replacement. This keeps the empirical distribution (fat tails, skew) and the cross-asset dependence on each date, but destroys serial dependence. For i.i.d. resampling $\mathbb E[W_T] = W_0(1+\bar r)^n$, which is tested.

**Stationary block bootstrap** (Politis & Romano, 1994). Blocks of consecutive historical returns with geometrically distributed lengths (mean $L$, default one month) are concatenated, wrapping around the sample. This additionally preserves short-range dependence such as volatility clustering (tested on an autocorrelated series).

## Reproducibility

All randomness comes from one PCG64 generator seeded with an explicit seed. The seed is shown with every result; the same inputs and seed produce bit-identical outputs. Leaving the seed empty draws a random one, which is still reported so the run can be reproduced.

## Outputs

Percentile paths (5th, 10th, 25th, 50th, 75th, 90th, 95th), mean path, sample paths, the distribution of final values, probability of loss and of reaching a target, VaR and CVaR of the terminal return, and percentiles of annualised growth and of maximum drawdown.

## Limits

To keep requests interactive, paths × simulated periods may not exceed 100 million (for example 10,000 daily paths over 39 years); the API returns a clear error beyond that.

## Limitations

- Parameters are treated as known; estimation error in $\mu$ and $\Sigma$ is not simulated, so the spread of outcomes is understated.
- History-based methods cannot produce scenarios worse than the worst periods in the sample.
- No contributions, withdrawals, fees, taxes or transaction costs.
- A simulation is a consequence of its assumptions, not a forecast.
