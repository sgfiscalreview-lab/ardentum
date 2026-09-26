# Estimation

How expected returns and covariances are estimated — and why the estimates deserve scepticism.

Mean–variance optimisation needs two inputs: a vector of expected returns $\mu$ and a covariance matrix $\Sigma$. Neither is observable. Ardentum estimates both from a user-chosen historical window and records the estimator, window, number of observations and shrinkage intensity with every result.

## Estimation error is the central problem

The standard error of an annualised mean return is roughly $\sigma_A/\sqrt{T_{\text{years}}}$. For an asset with 20% volatility and ten years of data that is about 6.3 percentage points — larger than most differences in expected returns between assets. Optimisers amplify these errors: they overweight assets whose returns were overestimated (Best & Grauer, 1991; Chopra & Ziemba, 1993; Michaud, 1998). Ardentum responds by offering shrinkage estimators, constraints, objectives that ignore expected returns (minimum volatility), and a weight-stability analysis.

## Expected returns

**Historical mean.** $\hat\mu = P\cdot\bar r$, the annualised arithmetic sample mean.

**Bayes–Stein shrinkage** (Jorion, 1986). Sample means are shrunk toward the mean return of the global minimum-variance portfolio:

$$
\hat\mu_{BS} = (1-\phi)\,\hat\mu + \phi\,\mu_0\mathbf 1,\qquad
\mu_0 = \frac{\mathbf 1^\top \tilde\Sigma^{-1}\hat\mu}{\mathbf 1^\top\tilde\Sigma^{-1}\mathbf 1},\qquad
\phi = \frac{N+2}{(N+2) + T\,(\hat\mu-\mu_0\mathbf 1)^\top\tilde\Sigma^{-1}(\hat\mu-\mu_0\mathbf 1)}
$$

with $\tilde\Sigma = \frac{T-1}{T-N-2}S$. The intensity $\phi\in(0,1]$ is data-driven: when sample means barely differ relative to their noise, $\phi\to1$. Requires $T > N+2$.

## Covariance

**Sample covariance** (unbiased, $T-1$). Singular when $T\le N$ and noisy when $T/N$ is small; Ardentum refuses to use it when it is singular.

**Ledoit–Wolf, scaled-identity target** (Ledoit & Wolf, 2004a). The default:

$$
\hat\Sigma_{LW} = \delta\,\bar\sigma^2 I + (1-\delta)S,\qquad \bar\sigma^2 = \operatorname{tr}(S)/N
$$

with the asymptotically optimal intensity $\delta$ estimated from the data. The result is always positive definite and well-conditioned. Ardentum's implementation matches scikit-learn's to machine precision (automated test).

**Ledoit–Wolf, constant-correlation target** (Ledoit & Wolf, 2004b). Shrinks toward a matrix with the sample variances and the average pairwise correlation $\bar\rho$:

$$
F_{ii} = s_{ii},\quad F_{ij} = \bar\rho\sqrt{s_{ii}s_{jj}},\qquad \hat\Sigma = \delta F + (1-\delta)S,\qquad \delta = \max\!\left(0,\min\!\left(1,\tfrac{\hat\kappa}{T}\right)\right),\ \hat\kappa = \tfrac{\hat\pi-\hat\rho}{\hat\gamma}
$$

where $\hat\pi,\hat\rho,\hat\gamma$ follow the paper's appendix. It suits equity universes, where correlations are broadly similar. Verified against a direct loop implementation of the paper's formulas.

Both Ledoit–Wolf estimators use the $1/T$ normalisation of the original papers.

## Choosing the window and frequency

- Longer windows reduce sampling error but may mix different regimes.
- Daily data provides more observations for covariance estimation; expected-return precision depends on the calendar length of the window, not the number of observations.
- Monthly data is less affected by asynchronous closing prices across markets.

## What is reported

Every optimisation, frontier, simulation and comparison lists: window start and end, number of observations, frequency, mean and covariance estimators and their shrinkage intensities, and the risk-free rate.
