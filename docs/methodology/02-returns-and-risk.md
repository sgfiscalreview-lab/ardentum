# Returns and risk

Definitions of every realised (historical) statistic, with the exact conventions used.

## Returns

For adjusted closing prices $P_t$ (split- and dividend-adjusted, so price returns are total returns):

$$
r_t = \frac{P_t}{P_{t-1}} - 1 \qquad\text{(simple, arithmetic)}\qquad
x_t = \ln\frac{P_t}{P_{t-1}} = \ln(1+r_t) \qquad\text{(logarithmic)}
$$

The first date has no return and is dropped. It is never filled with zero, because a fabricated zero would bias means and volatilities downwards. Log returns add over time; simple returns aggregate across assets ($r_{p,t} = \sum_i w_i r_{i,t}$), which is why portfolio calculations use simple returns.

## Annualisation

With $P$ periods per year (252, 52 or 12) and $n$ observations:

| Quantity | Formula |
|---|---|
| Arithmetic annual return | $\bar r_A = P\cdot\frac{1}{n}\sum_t r_t$ |
| CAGR (geometric) | $\left(\prod_t (1+r_t)\right)^{P/n} - 1$ |
| Annualised volatility | $\sigma_A = \sqrt{P}\cdot s(r)$, sample standard deviation with $n-1$ |
| Annualised covariance | $\Sigma_A = P\cdot \widehat{\mathrm{Cov}}(r)$ |

The square-root-of-time rule assumes serially uncorrelated returns; with autocorrelation it misstates annual volatility (Lo, 2002).

## Risk-adjusted performance

**Sharpe ratio** (Sharpe, 1966; 1994), using an effective annual risk-free rate $R_f$ converted to a per-period rate $r_f = (1+R_f)^{1/P}-1$:

$$
SR = \sqrt{P}\,\frac{\overline{r - r_f}}{s(r - r_f)}
$$

It is reported as *undefined* (with the reason) when volatility is zero.

**Sharpe ratio interval.** A Sharpe ratio estimated from a few years of returns is uncertain, often by more than its size, so every one comes with a 95% confidence interval $SR \pm 1.96\,SE$. Write $x_t$ for the excess returns, $\mu = ar x$, $g = \overline{x^2}$ and $v = g - \mu^2$, so the per-period ratio is $\mu/\sqrt{v}$. By the delta method

$$
SE^2 = rac{P}{T}\,
abla^	op \Psi\, 
abla,\qquad 
abla = \left(rac{g}{v^{3/2}},\; -rac{\mu}{2v^{3/2}}
ight),
$$

where $\Psi$ is the Newey-West (Bartlett kernel) long-run covariance of $(x_t - \mu,\; x_t^2 - g)$ with $\lfloor 4(T/100)^{2/9}
floor$ lags. For independent normal returns this reduces to Lo's (2002) $\sqrt{(1 + SR^2/2)/T}$ per period; without lags it is Mertens' (2002) formula, which adds skewness and kurtosis; with lags it also allows for autocorrelation, which Lo shows can change the standard error considerably. Both reductions, and the interval's coverage in simulations, are automated tests. Fewer than 24 returns give no interval (n/a, with the reason).

**Sortino ratio** (Sortino & Price, 1994) with minimum acceptable return $m$ (per period), target downside deviation over **all** observations:

$$
DD = \sqrt{\tfrac{1}{n}\textstyle\sum_t \min(r_t - m, 0)^2}, \qquad
\text{Sortino} = \sqrt{P}\,\frac{\bar r - m}{DD}
$$

Undefined when no return falls below $m$.

**Maximum drawdown** on the wealth index $W_0 = 1$, $W_t = \prod_{s\le t}(1+r_s)$:

$$
\text{MDD} = \min_t \left(\frac{W_t}{\max_{s\le t} W_s} - 1\right)
$$

The initial value $W_0$ is included, so a loss in the first period counts as a drawdown. The **Calmar ratio** is $\text{CAGR}/|\text{MDD}|$.

## Relationship to a benchmark

$$
\beta = \frac{\mathrm{Cov}(r_a, r_m)}{\mathrm{Var}(r_m)},\qquad
TE = \sqrt{P}\,s(r_p - r_b),\qquad
IR = \sqrt{P}\,\frac{\overline{r_p - r_b}}{s(r_p - r_b)}
$$

## Tail risk

Historical one-period **Value at Risk** at confidence $c$ is the loss not exceeded in a fraction $c$ of observations, $\text{VaR}_c = -q_{1-c}(r)$ (empirical quantile, linear interpolation). **Conditional VaR** (expected shortfall) is the mean loss in that tail, $\text{CVaR}_c = -\mathbb{E}[r \mid r \le q_{1-c}]$, a coherent risk measure (Artzner et al., 1999). Both are reported as positive fractions and refer to the data frequency (e.g. one day).

## Portfolio risk decomposition

With weights $w$ and covariance $\Sigma$, portfolio volatility $\sigma_p = \sqrt{w^\top\Sigma w}$ is homogeneous of degree one, so by Euler's theorem

$$
\sigma_p = \sum_i w_i \frac{\partial \sigma_p}{\partial w_i} = \sum_i \underbrace{\frac{w_i (\Sigma w)_i}{\sigma_p}}_{\text{risk contribution } RC_i}
$$

Risk contributions sum exactly to $\sigma_p$ (Litterman, 1996). When $\sigma_p = 0$ they are undefined and shown as n/a with the reason, never as zeros. Ardentum also reports the **diversification ratio** $\sum_i w_i\sigma_i / \sigma_p$ (Choueifaty & Coignard, 2008) and the **effective number of assets** $1/\sum_i w_i^2$; with short positions it uses the gross weights, $1/\sum_i \left(|w_i| / \sum_j |w_j|\right)^2$, so shorts count as positions.

## Correlation

Pearson correlations of returns. An asset whose returns never change over the window (cash at a fixed price, for example) has no variance, so its correlations are undefined: its row and column are n/a with a note naming it, and every other pair keeps its correlation.

## Consistency check

Because expected returns and covariances are annualised linearly and the risk-free rate is expressed as $P\cdot r_f$ on the same scale, the ex-ante Sharpe ratio of a portfolio computed from sample estimates equals its ex-post Sharpe ratio on the same sample exactly. This identity is an automated test.
