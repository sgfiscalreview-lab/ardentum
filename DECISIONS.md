# Ardentum — Decision Log

Each entry: context, decision, consequences. Decisions marked **(founder)** need
founder confirmation because they involve licensing, cost or legal matters.

## D-001 Monorepo with separate backend and frontend
Backend (`backend/`, Python/FastAPI) and frontend (`frontend/`, Next.js) live in one
repository so that API contracts, tests and docs change together. Types flow from the
backend OpenAPI schema into the frontend.

## D-002 Python 3.12, uv, strict typing
`uv` for reproducible environments (`uv.lock`), ruff for lint/format, mypy `--strict`.
CVXPY/SciPy are treated as untyped (`follow_imports=skip`).

## D-003 CVXPY with Clarabel (fallback SCS)
Clarabel is an interior-point conic solver bundled with CVXPY that handles the QP/SOCP
problems we need (quadratic objective, SOC tracking-error/volatility constraints).
Every solution is independently verified against all constraints after solving;
violations raise `SolverError` rather than returning a wrong portfolio.

## D-004 Market data: pluggable providers; Tiingo adapter implemented **(founder)**
No market-data host is reachable from the development environment, and every
provider has licensing terms. We implemented: a synthetic demo universe (always
available), CSV upload (user-supplied data), and a Tiingo adapter (adjusted closes)
tested against recorded response shapes. Tiingo's free tier is licensed for personal
use; **commercial use requires a paid Tiingo plan or another licensed vendor** —
founder decision required before public launch. FRED (public domain) is used for the
risk-free rate when a key is configured.

## D-005 Synthetic demo data, clearly labelled
To avoid fake data masquerading as real, demo assets are fictional issuers with a
`.SYN` ticker suffix, names suffixed "(synthetic)", provenance `is_synthetic=true`,
and ESG scores explicitly "not from any ESG rating provider". The UI shows a
persistent synthetic-data badge.

## D-006 Annualisation conventions
252 trading days, 52 weeks, 12 months. Expected returns and covariances are annualised
linearly (×P). The risk-free rate is an effective annual rate converted geometrically
to a per-period rate; for ex-ante excess returns it is re-expressed as
`P·((1+rf)^(1/P)−1)` so that ex-ante and ex-post Sharpe ratios agree exactly on the
same sample (tested). CAGR is geometric; "expected return" in optimisation is arithmetic.

## D-007 Default covariance estimator: Ledoit–Wolf (identity target)
Sample covariance is noisy and singular when T ≤ N. Ledoit–Wolf (2004) is the default;
sample and constant-correlation shrinkage are available. LW uses the papers' 1/T
normalisation (documented).

## D-008 Max-Sharpe via homogenisation
Max-Sharpe is solved exactly as a convex QP after the Charnes–Cooper transformation.
When no feasible portfolio has an expected return above the risk-free rate, the
maximum-Sharpe portfolio is reported as undefined (explicit error), never approximated.

## D-009 ESG methodology
* Scores on 0–100 (higher = better), provenance required (source, as-of date).
* Minimum portfolio score is a linear constraint (value-weighted average).
* Sector exclusions and asset exclusions fix weights at zero.
* ESG preference ("tilt") adds `τ·z` to expected returns in return-seeking objectives
  only (Pedersen, Fitzgibbons & Pomorski 2021); min-vol/target-return are unaffected
  and warn. Reported returns are never ESG-adjusted.
* ESG is restricted to long-only portfolios (a short book makes the weighted score meaningless).
* Missing scores are never imputed: the user must exclude unscored assets explicitly.
* ESG impact compares against a baseline with the same objective and non-ESG constraints;
  "ESG settings" = min score, tilt, sector exclusions, exclusion of unscored assets.

## D-010 Backtest timing
Decisions at the close of rebalance date t use returns ≤ t; new weights earn returns from
t+1. Costs are linear in turnover (initial purchase counts). The strategy receives only a
copy of the trailing window. Invariance of past decisions to future data is tested.

## D-011 Data alignment
Common window starts at the latest first-valid date; gaps ≤ 3 observations are forward
filled and reported; longer gaps are errors. No back-filling, no interpolation.

## D-012 Monte Carlo
Constant-mix portfolio simulated at the data frequency. Parametric = lognormal moment-matched
to the same annualised estimates the optimiser used; bootstrap = i.i.d. or stationary block
(Politis–Romano). Seed is explicit and echoed in the response; same seed ⇒ identical output.

## D-013 Authentication: Supabase Auth; backend verifies JWTs **(founder: Supabase project)**
The backend never stores passwords. A dev-only login mode makes local development and
E2E tests self-contained; settings validation forbids it in production.

## D-014 Uploaded datasets stored as gzip CSV blobs
Simpler and faster than a row per price for ≤5 MB uploads; parsed and cached (LRU) on use.

## D-015 Explanations are deterministic
Explanations derive from KKT conditions, risk decomposition and constraint diagnostics —
not generated text — so every statement is a checkable fact about the solution.

## D-016 Comparison page replays fixed weights in-sample, with warning
Comparing portfolios on the estimation window is in-sample; the response always carries an
explicit warning and points to the walk-forward backtest for out-of-sample evaluation.
