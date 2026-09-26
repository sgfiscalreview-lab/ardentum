# Progress

Status as of 2026-09-26.

| Phase | Area | Status | Evidence |
|---|---|---|---|
| 1 | Architecture, tooling, project docs | ✅ | ARCHITECTURE.md, DECISIONS.md, CLAUDE.md |
| 2 | Market-data layer | ✅ (live providers need keys/licence) | `backend/tests/data/*` |
| 3 | Portfolio mathematics | ✅ | `tests/quant/test_returns.py`, `test_metrics.py`, `test_portfolio.py`, `test_estimation.py` |
| 4 | Optimisation engine | ✅ | `tests/quant/test_optimisation.py` (closed form, SLSQP, PyPortfolioOpt, brute force, KKT) |
| 5 | Efficient frontier | ✅ | frontier properties + Merton hyperbola tests |
| 6 | Portfolio dashboard | ✅ | Next.js workspace (8 steps); E2E `frontend/e2e/workflows.spec.ts` |
| 7 | Monte Carlo | ✅ | analytic-moment, reproducibility and block-structure tests; UI fan chart |
| 8 | Backtesting + attribution | ✅ | manual replication, look-ahead invariance, Cariño/Brinson identities |
| 9 | ESG constraints | ✅ | optimisation ESG tests, API ESG-impact tests, E2E ESG flow |
| 10 | Portfolio comparison | ✅ | API + E2E compare tests (in-sample warning) |
| 11 | Explainability | ✅ | `tests/quant/test_explain.py`; holdings reasons, binding constraints, stability |
| 12 | Auth + saved portfolios | ✅ | Supabase JWT tests, ownership isolation, E2E save/export/delete |
| 13 | Production deployment | 🟡 artifacts ready | Dockerfiles, docker-compose, CI, DEPLOYMENT.md — **awaiting founder accounts** (TODO) |
| 14 | Research section / docs | ✅ | `docs/methodology/*` rendered at `/research` with KaTeX |
| 15 | Security / performance / a11y / UX audit | ✅ first pass | axe WCAG 2.1 AA tests (light+dark), rate limiting, timing, visual review |

## Test status
- Backend: 218 tests passing (SQLite); API suite also passing on PostgreSQL 16; 94% line coverage; ruff clean; mypy --strict clean.
- Frontend: ESLint (incl. React Compiler rules) clean; `tsc --strict` clean; Vitest unit tests passing.
- End-to-end: 20 Playwright tests (9 workflows + 11 accessibility checks) passing, servers started by Playwright.

## Performance (dev container, 14 assets, 10 years daily)
| Request | Time |
|---|---|
| Optimise (+40 stability resamples) | ~0.5 s |
| ESG impact incl. ESG-efficient frontier | ~0.2 s |
| Walk-forward backtest, monthly re-optimisation, 12 years | 1–2 s |
| Monte Carlo worst case allowed (1e8 path-periods, block bootstrap) | ~4.6 s |

## Not yet verified (requires external access)
- Live Tiingo/FRED calls (hosts blocked here; adapters tested against documented response shapes).
- Docker image builds (no Docker daemon here; the CI `docker` job builds both images).
- Production deployment on real infrastructure (needs founder accounts).

## Environment notes
Local PostgreSQL for tests:
```bash
PGDIR=/tmp/pgdata-ardentum; mkdir -p $PGDIR && chown postgres:postgres $PGDIR
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDIR -A trust -U postgres"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDIR -o '-p 5433 -k /tmp' -l $PGDIR/log start"
psql -h /tmp -p 5433 -U postgres -c "CREATE DATABASE ardentum_test;"
```
