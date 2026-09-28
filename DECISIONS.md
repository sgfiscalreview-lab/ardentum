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

## D-017 Free hosting stack (founder-approved)
Frontend as a static export on Cloudflare Pages (Netlify fallback) calling the API directly
with CORS; backend on Google Cloud Run (max 2 instances, budget alert; Render free as the
no-card fallback); Supabase free tier for Postgres and OAuth sign-in (Google/GitHub), kept
awake by a daily `/health/db` ping from GitHub Actions. See DEPLOYMENT.md.

## D-018 Real market data: Kenneth French Data Library **(founder: confirm terms before commercial launch)**
The library is free, needs no key and has daily value-weighted US industry returns since
1926, which makes it the only free *real* dataset suitable for portfolio analysis. It has
no explicit licence; it is published by Prof. French for public use with citation. We cite
it in every result's provenance and flag that commercial redistribution should be confirmed
with the author. These are industry portfolios, not individual securities, so company ESG
data does not apply to them.

## D-019 Provider payloads cached in PostgreSQL
External payloads (Ken French zips, Tiingo histories, FRED series, FX rates) are stored
gzip-compressed in `provider_cache` with an in-process LRU in front. Free-tier instances
restart often and sources rate-limit, so a shared cache avoids re-downloading. When a
refresh fails the last good copy is served and the result says it is stale.

## D-020 Risk-free rate: user input, optionally fetched from a public source
The rate stays an explicit input so results are reproducible from the request alone. The
UI can fill it from (a) Fama-French RF (1-month T-bill; no key), compounded over the window
and annualised geometrically, or (b) FRED DGS3MO (needs a free key), whose daily investment
yields are converted to effective annual rates, $(1+y\cdot 91/365)^{365/91}-1$, and
averaged. The chosen source is echoed (`estimation.risk_free_source`) in every result.

## D-021 Multi-currency: unhedged conversion at ECB reference rates
Assets carry a quote currency (uploads: `currency` column; built-in data: USD). A universe
mixing currencies must name a base currency — we never silently mix. Prices are converted
as $P_B = P_L\cdot X$ with daily ECB reference rates from Frankfurter (free, keyless,
commercial use allowed), so $1+r_B=(1+r_L)(1+r_X)$: returns include currency moves
(unhedged). Rates are carried forward over at most 5 missing days (ECB holidays); prices
before 1999 or beyond a longer gap are errors. Hedged returns would need forward points or
interest differentials, which have no free daily source.

## D-022 Black-Litterman as a mean estimator
Implemented as a third expected-return estimator so every feature (optimise, frontier,
ESG impact, simulation, backtest, stability) can use it unchanged. The posterior predictive
covariance replaces the covariance estimate. The market-cap prior needs capitalisations
from the data (Ken French files or uploaded `market_cap`); otherwise users choose equal or
custom weights — the server never substitutes a prior silently. Verified against
PyPortfolioOpt. The UI offers absolute and pairwise relative views; the API accepts any
linear view portfolio.

## D-023 Minimum-CVaR objective on historical scenarios
Rockafellar-Uryasev LP over the estimation window, solved by the same verified CVXPY path
as other objectives. It uses no expected-return estimate unless a minimum return is set.
Historical scenarios only (no parametric CVaR): it keeps real fat tails, at the cost of
not extrapolating beyond the sample. A CVaR frontier is not offered yet.

## D-024 Shared rate limiting in PostgreSQL
Free hosting runs several short-lived instances, so an in-process limiter under-counts.
A sliding-window counter per client lives in `rate_limit_counters` (one atomic upsert per
compute request; old windows purged opportunistically). Clients are identified by the
verified user id, or by IP address; `ARDENTUM_TRUSTED_PROXY_HOPS` (1 on Cloud Run/Render)
selects the proxy-appended X-Forwarded-For entry so clients cannot forge it. If the
database is unavailable the limiter allows the request and logs a warning (availability
over strictness). SQLite deployments default to the in-process limiter.

