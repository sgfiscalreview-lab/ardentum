# Optimisation

The mean–variance problems Ardentum solves, how they are solved exactly, and how every solution is checked and explained.

## Objectives

Let $w$ be portfolio weights, $\mu$ annualised expected returns, $\Sigma$ the annualised covariance and $r_f$ the risk-free rate on the same scale (Markowitz, 1952).

| Objective | Problem |
|---|---|
| Minimum volatility | $\min_w\ w^\top\Sigma w$ |
| Maximum Sharpe ratio | $\max_w\ (\mu^\top w - r_f)/\sqrt{w^\top\Sigma w}$ |
| Target return | $\min_w\ w^\top\Sigma w\ \text{ s.t. }\ \mu^\top w \ge m$ |
| Target volatility | $\max_w\ \mu^\top w\ \text{ s.t. }\ \sqrt{w^\top\Sigma w} \le \sigma^*$ |
| Maximum utility | $\max_w\ \mu^\top w - \tfrac{\gamma}{2}w^\top\Sigma w$ |
| Minimum CVaR | $\min_w\ \mathrm{CVaR}_\beta(-R w)$, optionally s.t. $\mu^\top w \ge m$ (see below) |
| Risk parity | $w_i(\Sigma w)_i = \tfrac{1}{n}\,w^\top\Sigma w$ for every held asset (see below) |

All except risk parity share the constraint set $\mathcal C$ below. Variance is written $\lVert F w\rVert_2^2$ with $F = \Lambda^{1/2}V^\top$ from the eigendecomposition $\Sigma = V\Lambda V^\top$, which is exact and numerically robust even for singular (positive semi-definite) matrices.

## Constraints

| Constraint | Formulation |
|---|---|
| Full investment | $\mathbf 1^\top w = 1$ |
| Position bounds | $\ell_i \le w_i \le u_i$ (global or per asset) |
| Exclusions (assets or sectors) | $w_i = 0$ |
| Sector limits | $\underline s_k \le \sum_{i\in S_k} w_i \le \overline s_k$ |
| Minimum ESG score | $s^\top w \ge s_{\min}$ (long-only) |
| Gross exposure | $\lVert w\rVert_1 \le L$ |
| Tracking error | $\lVert F(w - b)\rVert_2 \le TE_{\max}$ |

All are linear or second-order-cone constraints, so every problem is convex and has a global optimum that interior-point solvers find reliably.

## Maximum Sharpe ratio: an exact convex reformulation

The Sharpe ratio is not concave, but with the Charnes–Cooper change of variables $y = \kappa w$, $\kappa > 0$ (Charnes & Cooper, 1962; Cornuéjols & Tütüncü, 2007) the problem becomes

$$
\min_{y,\kappa}\ y^\top\Sigma y\quad\text{s.t.}\quad (\mu - r_f\mathbf 1)^\top y = 1,\quad A y \le b\,\kappa,\quad \kappa \ge 0,
$$

a convex quadratic programme whose solution gives $w^\star = y^\star/\kappa^\star$. Every linear constraint is homogenised the same way; the tracking-error cone becomes $\lVert F(y - b\kappa)\rVert \le TE_{\max}\kappa$.

The reformulation requires a feasible portfolio with expected return above $r_f$. Ardentum first solves $\max \mu^\top w - r_f$ over $\mathcal C$; if that is not positive, the maximum-Sharpe portfolio is **undefined** and reported as such rather than approximated.

## Minimum CVaR: a linear programme over history

Volatility treats gains and losses alike and assumes nothing about tails. **Conditional value at risk** (CVaR, expected shortfall) at level $\beta$ is the average loss in the worst $1-\beta$ of outcomes. Using the $T$ historical per-period return vectors $r_t$ of the estimation window as equally likely scenarios, Rockafellar and Uryasev (2000) show

$$\mathrm{CVaR}_\beta(w) = \min_{\alpha}\ \alpha + \frac{1}{(1-\beta)T}\sum_{t=1}^{T}\big(-r_t^\top w - \alpha\big)^+ ,$$

with the minimising $\alpha$ equal to the value at risk. Introducing $u_t \ge 0$, $u_t \ge -r_t^\top w - \alpha$ turns minimum CVaR into a linear programme (plus any second-order-cone constraints such as tracking error), solved jointly over $(w,\alpha,u)$. The result keeps the empirical distribution's fat tails and asymmetry.

CVaR here is **per data period** (e.g. one-day CVaR for daily data) and is **historical**: it cannot anticipate losses worse than the window contains. At least $1/(1-\beta)$ observations are required. Every optimisation result also reports the historical one-period VaR and CVaR of its weights at the chosen level.

Validation: the optimum equals an independent solution of the same programme by SciPy's HiGHS solver, is no worse than a brute-force grid over the simplex, and the reported CVaR equals the closed form (mean of the $k$ worst losses when $(1-\beta)T=k$).

## Risk parity: equal risk contributions

The Euler decomposition splits portfolio variance into one contribution per asset, $w_i(\Sigma w)_i$, which sum to $w^\top\Sigma w$. A **risk parity** (equal risk contribution) portfolio makes these contributions equal, so each of the $n$ holdings carries $1/n$ of the risk (Maillard, Roncalli and Teiletche, 2010). It uses no expected returns, the noisiest input, which is its appeal; the price is that low-risk assets can need large weights.

The weights solve Spinu's (2013) strictly convex problem

