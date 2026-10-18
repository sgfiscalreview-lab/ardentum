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

## D-027 Visual design and legal pages (look superseded by D-041)
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
Singapore, the closest Render region to the Tokyo Supabase project. Deploys follow every
commit on main under `backend/` (`autoDeployTrigger: commit`); `checksPass` was dropped
because it also waited for the live smoke test, whose failures can come from the website
host and then blocked all API deploys. Code reaches main only through pull requests
whose CI passed. The keep-alive is scheduled every 5 minutes because GitHub delays
scheduled runs (10-minute schedules arrived every 13 to 17 minutes).
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

## D-030 Composite open-ESG scores
Overlays can combine 2 to 6 WikiRate metrics. Each is scored by the existing single-metric
pipeline (ISIN or user-confirmed matching, latest answer up to a year, linear or
percentile transform with its own direction), then combined as a weighted average with
positive user weights normalised to one (`quant.esg.composite_scores`). An asset gets a
composite only with a score for every metric: renormalising over the available metrics
is implicit imputation and compares companies on different measures, which CLAUDE.md
rules out. Saved composites keep `kind: composite` in the overlay spec; `metric` and
`transform` are null on those overlays and `components` lists the metrics and weights.
Each asset's score provenance names every metric with its weight, year, part score and
transformation.

## D-031 Currency-hedged returns from BIS policy rates
D-021 left hedging out for lack of a free source of forward points. Covered interest
parity prices a forward from the two currencies' short rates, and the BIS publishes daily
central-bank policy rates for about 30 economies through a free, keyless API whose terms
allow reuse (including commercial) with the BIS cited. The hedge is a one-period forward
on the start-of-period value, re-set on every source price date, so
`r_H = r_L (1 + r_X) + (1 + i_B d)/(1 + i_L d) - 1` with rates known at `t-1` (no
look-ahead). Policy rates approximate the money-market rates that actually price
forwards; the spread, transaction costs and forward bid-ask are ignored and this is
stated in every result's provenance. Rates are cached for 20 hours like FX. Currencies
without a BIS series (e.g. SGD) cannot be hedged and get a clear error. OECD 3-month
interbank rates via FRED were the alternative, but they are monthly and need a key.

## D-032 Legal and compliance checklist
Reviewed the app against a common 20-point checklist. Items that apply were built:
privacy policy (legal bases, processors including Render and BIS, international
transfers, retention, rights, how to request deletion, no marketing emails), terms (age
16+, fees and refunds, licences), a cookie policy listing every browser-storage item,
operator address and registration (optional settings, shown in the footer), an age
confirmation at sign-in, third-party notices generated at build time, and a table view for
the one chart without a text alternative. Data minimisation: rate-limit counters now store
a keyed, daily-changing HMAC of the IP address instead of the address
(`ARDENTUM_RATE_LIMIT_SECRET`; Render generates it).

Not built, and why:
* **Cookie consent banner.** Ardentum sets no cookies and stores only strictly necessary
  items (session token, theme and workspace choices), which ePrivacy Art. 5(3) and UK PECR
  reg. 6 exempt from consent. A banner with nothing to refuse would itself be a dark
  pattern. The cookie policy commits to asking first if non-essential storage is added.
* **Refund policy page, hidden fees.** The service is free with no payment flow; the terms
  say so and set conditions for any future paid features.
* **Fake reviews, unsupported claims.** None exist (no testimonials by design); the landing
  copy was re-checked against the code and tests.
* **Unsubscribe links.** No marketing emails are sent; Supabase account emails are
  transactional.
