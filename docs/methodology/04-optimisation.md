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

All share the constraint set $\mathcal C$ below. Variance is written $\lVert F w\rVert_2^2$ with $F = \Lambda^{1/2}V^\top$ from the eigendecomposition $\Sigma = V\Lambda V^\top$, which is exact and numerically robust even for singular (positive semi-definite) matrices.

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

## Efficient frontier

The frontier is traced by solving the target-return problem on a grid from the minimum-volatility portfolio's return up to the maximum return attainable under $\mathcal C$ (a linear programme). The problem is compiled once with the target as a parameter and re-solved for each point. Without constraints other than full investment, the frontier is Merton's (1972) hyperbola

$$
\sigma^2(m) = \frac{A m^2 - 2Bm + C}{AC - B^2},\quad A=\mathbf 1^\top\Sigma^{-1}\mathbf 1,\ B=\mathbf 1^\top\Sigma^{-1}\mu,\ C=\mu^\top\Sigma^{-1}\mu,
$$

which Ardentum reproduces to within $10^{-5}$ relative error (automated test). The capital market line runs from $r_f$ through the maximum-Sharpe portfolio.

## Solving and verification

Problems are solved with CVXPY (Diamond & Boyd, 2016) using the Clarabel interior-point solver (Goulart & Chen, 2024), with SCS as a fallback. After solving, Ardentum:

1. removes round-off below $10^{-8}$, clips to bounds and renormalises;
2. **re-checks every constraint** (tolerance $10^{-6}$) — a violating solution raises an error instead of being shown;
3. computes diagnostics: which constraints bind, and their shadow prices (dual values) where they are interpretable.

Pre-checks catch common infeasibilities with a specific message (e.g. maximum weights that sum to less than 100%, a minimum ESG score above the best-scoring asset, a target return above the attainable maximum).

## Validation

The optimiser is tested against independent answers: closed-form global minimum-variance, tangency and utility portfolios; Merton's frontier; SciPy SLSQP with multiple starts; PyPortfolioOpt; brute-force grid search; and the Karush–Kuhn–Tucker optimality conditions.

## Explanations

Explanations are derived from optimality conditions, not generated text, so each is a checkable fact:

- **Minimum volatility.** Every held, unconstrained asset has the same marginal variance $(\Sigma w)_i$; an asset left out has a marginal variance at least as high — adding it would raise risk.
- **Maximum Sharpe.** Held, unconstrained assets satisfy $\mu_i - r_f = \beta_i(\mu_p - r_f)$ with $\beta_i = (\Sigma w)_i/(w^\top\Sigma w)$. An asset left out has an expected return below this *required return*: its return does not compensate for the risk it would add.
- Assets at their maximum weight would be held in larger size without the limit; binding constraints are listed with their shadow prices.

## Weight stability

Optional: the return history is resampled with replacement (bootstrap), inputs are re-estimated and the problem re-solved many times with a fixed seed. The 5th–95th percentile range of each weight shows how much the portfolio depends on estimation noise (in the spirit of Michaud, 1998). Wide ranges are a warning, not a failure.

## Limitations

Single-period model; returns summarised by mean and covariance only (no skewness, fat tails or regime changes); no transaction costs, taxes or liquidity limits inside the optimisation; estimates treated as known.
