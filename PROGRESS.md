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
| 13 | Production deployment | 🟡 artifacts ready | Free-tier stack (D-017): static export for Cloudflare Pages, Cloud Run container, Supabase OAuth, keep-alive; DEPLOYMENT.md step-by-step — **awaiting founder accounts** (TODO) |
| 14 | Research section / docs | ✅ | `docs/methodology/*` rendered at `/research` with KaTeX |
| 15 | Security / performance / a11y / UX audit | ✅ first pass | axe WCAG 2.1 AA tests (light+dark), shared rate limiting, timing, visual review |

## Free-tier extensions (founder-approved plan)

| Item | Status | Evidence |
|---|---|---|
| Real market data: Ken French 12/49 US industries (1926–) with market caps | ✅ | `tests/data/test_kenfrench.py`, `tests/api/test_kenfrench_api.py` |
| PostgreSQL provider cache with stale fallback | ✅ | cache persistence and outage tests |
| Risk-free rate from Fama-French RF or FRED DGS3MO | ✅ | closed-form annualisation and bill-yield tests; API tests |
| Multi-currency universes (ECB rates via Frankfurter, unhedged) | ✅ | identity `(1+r_B)=(1+r_L)(1+r_X)`, gap handling, API conversion check |
| Monte Carlo contributions/withdrawals, depletion probability | ✅ | annuity closed form, brute-force depletion year, expected-wealth identity |
| Black–Litterman estimator with views | ✅ | agreement with PyPortfolioOpt (1e-10), Idzorek confidences, reverse optimisation |
| Minimum-CVaR optimisation (and historical VaR/CVaR on every result) | ✅ | SciPy HiGHS LP, brute-force grid, closed-form CVaR |
| Shared rate limiting (PostgreSQL), verified-user keys, forged-header protection | ✅ | `tests/api/test_ratelimit.py` (SQLite + PostgreSQL) |
| Background jobs with long-polling and recovery of abandoned runs | ✅ | `tests/api/test_jobs.py` |
| Open ESG data from WikiRate (CC BY 4.0): match by ISIN, score, save, apply | ✅ | `tests/data/test_wikirate.py`, `tests/api/test_open_esg_api.py`, `e2e/open-esg.spec.ts` |
| Plain visual design (founder's list of patterns to avoid), real screenshots on the landing page, skeleton loaders | ✅ | CLAUDE.md UI rules, D-027; axe checks on every page in both themes |
| Terms of Service, Privacy Policy, account export and deletion | ✅ | `tests/api/test_account.py`, E2E legal/account flow |
| Founder setup guide (click by click) | ✅ | `docs/SETUP_GUIDE.md` |
| Currency-hedged returns: rolling one-period forward by covered interest parity, BIS policy rates (free, keyless), hedging switch on the Universe page | ✅ | `tests/quant/test_currency_hedged.py` (closed forms, carry, no look-ahead), `tests/data/test_bis.py` (live-format fixtures), `tests/api/test_currency_hedged_api.py` (independent recomputation), E2E |
| Composite open-ESG scores: 2-6 WikiRate metrics, each transformed to 0-100, combined with user weights; assets missing any metric stay unscored | ✅ | `tests/quant/test_esg_composite.py`, `tests/api/test_open_esg_composite_api.py`, E2E composite test |
| Mean-CVaR efficient frontier (historical CVaR, Rockafellar-Uryasev LP), with the mean-variance portfolios measured by the same CVaR; Volatility/CVaR switch on the frontier page | ✅ | `tests/quant/test_cvar_frontier.py` (SciPy HiGHS, brute force, closed form), `tests/api/test_cvar_frontier_api.py`, E2E frontier test |
| Render Blueprint (`render.yaml`, no card) as the recommended API host; keep-alive every 10 minutes | ✅ | D-028; memory measured at 243 MB peak of 512 MB |
| Live smoke test of the deployment (`scripts/smoke.py`, daily workflow); keep-alive defaults to the production API | ✅ | checked locally against a production-mode API and a Pages-like server |
| Legal and compliance review (D-032): Cookie Policy with a clear-settings button, Licences page and generated third-party notices (build fails on undeclared or copyleft licences), Privacy Policy with legal bases, transfers, retention, rights and deletion requests, Terms with age limit and fees/refunds, operator address and registration, age confirmation at sign-in, IP addresses hashed in rate-limit counters, table view for the last chart without one | ✅ | `tests/api/test_ratelimit.py`, E2E legal flow, accessibility checks on the new pages |
| Audit fixes (D-033): phone layout (header, page grids), CORS on unexpected 500s, error and 404 pages, saved-settings upgrade, request timeout with a clear message, pooled HTTP client, SCS time cap, thin-tail CVaR warning, Content-Security-Policy, preview CORS, uptime-monitor docs | ✅ | `e2e/responsive.spec.ts`, `tests/api/test_unexpected_errors.py`, `src/lib/workspace.test.ts`, CVaR tail test; static build checked in Chromium with the policy applied |
| Database URLs copied from Supabase's ORM snippets (`?pgbouncer=true`) accepted | ✅ | `tests/data/test_db_url.py`; migrations checked with such a URL on PostgreSQL |

## Test status
- Backend: 345 tests passing (SQLite); API suite (85 tests) also passing on PostgreSQL 16; 93% line coverage; ruff clean; mypy --strict clean. Migrations 0001–0005 upgrade, `alembic check` and downgrade cleanly on PostgreSQL.
- Frontend: ESLint (incl. React Compiler rules) clean; `tsc --strict` clean; Vitest unit tests passing.
- End-to-end: 44 Playwright tests (14 workflows incl. open ESG data, composite scores, CVaR frontier, currency hedging, legal pages and account deletion, 27 accessibility checks over 13 pages in light and dark, 3 phone-width layout checks) passing; Playwright starts the API, the web app and a local WikiRate stand-in.

## Performance (dev container, 14 assets, 10 years daily)
| Request | Time |
|---|---|
| Optimise (+40 stability resamples) | ~0.5 s |
| ESG impact incl. ESG-efficient frontier | ~0.2 s |
| Walk-forward backtest, monthly re-optimisation, 12 years | 1–2 s |
| Monte Carlo worst case allowed (1e8 path-periods, block bootstrap) | ~4.6 s |

## Not yet verified (requires external access)
- Live calls to Ken French, Frankfurter, WikiRate, FRED and Tiingo (hosts blocked here; adapters tested against the documented/recorded formats).
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

E2E in this container (Playwright's bundled browser is not installed; use the system one):
```bash
cd frontend && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run e2e
```