## D-025 Background jobs without a queue service
Long calculations (Monte Carlo, backtests, frontiers, ESG impact, comparisons) run as
jobs: `POST /jobs` validates and starts the work; `GET /jobs/{id}?wait=20` long-polls.
Cloud Run's request-based billing throttles CPU between requests, so the work runs while
the client's poll is open, and any instance claims a queued job, or one whose heartbeat
is older than 30 s, with a conditional UPDATE. Jobs are deterministic, so a re-run is
safe; after two interrupted runs the job fails with a message. No Redis/Celery or paid
queue is needed. Results (gzip JSON) expire after 24 h. Signed-in users' jobs are
private; anonymous jobs are addressed by an unguessable UUID. The synchronous endpoints
remain for API clients.

## D-026 Open ESG data from WikiRate (founder-approved)
The founder asked for ESG values from open databases in addition to user-supplied scores.
WikiRate is free, licensed CC BY 4.0 (commercial use allowed with attribution), has a JSON
API and company ISINs. Scores are *derived* by Ardentum from one numeric metric chosen by
the user (fixed linear scale or percentile rank, user-chosen direction); matching is by ISIN
or user confirmation only; missing or non-numeric answers stay unscored. Overlays are
recomputed server-side on save, stored per user and dataset, and replace (never mix with)
the dataset's scores. Responses are cached for a day in `provider_cache`. A free WikiRate
API key can be set in `ARDENTUM_WIKIRATE_API_KEY` if WikiRate requires one.

## D-027 Visual design and legal pages
The founder asked that the UI avoid a list of patterns typical of generated sites (see
CLAUDE.md "UI rules"). The design is deliberately plain: restrained warm neutrals, a navy
accent, flat 2px surfaces, system fonts with a serif for titles, static skeletons, no
decorative motion. The landing page shows real screenshots of the app (on the labelled
synthetic data) instead of feature cards. Terms of Service and a Privacy Policy describe
exactly what the system does; operator name, contact and governing law are build-time
settings **(founder: fill in and have the texts reviewed)**. Users can export and delete
all their data (`GET /auth/me/export`, `DELETE /auth/me`); with
`ARDENTUM_SUPABASE_SERVICE_KEY` set, deletion also removes the Supabase sign-in record.

## D-028 Render as the no-card host for the API
The founder could not complete the Google Cloud setup. Render's free web service needs no
card and is set up entirely in the browser from `render.yaml` (a Blueprint), so it is now
the recommended host; Cloud Run stays supported (faster CPU, needs billing). Measured on
the demo data: about 200 MB after start-up and 243 MB at the largest allowed simulation,
inside the free plan's 512 MB with one worker; CPU-heavy requests take several times longer
on the free plan's CPU share, which the background-job design (D-025) absorbs (heartbeat
every 5 s, stale after 30 s). The free plan sleeps after 15 idle minutes, so the keep-alive
workflow now runs every 10 minutes (free for a public repository; one always-on service
fits the 750 free hours a month, so a second free Render service would not). Region
Singapore, the closest Render region to the Tokyo Supabase project. Deploys wait for CI
(`autoDeployTrigger: checksPass`) and only follow changes under `backend/`.
Measured with the production image limited to 512 MB and 0.1 CPU: first start with all
migrations 59 s, restart (waking from sleep) 58 s, 30-point frontier 2.7 s, default
simulation 5.9 s, largest allowed simulation 47 s, memory under 180 MB, no OOM.

## D-029 Mean-CVaR efficient frontier
A separate endpoint (`POST /frontier/cvar`, job kind `cvar_frontier`) so the mean-variance
contract stays unchanged. Each point solves the Rockafellar-Uryasev LP at a target return
over the estimation window's historical scenarios; CVaR stays one-period (the data's
frequency) and is not annualised, since tail losses do not scale with the square root of
time. The ESG preference tilt does not apply (as for the mean-variance frontier), but ESG
constraints do. The response also measures the mean-variance frontier's portfolios by the
same CVaR, which makes the difference between the two risk measures visible; for
elliptical returns the curves coincide, and the page says so.
