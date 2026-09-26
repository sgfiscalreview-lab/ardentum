# Ardentum

**Quantitative portfolio analysis you can explain.** Construct, optimise, simulate,
backtest and compare investment portfolios, with the mathematics, assumptions and
limitations behind every result.

| | |
|---|---|
| **Optimisation** | Minimum volatility, maximum Sharpe (exact convex reformulation), target return/volatility, mean–variance utility |
| **Constraints** | Position bounds, exclusions, sector limits, gross exposure, tracking error, minimum ESG score, ESG preference |
| **Estimation** | Historical and Bayes–Stein means; sample and Ledoit–Wolf (identity / constant-correlation) covariance |
| **Analysis** | Efficient and ESG-efficient frontiers, risk decomposition, KKT-based explanations, weight-stability resampling |
| **Simulation** | Seeded parametric, bootstrap and stationary block-bootstrap Monte Carlo |
| **Backtesting** | Walk-forward (no look-ahead), transaction costs, Cariño-linked and Brinson–Fachler attribution |
| **Platform** | Accounts (Supabase Auth), saved portfolios, CSV uploads, CSV/JSON export, methodology section |

> Ardentum is an analytical tool for education and research. It does not provide
> investment advice. The bundled demo universe is **synthetic** and labelled as such.

## Repository layout

```
backend/     FastAPI service and the quantitative engine (Python 3.12, uv)
  src/ardentum/quant/     pure, tested financial mathematics
  src/ardentum/data/      data providers, CSV parsing, validation, synthetic demo data
  src/ardentum/services/  orchestration (no maths)
  src/ardentum/api/       HTTP layer: routers, schemas, auth, errors
  migrations/             Alembic migrations (PostgreSQL)
frontend/    Next.js + TypeScript + Tailwind web app, Playwright E2E tests
docs/methodology/   methodology documents (rendered in the app's Research section)
```

Project state and decisions: [ARCHITECTURE.md](ARCHITECTURE.md) ·
[DECISIONS.md](DECISIONS.md) · [PROGRESS.md](PROGRESS.md) · [TODO.md](TODO.md) ·
[CLAUDE.md](CLAUDE.md) · [DEPLOYMENT.md](DEPLOYMENT.md)

## Quick start (local development)

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22.

```bash
# 1. API (SQLite, development sign-in) on http://localhost:8000
cd backend
uv sync
uv run uvicorn ardentum.api.main:create_app --factory --reload --port 8000

# 2. Web app on http://localhost:3000 (proxies /api/v1 to the API)
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000 and choose **Open the workspace**. In development any email
signs you in (no password); production uses Supabase Auth.

Or run the full stack with PostgreSQL in Docker: `docker compose up --build`.

## Tests

```bash
cd backend && uv run pytest -q          # 215 unit/integration tests (94% coverage)
cd backend && uv run ruff check src tests && uv run mypy
cd frontend && npm run lint && npm run typecheck && npm test
cd frontend && npx playwright test      # starts API + web, runs E2E workflows
```

Run the API tests against PostgreSQL with
`ARDENTUM_TEST_DATABASE_URL=postgresql://... uv run pytest tests/api`.

How each calculation is validated (closed forms, SciPy, scikit-learn,
PyPortfolioOpt, brute force, KKT conditions, look-ahead invariance) is documented in
[docs/methodology/09-validation.md](docs/methodology/09-validation.md).

## Configuration

See [backend/.env.example](backend/.env.example) and
[frontend/.env.example](frontend/.env.example). Live market data (Tiingo) and the
FRED risk-free rate are enabled by API keys; check licence terms before commercial use.