$$\min_{y>0}\ \tfrac12\,y^\top\Sigma y - \tfrac1n\sum_{i=1}^n \log y_i, \qquad w = y\,/\,\textstyle\sum_i y_i .$$

Its optimality condition $(\Sigma y)_i = 1/(n\,y_i)$ says exactly that every $y_i(\Sigma y)_i$ equals $1/n$, and strict convexity makes the solution unique when $\Sigma$ is positive definite. CVXPY solves it (an exponential-cone programme), and a few Newton steps on the optimality condition make the shares equal to machine precision. Excluded assets are left out; short positions are not allowed.

The weights are set by the risks alone, so other constraints (weight and sector limits, a minimum ESG score, a tracking-error limit) are checked afterwards. A broken one is reported with the weight that breaks it, for example "GOVB.SYN gets 45.1%, above its maximum of 30.0%", rather than replaced by a portfolio that is no longer risk parity.

Validation: two assets give inverse-volatility weights for any correlation, and so does any number of assets with one common correlation (closed forms); every risk contribution equals $1/n$ to $10^{-10}$; the weights match an independent solution of the same problem by SciPy's quasi-Newton method; and the volatility lies between those of the minimum-variance and equally weighted portfolios, as Maillard, Roncalli and Teiletche prove.

## Efficient frontier

The frontier is traced by solving the target-return problem on a grid from the minimum-volatility portfolio's return up to the maximum return attainable under $\mathcal C$ (a linear programme). The problem is compiled once with the target as a parameter and re-solved for each point. Without constraints other than full investment, the frontier is Merton's (1972) hyperbola

$$
\sigma^2(m) = \frac{A m^2 - 2Bm + C}{AC - B^2},\quad A=\mathbf 1^\top\Sigma^{-1}\mathbf 1,\ B=\mathbf 1^\top\Sigma^{-1}\mu,\ C=\mu^\top\Sigma^{-1}\mu,
$$

which Ardentum reproduces to within $10^{-5}$ relative error (automated test). The capital market line runs from $r_f$ through the maximum-Sharpe portfolio.

## Mean-CVaR efficient frontier

Replacing variance by historical CVaR gives the mean-CVaR frontier (Rockafellar and Uryasev 2002; Krokhmal, Palmquist and Uryasev 2002). For each target $m$ on a grid from the minimum-CVaR portfolio's expected return to the highest attainable return,

$$
\min_{w,\alpha,u}\ \alpha + \frac{1}{(1-\beta)T}\sum_{t=1}^{T} u_t \quad\text{s.t.}\quad u_t \ge -r_t^\top w - \alpha,\ u_t \ge 0,\ \mu^\top w \ge m,\ w \in \mathcal C .
$$

The optimal value is a convex, nondecreasing function of $m$, so only the efficient branch above the minimum-CVaR portfolio is shown. As with minimum CVaR, the tail measure is per data period and historical; expected returns are the same annualised estimates used elsewhere. The page also measures the mean-variance frontier's portfolios by the same CVaR: for elliptical (e.g. normal) returns the two frontiers coincide, so a gap between them is a picture of the fat tails and skew that volatility ignores.

Validation: every point equals an independent solution of the same linear programme by SciPy's HiGHS solver; no portfolio on a brute-force grid over the simplex with at least the same expected return has lower CVaR; each point's reported CVaR and VaR equal the closed-form historical values of its weights; returns increase and CVaR never decreases along the frontier; and no mean-variance portfolio has lower CVaR than the mean-CVaR frontier at or below its return.

## Solving and verification

Problems are solved with CVXPY (Diamond & Boyd, 2016) using the Clarabel interior-point solver (Goulart & Chen, 2024), with SCS as a fallback. After solving, Ardentum:

1. removes round-off below $10^{-8}$, clips to bounds and renormalises;
2. **re-checks every constraint** (tolerance $10^{-6}$); a violating solution raises an error and is never shown;
3. computes diagnostics: which constraints bind, and their shadow prices (dual values) where they are interpretable.

Pre-checks catch common infeasibilities with a specific message (e.g. maximum weights that sum to less than 100%, a minimum ESG score above the best-scoring asset, a target return above the attainable maximum).

## Validation

The optimiser is tested against independent answers: closed-form global minimum-variance, tangency and utility portfolios; Merton's frontier; SciPy SLSQP with multiple starts; PyPortfolioOpt; brute-force grid search; and the Karush–Kuhn–Tucker optimality conditions.

## Explanations

Explanations are derived from the optimality conditions, so each one is a checkable fact:

- **Minimum volatility.** Every held, unconstrained asset has the same marginal variance $(\Sigma w)_i$; an asset left out has a marginal variance at least as high, so adding it would raise risk.
- **Maximum Sharpe.** Held, unconstrained assets satisfy $\mu_i - r_f = \beta_i(\mu_p - r_f)$ with $\beta_i = (\Sigma w)_i/(w^\top\Sigma w)$. An asset left out has an expected return below this *required return*: its return does not compensate for the risk it would add.
- Assets at their maximum weight would be held in larger size without the limit; binding constraints are listed with their shadow prices.

## Weight stability

Optional: the return history is resampled with replacement (bootstrap), inputs are re-estimated and the problem re-solved many times with a fixed seed. The 5th–95th percentile range of each weight shows how much the portfolio depends on estimation noise (in the spirit of Michaud, 1998). Wide ranges are a warning sign about the inputs.

## Limitations

Single-period model; returns summarised by mean and covariance only (no skewness, fat tails or regime changes); no transaction costs, taxes or liquidity limits inside the optimisation; estimates treated as known.