The build-time licence check allows LGPL only in build-only packages (sharp's libvips) and
fails on any other copyleft or undeclared licence, so a dependency change cannot ship one
unnoticed.

## D-033 Audit fixes
A full audit (quant, API, frontend, UX, security, deployment) found no wrong numbers; the
fixes are about robustness and phones.
* **Phone layout.** The header and eight page grids were wider than a 375 px screen (a
  grid without `grid-cols-1` sizes its single column to its widest content). The header now
  puts the menu on its own row below `sm`; `e2e/responsive.spec.ts` keeps it that way.
* **Unexpected errors.** Starlette sends `Exception` handlers to its outermost middleware,
  whose responses skip CORS, so browsers hid the message and reference and showed a
  network error. `UnexpectedErrorMiddleware` answers inside the CORS layer. Caller-supplied
  request ids are only echoed if they look like ids.
* **Frontend resilience.** Styled `error.tsx`, `global-error.tsx` and `not-found.tsx`;
  saved workspace settings are rebuilt on top of the current defaults; requests time out
  after 90 s with a message about the API starting up; cancellations are not shown as errors.
* **Numerics and resources.** One pooled HTTP client for data providers (clients were never
  closed); the SCS fallback is capped at 20 s; a CVaR resting on fewer than 10 tail
  observations carries a warning.
* **Content-Security-Policy.** Written into `out/_headers` after each static build
  (`scripts/add-csp.mjs`) because the allowed API and Supabase origins are build settings.
  Next.js inlines scripts in exported pages and static hosting has no per-request nonce,
  so `script-src` allows `'unsafe-inline'`; everything else is locked to the app's origins.
* **Operations.** Preview deployments may call the API (`ARDENTUM_CORS_ORIGIN_REGEX` in
  `render.yaml`); the guides recommend an outside uptime monitor because GitHub disables
  schedules after 60 idle days, and note that one awake Render service uses ~744 of 750
  free hours.


## D-034 Open-source release 1.0.0
The code is released under the MIT licence, with `CITATION.cff`, a changelog and release
notes, so it can be cited and archived with a DOI (Zenodo archives each GitHub release;
`docs/RELEASING.md`). MIT is the most widely understood permissive licence and matches the
licences of the main dependencies. It covers the code only: data sources keep their own
terms (Licences page), and the name is not licensed. The copyright line reads "The
Ardentum authors" until the author adds their name.

## D-035 Anonymous usage counts and a guided tour
To report real usage without tracking anyone, the API keeps one number per UTC day and
kind of action (`usage_counts`: day, event, count). A request adds one only when it
succeeds; background jobs add one in the same transaction that marks them finished, so a
visible result is always counted and a failed count can never fail a job (savepoint).
Nothing about the person, address, device or content is stored, so the totals are not
personal data; they are public at `/api/v1/usage` and on the Usage page, and the Privacy
Policy describes them. The live smoke test sends `X-Ardentum-Monitor` and is not counted
(the header can only lower counts, so honouring it from anyone is safe). Visitors and page
views are deliberately not counted: that would need a tracker or IP logging.
The guided tour (`/tour`, `?tour=<step>` on workspace pages) walks through eight steps on
the synthetic demo data with no sign-in.

## D-036 Research studies
`research/` holds three studies built on the engine and rerun on public data by a GitHub
workflow (the dev container cannot reach the data hosts). Choices:
* **Walk-forward only.** Every portfolio uses data available at its formation date.
* **Sharpe-ratio tests.** The Jobson-Korkie test with Memmel's correction is reported
  because DeMiguel, Garlappi and Uppal (2009) use it, next to a HAC version of Ledoit and
  Wolf (2008), which stays valid under fat tails and autocorrelation. The robust test uses
  a Bartlett kernel with the Newey-West (1994) lag rule rather than their quadratic-spectral
  kernel with prewhitening; simulation tests check its size.
* **Promised versus delivered.** The delivered Sharpe ratio is computed over all
  out-of-sample months pooled. Averaging 12-month Sharpe ratios overstates it (noisy
  ratios; calm years dominate), which an earlier version did.
* **Currency hedge.** A one-month forward priced by covered interest parity from central
  bank policy rates, the same method as the app (D-031); policy rates stand in for the
  interbank rates that price real forwards.
* Rejected topics: the cost of ESG screens (no historical ESG scores in the free data, and
  scores are never imputed), value-premium decay (does not use the engine),
  Black-Litterman views (results depend on subjective views).

## D-037 Classroom kit
A ready-made lesson (`/classroom`, `/classroom/worksheet`) gives teachers a reason to use
Ardentum and students something concrete to do: find a portfolio safer than the safest
asset, test the optimiser's promised Sharpe ratio in a walk-forward backtest against equal
weights, and read Monte Carlo ranges. It runs on the synthetic demo data with the
workspace defaults, so every student sees the same numbers. Those numbers live in
`frontend/src/lib/classroom-answers.json`; `backend/tests/api/test_classroom_answers.py`
recomputes them through the API, and an end-to-end test checks that the workspace defaults
reproduce them, so a change to the demo data, the defaults or the engine cannot leave the
answer key wrong. The worksheet prints without the site header, footer or page tint.

## D-038 Security pass
A review against a common web-app checklist (secrets, rate limits, access, passwords, keys,
authentication, dependencies, input, XSS, debug mode, environment, exposed files, admin
routes, endpoints, CORS, headers, database access). `SECURITY.md` maps each item to the
code and tests.
* **Database closed to Supabase's Data API (the one serious finding).** Supabase publishes
  the `public` schema at `/rest/v1` and grants new tables to its `anon` and
  `authenticated` roles, whose key the website holds by design. The migrations never
  enabled row-level security, so anyone with that key could read and change every table;
  the live smoke test confirmed it. Migration 0007 enables row-level security with no
  policies and revokes those roles' privileges, including on future tables. The API is
  unaffected because it connects as the tables' owner. A PostgreSQL test recreates
  Supabase's grants and fails if any table, present or future, is left open; the smoke
  test checks the live project. Remote production connections require TLS.
* **Two rate-limit budgets.** Calculations keep theirs; saves, uploads, deletions,
  sign-in and WikiRate lookups get a second one (60 a minute each), so a script cannot
  fill the free database or get the API blocked by WikiRate. CORS now wraps every
  middleware: a 429 previously reached browsers without CORS headers and looked like a
  network error.
* **Bounded input.** Bodies are capped at 1 MB (uploads: two 5 MB files); saved settings
  at 64 KB; ESG overlays at 100 per user; the remaining unbounded lists at the asset
  limit. Framework errors use the usual error format.
* **Output that other programs read.** CSV exports write formula-like text as text
  (WikiRate company names are editable by anyone); WikiRate links must be http(s); the
  sign-in return address accepts only plain paths on the site (`/\host` was accepted).
* **Headers and surface.** HSTS, Content-Security-Policy and cross-origin policies on the
  API (the documentation page may load Swagger UI); the Node server sends the website's
  full header set, built from the same module as the static `_headers`. Developer sign-in
  is not registered outside dev mode. Uvicorn's access log (client addresses) and server
  header are off; the API's own log has no addresses, as the Privacy Policy says.
* **Secrets and dependencies.** gitleaks scans every commit in CI (history clean); builds
  fail if a secret key reaches browser files; the smoke test checks the live bundle.
  pip-audit and npm audit run weekly and on lockfile changes rather than in CI, so a new
  advisory does not block unrelated work; Dependabot proposes grouped monthly updates.
* **Kept as is.** The API documentation stays public (it documents the public API).
  There are no admin routes and no passwords (OAuth only). Major-version upgrades
  (TypeScript 7, ESLint 10, Vitest 5, jsdom 30) wait for their own pull requests.

## D-039 Product improvements after trying every page
Every page was opened on a laptop and a phone screen and every calculation was run, looking
for anything confusing. Changes:
* **Sleeping API.** The free host stops the API after a quiet period, and the first
  request then waits up to a minute with nothing on screen. Every page load now sends a
  wake-up request, and a notice with a running count appears when a request has waited
  three seconds for a possibly sleeping API (before any answer in the session, or after
  ten quiet minutes). Background-job polls, which wait on purpose, never trigger it.
* **Shareable links.** Settings were only in one browser's storage, so a teacher could
  not hand a class an analysis. The link carries the settings and the page's calculation
  in its fragment, deflate-compressed: no server stores anything, and the recipient's page
  recomputes the identical result. The recipient's own settings are replaced only with a
  visible notice and a way back; unreadable links change nothing. Links to an uploaded
  dataset or saved ESG scores say that only their owner can open them.
* **Risk parity.** A common objective that uses no expected returns, the noisiest input.
  It is exact (equal shares to machine precision) rather than "closest within your
  limits": the weights come from the risks alone, so a limit it breaks is named with the
  weight that breaks it. With the workspace's default 30% cap on the demo data, the bond
  fund needs 45%, and the message says so.
* **Readability.** The optimiser's reasons were in a narrow last column, cut off on
  laptops and phones; each now has a full-width row. Result labels link to a glossary of
  plain definitions, each linked to its formulas. Workspace pages print (or save as PDF)
  their results without menus and settings. Long calculations show elapsed seconds.
* **Dependabot.** At most one minor-and-patch and one major pull request per ecosystem
  each month. Docker base images are left alone: their Python and Node versions match
  `requires-python` and CI, so a bump there must be made together with those settings.

## D-040 Crisis replay, factor exposure, trade lists and starting examples
Four additions chosen after asking what a first-time visitor, a class and a returning user
miss most.
* **Crisis replay.** Seven crises, each from the US market's closing high to its closing
  low (S&P 500; Dow Jones for 1929), so every portfolio is measured over the same dates.
  The portfolio is bought at the first close and held without trading: the simplest
  assumption to explain ("you owned this going in") and the one under which contributions
  add up exactly to the return. Recovery keeps holding after the low until the previous
  high is regained, using all later data. The named crises are refused on synthetic data,
  whose dates contain no real events; any period the user chooses works on any daily data.
  The dates live in one backend catalogue that the page reads, so they cannot drift apart.
* **Factor exposure.** The Fama-French three-factor model, because its data is already
  downloaded with the industry portfolios and it is the standard first model in teaching.
  Newey-West standard errors because daily returns are heteroskedastic and slightly
  autocorrelated; p-values from Student's t, matching statsmodels (a test-only dependency).
  Weekly and monthly factor returns are compounded from the daily series rather than taken
  from French's monthly files, so any frequency and any upload calendar line up with the
  factor data; periods the factors do not fully cover are dropped and reported. Synthetic
  data is refused: regressing it on real factors would produce meaningless numbers.
* **Trade list.** Costs are paid out of the portfolio, so the value invested afterwards
  solves a one-dimensional equation; it has a unique root and the result is checked
  against the cash identity. Amounts are in the user's currency, with no prices or units,
  because the built-in assets are not tradable as such (the page says so). Trade lists
  stay out of shared links: they contain what someone owns.
* **Starting examples.** Four one-click examples replace the settings and open a page
  with the calculation already submitted (the same mechanism as shared links). Three use
  real data, one the synthetic 60/40 demo; each is labelled.
* **Found on the way.** Choosing a real industry dataset showed a free-text ticker box
  meant for live data instead of the list of industries; the list now shows whenever a
  dataset has one. The Kenneth French address is configurable, and the browser tests use
  a local stand-in serving the generated fixtures, so they no longer depend on Dartmouth.

## D-041 Fluid interface, after Apple's design guidance
The founder asked for a redesign following `.claude/skills/apple-design` (Apple's WWDC
talks, chiefly *Designing Fluid Interfaces*, translated for the web). This replaces the
visual parts of D-027 (flat 2px surfaces, no shadows, blur or motion); the palette, the
system fonts, the plain copy and the other UI rules stay.
* **Materials and depth.** The header is a translucent material that content scrolls
  under; its lower edge shows only once something is beneath it. Popovers, tooltips and
  the steps sheet use a thicker material and a deeper shadow than cards, so size and
  layer read as depth. Corners are 6 to 22 px by size. Translucency turns solid when the
  user asks for reduced transparency or more contrast, or the browser cannot blur.
* **Springs, not durations.** Everything that moves uses a spring defined by Apple's two
  parameters (damping ratio, response), mapped to stiffness and damping in
  `lib/motion.ts` and tested against the closed form. Critically damped by default; a
  slight overshoot only after a drag or flick, because then the gesture carried momentum.
  Springs start from the value on screen, so every animation can be redirected.
* **Direct manipulation.** On phones the workspace steps live in a bottom sheet that
  follows the finger from where it was grabbed, resists past the top (rubber-banding),
  continues at the release speed and projects a flick forward to decide whether it closes
  (Apple's projection with deceleration 0.998). Buttons respond on press, not on release.
* **Anchored, symmetric paths.** Popovers grow from the control that opened them and
  return into it; the sheet leaves the way it came; a disclosure folds back into its
  header. Segmented controls slide one highlight between choices.
* **Accessibility.** With reduced motion the sheet fades instead of sliding and nothing
  scales on press; Motion's `reducedMotion="user"` covers the rest. Keyboard paths: arrow
  keys move segmented choices, Escape closes popovers and the sheet, focus stays in the
  sheet while open and returns to its opener.
* **Typography.** System sans for titles as well (the serif is gone), with size-specific
  tracking: negative for display and titles, slightly positive for captions.
* **Library.** Motion (`motion`, MIT) for springs, presence and shared-layout animation;
  loaded lazily through `LazyMotion` so pages that do not animate pay little for it.

## D-042 Completing the fluid interface
A review of D-041 against every section of the apple-design skill left gaps; this closes
them and records the two parts deliberately left out.
* **Sheet.** The page behind is pushed back (scaled to 95% with rounded corners on a
  charcoal backdrop) in step with the sheet, so dragging the sheet also moves the page.
  A closing sheet can be caught and pulled back up. A press becomes a drag after 10 px.
  The sheet is slightly see-through while it travels. A frame-by-frame recording of the
  opening found it flung 5,700 px past the top and falling back: parking it at the
  screen edge with `set()` implied a huge velocity that the spring inherited. It is now
  placed with `jump()`, and the recording shows a monotonic rise from 800 to 120 px.
* **Only transform and opacity animate.** Disclosures and the server notice no longer
  animate height. The notice floats above the page instead of pushing it down.
  Departing surfaces stop taking clicks as they start to leave.
* **Materials.** Popovers and the notice materialize: their blur radius grows with scale
  and opacity. Materials have a light top edge. The header's ruled line became a scroll
  edge: a short band of blur that fades out, shown only while content is underneath.
  The fade is a mask on the blur and colours nothing, so the no-gradients rule holds.
  The workspace sidebar is an inset, opaque tint, as a structural region.
* **Accessibility and type.** Light and dark switch with a 280 ms colour ease instead of a
  brightness jump. Every text size is in rem, so a larger text setting enlarges it.
  Small controls get touch margins; axe now checks WCAG 2.2 AA (target size) and also
  runs at phone width, which found wide formulas on methodology pages that scrolled but
  could not be reached by keyboard (now focusable).
* **Forgiveness.** Starting from an example keeps the way back, like a shared link: the
  notice offers "Go back to my settings", and trying several examples still leads back
  to the settings from before the first. Disabled run buttons say why beside them.
* **Left out.** Sound and haptics: the skill's own utility rule says to add them only
  where they earn their place, and in an analysis tool they do not (iPhone Safari also
  has no vibration support). Motion blur for very fast movement: it would repaint every
  frame, against the same skill's compositor-only rule, and the fastest motion here (a
  flicked sheet) is short.
* **Corners and screenshots (founder review).** The landing screenshots sat in a 16 px
  frame with its own border and shadow around a picture that already held the card's
  12 px corners, border, shadow and a strip of page background, and cut off at the
  bottom mid-card: two edges, corners on different centres, content missing. Pictures
  are now taken card by card on the app's own background, end at the last whole card
  and are shown with no frame, so the card's own edge is the only edge. Nested panels
  follow concentric radii (inner = outer minus padding): tiles in cards 8 px, the
  sidebar, sheet and popovers 20 px around 8 px rows.

## D-043 Backend review: numbers that could be wrong, outages, and saying why
A review of the backend from three sides (quant methods, engineering, product) found
places where a number could be wrong without any sign, where one request could take the
API down, and where a figure was blank or zero without a reason. Each finding was checked
in the code before it was fixed; each fix has a test that fails without it.
* **Refuse rather than mis-annualise.** Returns are annualised with 252, 52 or 12 periods
  a year, so a frequency finer than the prices (daily returns from monthly prices: about
  4.6 times too much volatility) or daily statistics on calendar days (weekends included)
  are refused with the frequency to choose. An upload says which frequencies its prices
  support and switches the workspace to one of them, so the refusal is not met on every
  page. Resampling to weeks or months leaves out a last period that has not ended.
* **No look-ahead through priors.** Black-Litterman market-capitalisation prior weights in
  a backtest use the capitalisations of the latest month that had ended at each
  rebalance; a single current value is refused for backtests (it would tell past
  decisions which assets later grew). ESG scores have no history, so a backtest using them
  says it applies today's scores.
* **Undefined is n/a with a reason, never zero or identity.** One constant series used to
  turn the whole correlation matrix into the identity; now only its row is n/a. Risk
  contributions at zero volatility, and Compare's Sharpe ratio, ESG score and largest risk
  contributors, are n/a with the reason. Compare listed unheld assets among the largest
  risk contributors; it lists holdings only.
* **Explanations say only what is true.** They used the plain expected returns when an
  ESG tilt had changed the objective, and could say an asset's return was "below what it
  would need" when a full sector was what kept it out. They now use the returns the
  objective used, check each statement, and otherwise name the binding constraint.
* **Outages.** CSV headers and long-format ticker counts are checked before parsing (a wide
  file could exhaust the 512 MB instance). Jobs hold no database connection while
  computing, and at most two run at once. Provider downloads are parsed before they are
  cached: an error page served with status 200 used to be cached for a day. Free-text
  WikiRate searches stay in memory, and old WikiRate and Tiingo rows are purged; Ken
  French, exchange-rate and policy-rate rows are kept as the fallback when a source is
  down. A first sign-in sending several requests no longer fails on the duplicate insert.
  Deleting an account removes its rate-limit counters (the keys never matched). Request
  dates are bounded to 1900 to 2100 instead of failing inside pandas.
* **New: how sure is a Sharpe ratio?** Every performance summary carries a 95% interval
  for the Sharpe ratio, and a backtest tests the strategy against its benchmark (Ledoit
  and Wolf, 2008) with the p-value in words. Both use the delta method with a Newey-West
  (Bartlett) long-run covariance, so fat tails, skew and autocorrelation are allowed for;
  the interval reduces to Lo (2002) for independent normal returns and to Mertens (2002)
  without lags, which the tests check exactly, and simulations check coverage and test
  size. A bootstrap would be more exact in small samples but too slow for every request.
  The research studies keep their own copy of these statistics so their published
  numbers stay reproducible.
* **Smaller honesty fixes.** Monte Carlo states that values are nominal and that its
  inputs come from the window it describes; amounts are shown in the data's currency
  instead of always in dollars. A linear ESG scale warns when it clips values to its end
  points. The effective number of positions counts short positions.
* **Deploy freshness.** The API reports the commit it was built from, and the live check
  fails when the deployed API is older than the latest backend change on `main`.

## D-044 The API image runs on the Python it is tested on
The live API stopped answering on 2026-10-15 at about 13:30 UTC. Its image had been moved
to `python:3.14-slim` by a Dependabot pull request on 2 October, but the project declares
`requires-python = ">=3.12,<3.14"` and CI tests on 3.12. Finding no usable interpreter in
the image, uv quietly downloaded its own Python 3.13 into `/root` during the build, and
the app runs as an unprivileged user that cannot read `/root`. Every deploy after that
change failed (2, 2 and 4 October), so the 2 October version stayed live, which is why
crisis replay, factor exposure and trade lists were missing from it. The deploy of 15
October reported success and answered once, but has not started since the free instance
first went to sleep. Started as its own user, the image built from `main` stops at once
with `alembic: Permission denied` (reproduced in CI); Render's logs hold the exact sequence
on its side.
* The image is back on Python 3.12, the version CI tests. uv may not download an
  interpreter (`UV_PYTHON_DOWNLOADS=never`), so a base image outside `requires-python`
  now fails the build instead of producing an image that cannot start.
* CI no longer only builds the image: it starts it the way Render runs it (its own user,
  migrations through the entrypoint, PostgreSQL), checks that it answers, restarts it as
  a sleeping free instance does and checks again (`scripts/check_api_image.sh`). Building
  is not starting.
* Dependabot already leaves Docker base images alone; change the Python version by hand,
  together with `requires-python` and CI.

## D-045 A bootstrap Sharpe test for short histories; ESG scores as they were known
Two items left open by D-043.
* **Bootstrap.** The Sharpe test of D-043 rests on a normal approximation that can be
  poor on short histories. A backtest whose evaluation has at most 1,000 returns now also
  runs Ledoit and Wolf's studentized circular block bootstrap (2008, section 3.2): 999
  resamples, blocks of `round(T^(1/3))` periods, a fixed seed (0 unless the request sets
  `bootstrap_seed`) echoed in the result. Ledoit and Wolf calibrate the block length; the
  cube-root rule is simpler and standard. Above 1,000 returns the bootstrap is skipped and
  the result says why: the asymptotic test is reliable there, and the resampling would
  lengthen every long backtest for nothing. It runs inside the backtest, which
  is already a background job, so it needs no job of its own.
* **Point-in-time ESG.** Applying today's scores at past rebalances let later
  information steer earlier decisions. Each score now keeps the date from which it was
  known: an uploaded score its `esg_as_of`, a WikiRate score one score per answer year,
  known from 30 June of the next year (WikiRate does not record when an answer became
  available, and most annual reports are out by then). Percentile ranks are taken within
  each year, and a composite exists only for years in which every metric has a score, so
  nothing is imputed across years. A backtest uses only the latest score known at each
  rebalance, but only when every scored asset has dated scores and each was known by the
  first rebalance. Mixing point-in-time scores with today's, or dropping assets until
  their first score appears, would change the universe or the meaning of the constraint
  part way through; instead the backtest applies today's scores, says which assets had no
  score yet and from which date all are known, so a later start can be chosen.
  Undated scores (the demo data's) remain today's at every rebalance, with a note.
