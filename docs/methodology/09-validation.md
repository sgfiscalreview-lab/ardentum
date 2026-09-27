# How calculations are validated

Every financial calculation in Ardentum is covered by automated tests with independently known answers. This page summarises what is tested and against what.

| Area | Verified against |
|---|---|
| Returns, CAGR, annualisation | Hand-computed examples (e.g. 12 monthly returns of 1% give a CAGR of $1.01^{12}-1$; doubling over 24 months gives $\sqrt2-1$) |
| Volatility, Sharpe, Sortino, drawdown, Calmar, VaR/CVaR, beta, tracking error | Closed-form examples; brute-force drawdown; OLS slope for beta |
| Consistency of conventions | Ex-ante Sharpe from sample estimates equals ex-post Sharpe on the same data |
| Risk decomposition | Contributions sum to volatility; marginal contributions equal numerical gradients (property-based tests) |
| Ledoit–Wolf (identity) | scikit-learn, to machine precision |
| Ledoit–Wolf (constant correlation) | Direct loop implementation of the paper's formulas; PyPortfolioOpt within $O(1/T)$ |
| Bayes–Stein | Explicit formula; limiting cases (equal means give full shrinkage) |
| Minimum variance, tangency, utility portfolios | Closed-form solutions with unrestricted weights |
| Efficient frontier | Merton's (1972) hyperbola; monotonicity and convexity; max-Sharpe dominates every frontier point |
| Long-only optimisation | SciPy SLSQP (multi-start), PyPortfolioOpt, brute-force grid search, KKT conditions |
| Constraints | Each constraint's binding behaviour; infeasibility detection with specific messages |
| ESG | Minimum-score satisfaction; Sharpe cannot improve under a constraint; tilt raises ESG score monotonically; ESG-Sharpe frontier non-increasing |
| Monte Carlo | Analytic lognormal mean and median; i.i.d.-bootstrap expectation; autocorrelation preserved by the block bootstrap and destroyed by the i.i.d. bootstrap; bit-identical reproducibility with a seed |
| Backtesting | Manual replication of rebalanced portfolios; transaction-cost accounting; **look-ahead invariance**; strategy only sees the trailing window |
| Attribution | Linked contributions sum to the compounded return; Brinson–Fachler effects sum to the active return |
| API | Every endpoint end-to-end on SQLite and PostgreSQL, including authentication, ownership isolation and error messages |

The test suite runs on every change in continuous integration. A calculation is not considered valid until it has such a test.
