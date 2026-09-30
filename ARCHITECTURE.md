# Ardentum — Architecture

Ardentum is a quantitative portfolio-analysis platform. Users choose a universe of
assets, estimate risk and return, construct and optimise portfolios under explicit
constraints (including ESG), simulate and backtest them, and see the reasoning
behind every result.

## System overview

```
┌──────────────────────────┐   HTTPS/JSON    ┌──────────────────────────────────────────┐
│  frontend/ (Next.js)     │ ─────────────▶ │  backend/ (FastAPI, Python 3.12)          │
│  - App Router, TS strict │  Bearer JWT     │                                          │
│  - Tailwind UI, charts   │                 │  api/        HTTP layer (routers, schemas,│
│  - Supabase Auth client  │                 │              auth, errors, deps)          │
│  - Generated API types   │                 │  services/   orchestration, no maths      │
└───────────┬──────────────┘                 │  quant/      pure quantitative library   │
            │ sign-in                         │  data/       providers, CSV, validation   │
            ▼                                 │  db/         SQLAlchemy models            │
┌──────────────────────────┐                 └─────────┬───────────────┬────────────────┘
│  Supabase Auth           │  JWKS / secret            │               │
│  (identity provider)     │ ◀──────────────────────── │               │ HTTPS
└──────────────────────────┘                           ▼               ▼
                                          ┌──────────────────┐  ┌────────────────────────────┐
                                          │ PostgreSQL       │  │ External data (cached)     │
                                          │ (Supabase)       │  │ Ken French (returns, RF),  │
                                          │ users, datasets, │  │ Frankfurter/ECB (FX),      │
                                          │ portfolios, jobs,│  │ WikiRate (open ESG), FRED, │
                                          │ ESG overlays,    │  │ Tiingo (optional)          │
                                          │ provider cache,  │  └────────────────────────────┘
                                          │ rate limits      │
                                          └──────────────────┘
```

## Layering rules (enforced by review, see CLAUDE.md)

| Layer | Path | May import | Must not |
|---|---|---|---|
| Quant library | `backend/src/ardentum/quant` | numpy, pandas, scipy, cvxpy | do I/O, know about HTTP/DB, format text for UI beyond explanations |
| Data layer | `backend/src/ardentum/data` | quant errors, httpx, pandas | perform financial calculations beyond returns/validation |
| Services | `backend/src/ardentum/services` | quant, data, db, api.schemas | implement financial formulas |
| API | `backend/src/ardentum/api` | services, schemas | contain business logic |
| Frontend | `frontend/` | generated API types | compute financial metrics (it only formats numbers) |

Every financial number shown in the UI is computed by `ardentum.quant` and covered
by tests. The frontend never re-derives a metric.

## Backend modules

### `quant/` — the quantitative engine (pure, independently testable)

| Module | Responsibility |
|---|---|
| `returns.py` | simple/log returns, wealth index, annualisation (arithmetic vs geometric/CAGR) |
| `metrics.py` | volatility, covariance, correlation, beta, Sharpe, Sortino, drawdown, Calmar, VaR/CVaR, tracking error, information ratio, `performance_summary` |
| `portfolio.py` | portfolio return/volatility, Euler risk decomposition, diversification ratio, effective N, constant-mix/buy-and-hold returns |
| `estimation.py` | expected returns (historical, Bayes–Stein, Black–Litterman) and covariance (sample, Ledoit–Wolf identity, Ledoit–Wolf constant-correlation); `MarketEstimates` with provenance |
| `black_litterman.py` | equilibrium prior, He–Litterman/Idzorek view uncertainty, posterior returns and covariance |
| `optimisation.py` | CVXPY engine: min-vol, max-Sharpe (homogenised), target return, target volatility, max utility, min-CVaR (Rockafellar–Uryasev LP); bounds, exclusions, sector limits, min ESG, ESG tilt, gross exposure, tracking error; post-solve verification and diagnostics (binding constraints, shadow prices) |
| `frontier.py` | constrained efficient frontier; ESG-efficient (Sharpe vs min-ESG) frontier |
| `esg.py` | ESG score alignment/validation, standardisation, tilt, portfolio score; raw open-data metrics → 0–100 (linear scale, percentile rank) |
| `currency.py` | FX alignment and unhedged conversion of prices to a base currency |
| `montecarlo.py` | seeded parametric (lognormal), i.i.d. bootstrap and stationary block-bootstrap simulation; contributions/withdrawals and depletion |
| `backtest.py` | walk-forward backtest (no look-ahead), rebalancing schedules, costs, strategy protocol |
| `attribution.py` | contributions, Carino linking, Brinson–Fachler |
| `explain.py` | KKT-based explanations, assumptions, bootstrap weight stability |

### `data/`

* `providers/demo.py` — deterministic **synthetic** universe (fictional `.SYN` tickers,
  illustrative ESG scores), labelled synthetic everywhere.
