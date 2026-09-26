# CLAUDE.md — working agreement for Ardentum

Read this first, then `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`, `TODO.md`.

## Non-negotiables

1. **Correctness over demos.** Every financial calculation lives in
   `backend/src/ardentum/quant/` and has tests with known answers or independent
   references (closed form, SciPy, scikit-learn, PyPortfolioOpt, brute force, KKT).
2. **No silent failures.** Undefined metrics return `None` with a reason; infeasible
   problems raise `InfeasibleProblemError` with an actionable message; solver output
   is verified against all constraints.
3. **No look-ahead.** Backtest strategies receive only the trailing window; keep the
   invariance test green.
4. **No invented data.** Demo data is synthetic, `.SYN`-suffixed and labelled. ESG scores
   require a named source. Missing ESG scores are never imputed.
5. **No financial maths in the UI or services.** Frontend formats numbers only; services
   orchestrate only.
6. **Reproducibility.** Simulations take explicit seeds and echo them.

## Commands

Backend (from `backend/`):
```bash
uv sync                                   # install
uv run pytest -q                          # all tests (SQLite)
ARDENTUM_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/ardentum_test uv run pytest -q tests/api
uv run ruff format src tests && uv run ruff check src tests
uv run mypy                               # strict
uv run uvicorn ardentum.api.main:create_app --factory --reload --port 8000
ARDENTUM_DATABASE_URL=... uv run alembic upgrade head
```

Frontend (from `frontend/`):
```bash
npm ci
npm run dev            # http://localhost:3000 (expects API at NEXT_PUBLIC_API_URL)
npm run gen:api        # regenerate src/lib/api/schema.d.ts from the running backend
npm run lint && npm run typecheck && npm test
npm run build
npm run e2e            # Playwright (starts backend + frontend)
```

Local PostgreSQL (dev container): `initdb` + `pg_ctl -o '-p 5433'` (see PROGRESS.md notes).

## Conventions

* Rates/weights are decimals (0.05 = 5%). Returns/vols annualised unless named otherwise.
* 252/52/12 periods per year (DECISIONS D-006).
* New objective or constraint ⇒ add: closed-form or independent test, KKT/verification
  test, API schema field, explanation text, methodology doc update.
* Error messages are user-facing: state what is wrong and how to fix it.
* Keep `DECISIONS.md` (why), `PROGRESS.md` (what's done), `TODO.md` (what's next) current.
* Commit messages end with the session attribution lines.
