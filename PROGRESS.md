# Progress

Status as of 2026-09-26.

| Phase | Area | Status | Evidence |
|---|---|---|---|
| 1 | Architecture, tooling, project docs | ✅ | ARCHITECTURE.md, DECISIONS.md, CLAUDE.md |
| 2 | Market-data layer | ✅ (live providers need keys) | `tests/data/*` (demo determinism, CSV parsing, validation, mocked Tiingo/FRED) |
| 3 | Portfolio mathematics | ✅ | `tests/quant/test_returns.py`, `test_metrics.py`, `test_portfolio.py`, `test_estimation.py` |
| 4 | Optimisation engine | ✅ | `tests/quant/test_optimisation.py` (closed form, SLSQP, PyPortfolioOpt, brute force, KKT) |
| 5 | Efficient frontier | ✅ | frontier properties + Merton hyperbola tests |
| 6 | Portfolio dashboard (UI) | ⏳ | — |
| 7 | Monte Carlo | ✅ backend | `tests/quant/test_montecarlo.py` (analytic moments, seeds, autocorrelation) |
| 8 | Backtesting + attribution | ✅ backend | `tests/quant/test_backtest.py` (manual replication, look-ahead invariance), `test_attribution.py` |
| 9 | ESG constraints | ✅ backend | ESG tests in optimisation suite + API ESG-impact tests |
| 10 | Portfolio comparison | ✅ backend | `tests/api/test_api_core.py::test_compare` |
| 11 | Explainability | ✅ backend | `tests/quant/test_explain.py` |
| 12 | Auth + saved portfolios | ✅ backend | `tests/api/test_api_auth_portfolios.py`, `test_supabase_auth.py` |
| 13 | Production deployment | ⏳ | — |
| 14 | Research section / docs | ⏳ | — |
| 15 | Final audit | ⏳ | — |

## Test status
Backend: 214 tests passing (SQLite); API suite also passing on PostgreSQL 16.
ruff clean; mypy --strict clean.

## Environment notes
* Outbound access to market-data hosts (Tiingo, FRED, Yahoo, Stooq) is blocked in the
  development container, so live adapters are tested against recorded response shapes.
* Local PostgreSQL for tests:
  ```bash
  PGDIR=/tmp/pgdata-ardentum; mkdir -p $PGDIR && chown postgres:postgres $PGDIR
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDIR -A trust -U postgres"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDIR -o '-p 5433 -k /tmp' -l $PGDIR/log start"
  psql -h /tmp -p 5433 -U postgres -c "CREATE DATABASE ardentum_test;"
  ```
