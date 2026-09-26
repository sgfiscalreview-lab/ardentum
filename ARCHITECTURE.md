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
                                          ┌──────────────────┐  ┌────────────────────────┐
                                          │ PostgreSQL       │  │ Market data providers  │
                                          │ (Supabase)       │  │ Tiingo (prices), FRED  │
                                          │ users, datasets, │  │ (risk-free rate)       │
                                          │ portfolios       │  └────────────────────────┘
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
| `estimation.py` | expected returns (historical, Bayes–Stein) and covariance (sample, Ledoit–Wolf identity, Ledoit–Wolf constant-correlation); `MarketEstimates` with provenance |
| `optimisation.py` | CVXPY mean–variance engine: min-vol, max-Sharpe (homogenised), target return, target volatility, max utility; bounds, exclusions, sector limits, min ESG, ESG tilt, gross exposure, tracking error; post-solve verification and diagnostics (binding constraints, shadow prices) |
| `frontier.py` | constrained efficient frontier; ESG-efficient (Sharpe vs min-ESG) frontier |
| `esg.py` | ESG score alignment/validation, standardisation, tilt, portfolio score |
| `montecarlo.py` | seeded parametric (lognormal), i.i.d. bootstrap and stationary block-bootstrap simulation |
| `backtest.py` | walk-forward backtest (no look-ahead), rebalancing schedules, costs, strategy protocol |
| `attribution.py` | contributions, Carino linking, Brinson–Fachler |
| `explain.py` | KKT-based explanations, assumptions, bootstrap weight stability |

### `data/`

* `providers/demo.py` — deterministic **synthetic** universe (fictional `.SYN` tickers,
  illustrative ESG scores), labelled synthetic everywhere.
* `providers/csv_upload.py` — strict parsing of user CSVs (wide or long), metadata with ESG provenance.
* `providers/tiingo.py`, `providers/fred.py` — live adapters (need API keys; see DECISIONS D-004).
* `validation.py` — alignment of histories, gap handling, data-quality warnings.

### `services/`

* `market_data.py` — dataset resolution (`demo`, `tiingo`, uploaded UUIDs) and loading of
  aligned return windows at daily/weekly/monthly frequency.
* `analysis.py` — maps API requests → quant calls → API responses.

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

### `db/`

Tables: `users` (id = identity-provider subject), `datasets` (gzip CSV blob + asset
metadata JSON), `portfolios` (weights + generating spec + summary). Alembic migrations in
`backend/migrations`. Row ownership is enforced in the API (the backend is the only
database client; Supabase RLS is not relied upon).

## Frontend

Next.js (App Router) + TypeScript (strict) + Tailwind. API types are generated from the
backend OpenAPI schema (`npm run gen:api`). Pages: landing, workspace (universe →
analytics → optimise → frontier → ESG → Monte Carlo → backtest → compare), saved
portfolios, research/methodology, sign-in.

## Authentication

Production: Supabase Auth issues JWTs; the backend verifies signature (JWKS for
ES256/RS256, or the legacy HS256 secret), `exp`, `aud=authenticated`,
`iss=<SUPABASE_URL>/auth/v1`. Development/tests: a dev-only login issues HS256 tokens;
settings validation forbids it in production.

## Deployment (target)

* Frontend: Vercel (or any Node host) — `frontend/`.
* Backend: container (`backend/Dockerfile`) on Render/Fly.io/Cloud Run.
* Database + auth: Supabase (managed PostgreSQL + Auth).
* CI: GitHub Actions — lint, type-check, unit/integration tests (SQLite + PostgreSQL), frontend build, Playwright E2E.