* `providers/csv_upload.py` — strict parsing of user CSVs (wide or long), metadata with ESG provenance.
* `providers/kenfrench.py` — Kenneth French Data Library: industry portfolios (kf12, kf49), market and risk-free returns, market caps (D-018).
* `providers/fx.py` — ECB reference rates via Frankfurter (D-021).
* `providers/wikirate.py` — WikiRate open ESG data: metrics, companies (ISINs), answers (D-026).
* `providers/tiingo.py`, `providers/fred.py` — keyed adapters (Tiingo needs a licence for commercial use, D-004).
* `validation.py` — alignment of histories, gap handling, data-quality warnings.

### `services/`

* `market_data.py` — dataset resolution (`demo`, `kf12`, `kf49`, `tiingo`, uploaded UUIDs),
  currency conversion and loading of aligned return windows at daily/weekly/monthly frequency.
* `provider_cache.py` — PostgreSQL cache (gzip payloads) for external data with an in-process
  LRU and stale fallback (D-019).
* `risk_free.py` — risk-free rate from Fama-French RF or FRED DGS3MO (D-020).
* `open_esg.py` — WikiRate matching, scoring and saved ESG overlays.
* `jobs.py` — background jobs claimed by long-polls, heartbeat and recovery (D-025).
* `analysis.py` — maps API requests → quant calls → API responses (applies ESG overlays).
* `usage.py` — anonymous daily counts of completed calculations, saves and exports (D-035).

### `api/`

FastAPI app factory (`create_app`), routers under `/api/v1`, pydantic schemas, auth,
consistent error envelope `{"error": {"type", "message", "details"}}`.

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /meta` | liveness, capabilities |
| `POST /auth/dev-login`, `GET /auth/me` | dev-only token; current user |
| `GET/POST/DELETE /datasets[...]` | list/inspect demo & live datasets; upload/delete CSV datasets |
| `POST /analytics` | per-asset statistics, correlation, covariance, normalised prices |
| `POST /optimise` | optimisation + explanation + optional weight-stability resampling |
| `POST /frontier` | constrained vs unconstrained efficient frontier |
| `POST /esg/impact` | ESG vs baseline: return, risk, Sharpe, composition, tracking error, ESG frontier |
| `POST /montecarlo` | seeded simulation |
| `POST /backtest` | walk-forward backtest + attribution |
| `POST /compare` | side-by-side comparison of fixed-weight portfolios |
| `CRUD /portfolios`, `GET /portfolios/{id}/export` | saved portfolios; CSV/JSON export |
| `GET /risk-free/sources`, `POST /risk-free` | public risk-free sources; window-average rate |
| `POST /jobs`, `GET /jobs/{id}?wait=` | run any compute request in the background; long-poll |
| `GET /esg/open/metrics`, `GET /esg/open/companies`, `POST /esg/open/preview` | browse WikiRate; preview scores |
| `CRUD /esg/overlays` | saved open-data ESG overlays (used via `universe.esg_overlay_id`) |
| `GET /health/db` | database check (daily keep-alive) |
| `GET /usage` | public, anonymous usage counts |

Compute endpoints are rate limited per verified user or client IP with a counter shared
through PostgreSQL (D-024).

### `db/`

Tables: `users` (id = identity-provider subject), `datasets` (gzip CSV blob + asset
metadata JSON incl. currency, ISIN, market cap), `portfolios` (weights + generating spec +
summary), `provider_cache`, `rate_limit_counters`, `jobs`, `esg_overlays`, `usage_counts` (day, kind,
count; nothing about users). Alembic migrations in
`backend/migrations`. Row ownership is enforced in the API (the backend is the only
database client; Supabase RLS is not relied upon).

## Frontend

Next.js (App Router) + TypeScript (strict) + Tailwind. API types are generated from the
backend OpenAPI schema (`npm run gen:api`). Pages: landing, workspace (universe →
analytics → optimise → frontier → ESG data → ESG impact → Monte Carlo → backtest →
compare), saved portfolios, research/methodology, sign-in (Google/GitHub OAuth). Long
calculations go through background jobs (`runJob`). The app builds either as a static
export (`NEXT_OUTPUT=export`, calling the API directly) or as a Node server that proxies
`/api/v1`.

## Authentication

Production: Supabase Auth issues JWTs; the backend verifies signature (JWKS for
ES256/RS256, or the legacy HS256 secret), `exp`, `aud=authenticated`,
`iss=<SUPABASE_URL>/auth/v1`. Development/tests: a dev-only login issues HS256 tokens;
settings validation forbids it in production.

## Deployment (free tier, D-017; see DEPLOYMENT.md)

* Frontend: static export on Cloudflare Pages (Netlify fallback).
* Backend: container (`backend/Dockerfile`) on Google Cloud Run, max 2 instances (Render fallback).
* Database + auth: Supabase (managed PostgreSQL + Auth), kept awake by a daily GitHub Actions ping.
* CI: GitHub Actions — lint, type-check, unit/integration tests (SQLite + PostgreSQL),
  migrations, frontend build + static export, Playwright E2E (with a local WikiRate
  stand-in), Docker builds.
