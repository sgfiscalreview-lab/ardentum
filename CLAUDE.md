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
   require a named source. Missing ESG scores are never imputed. Open-data matches are
   by exact identifier (ISIN) or user confirmation, never silent fuzzy matching.
5. **No financial maths in the UI or services.** Frontend formats numbers only; services
   orchestrate only.
6. **Reproducibility.** Simulations take explicit seeds and echo them.

## UI rules (founder request)

* Colours only from the tokens in `frontend/src/app/globals.css`: warm paper and charcoal
  (never pure white or black backgrounds), one navy accent, muted earth-tone chart series.
  No purple, neon, pastel or rainbow palettes; no gradients, orbs or dot-grid backdrops
  (the header's scroll edge uses a fading mask on a blur, which colours nothing).
* Depth and motion follow `.claude/skills/apple-design` (DECISIONS D-041, D-042).
  Translucent materials (`.material`, `.material-thick`) only for floating chrome:
  header, popovers, tooltips, sheets, notices; never one translucent layer on another.
  Elevation from `.elev-1` (cards), `.elev-2` (controls), `.elev-3` (floating layers);
  radii from the `--radius-*` tokens (controls 6px, cards 8 to 12px, sheets 22px). The
  header has no ruled edge, only the scroll edge (`.scroll-edge`). Structural regions
  (the workspace sidebar) are an opaque tint (`bg-sidebar`), not a material.
* Everything that moves uses a spring from `frontend/src/lib/motion.ts`: `SPRING` by
  default (critically damped), `SPRING_SNAPPY` for small selections, `SPRING_MOMENTUM`
  only after a drag or flick. No keyframes or fixed-duration transitions for movement,
  except the 100 ms press scale of `.pressable` / `.pressable-soft`, which gives feedback
  on pointer-down. Popovers grow from their trigger (`PopoverPanel`), their material
  forming as they arrive (`MATERIAL_IN`/`MATERIAL_OUT`), and leave the same way.
  Anything leaving inside AnimatePresence uses `Departing`, so an exit never blocks
  input. Animate only transform and opacity (no height or layout per frame); place a
  value with `jump()`, not `set()`, when it must not carry velocity into the next spring.
  No decorative motion: nothing moves on hover, no animated arrows or chevrons, no
  decorative loops (the busy spinner is the only one); charts render without animation.
  Light and dark switch with a short colour ease (`easeThemeChange`).
* Reduced motion turns movement into fades; reduced transparency and more contrast make
  materials solid (`globals.css`). Keyboard paths for every gesture (arrow keys in
  segmented controls, Escape closes popovers and sheets, focus returns to the opener).
  Small controls get touch margins (`.hit`); pages pass axe WCAG 2.2 AA (target size
  included) at desktop and phone widths. Review new motion frame by frame (record the
  element's position on every animation frame) before shipping it.
* Forgiveness over confirmation: an action that replaces the user's settings keeps a way
  back (the notice after a shared link or a starting example); confirm only what cannot
  be undone (deleting a saved portfolio or the account). Disabled actions say why, next
  to the button.
* No icon sets (e.g. Lucide), emojis, sparkle icons, checkmark bullets or arrow glyphs;
  use words. No em dashes in user-facing text (backend messages and methodology docs
  included); missing values display as "n/a".
* Operating-system fonts only (`--font-sans`, also for titles); the `.type-*` classes set
  size-specific tracking (negative for large text, slightly positive for captions).
  Text sizes in rem so they follow the reader's text-size setting: `text-2xs`,
  `text-caption2`, `text-caption1`, `text-footnote`, `text-subheadline` or Tailwind's
  sizes, never `text-[13px]`. Never Inter, Geist or Space Grotesk.
* No feature-card rows, bento grids, terminal windows, testimonials or pricing tables.
  Show the real product (`npm run screenshots` in `frontend/` with the app running
  captures the landing-page screenshots) and plain statements; avoid "it's not X, it's Y"
  copy.
* Loading states use static skeletons (`Skeleton`, `SkeletonRows`, `ResultsSkeleton`).
* Every page links the Terms of Service and Privacy Policy (site footer).

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
npm run dev            # http://localhost:3000; proxies /api/v1 to API_URL (default http://localhost:8000)
NEXT_OUTPUT=export NEXT_PUBLIC_API_BASE=https://<api> npm run build   # static site in out/ (automatic on Cloudflare Pages, CF_PAGES=1); fails fast on missing/malformed NEXT_PUBLIC_* addresses
npm run gen:api        # regenerate src/lib/api/schema.d.ts from the running backend
npm run lint && npm run typecheck && npm test
npm run build
npm run e2e            # Playwright (starts backend, frontend and a WikiRate stand-in)
# in the dev container: PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run e2e
```

Local PostgreSQL (dev container): `initdb` + `pg_ctl -o '-p 5433'` (see PROGRESS.md notes).

## Conventions

* Rates/weights are decimals (0.05 = 5%). Returns/vols annualised unless named otherwise.
* 252/52/12 periods per year (DECISIONS D-006).
* New objective or constraint ⇒ add: closed-form or independent test, KKT/verification
  test, API schema field, explanation text, methodology doc update.
* New table ⇒ enable row-level security in its migration (Supabase publishes the `public`
  schema; `tests/api/test_db_lockdown.py` fails otherwise). Security overview: `SECURITY.md`.
* Error messages are user-facing: state what is wrong and how to fix it.
* Keep `DECISIONS.md` (why), `PROGRESS.md` (what's done), `TODO.md` (what's next) current.
* Commit messages end with the session attribution lines.
