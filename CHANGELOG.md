# Changelog

All notable changes to Ardentum are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); dates are the GitHub release dates.

## [Unreleased]

### Added
- Backtests with ESG constraints or a tilt use only the ESG scores known at each
  rebalance: dated uploads and WikiRate overlays keep a score per year, each counted from
  30 June of the next year. When some score was not yet known at the start, the backtest
  says which and from when, and applies today's scores.
- On histories of up to 1,000 returns, the strategy-versus-benchmark Sharpe test is
  checked by a bootstrap (Ledoit and Wolf's studentized block bootstrap) with a fixed,
  echoed seed.
- How sure is a Sharpe ratio: every one now comes with a 95% interval, and a backtest
  tests whether the strategy really beat its benchmark, with the p-value in plain words.
  Both allow for fat tails and autocorrelation (Ledoit and Wolf, 2008).
- An upload says which return frequencies its prices support and switches to one of them;
  prices coarser than monthly are refused at upload.
- The API reports the commit it was built from; the live check flags a stale deploy.
- Crisis replay: a portfolio bought before each of seven crashes since 1929 and held,
  with its return against the market, largest fall, worst day, each holding's
  contribution and how long it took to get back to its previous high. Real data; any
  period you choose also works on demo data.
- Factor exposure: the Fama-French three-factor model (market, size, value) for any
  portfolio on real data, with Newey-West standard errors, the split of the average
  return into factors and alpha, and each holding's loadings.
- Trade list: the purchases and sales, with costs, that move what you hold now to a
  target portfolio, adding or withdrawing money on the way.
- Four starting examples on the Universe page that open a finished result in one click.
- Risk parity (equal risk contribution) objective: every holding carries the same share of
  risk, using no expected returns; usable in walk-forward backtests.
- "Copy link" on every workspace page: a link that reopens the same settings and
  recomputes the same result in any browser, with nothing stored on a server.
- Glossary of the terms on the site (`/glossary`), linked from result labels.
- Printing a workspace page prints its results without menus and settings.
- A notice while the free API server starts after a quiet period; pages wake it early.
- Classroom kit: a teacher guide with a 45-minute lesson plan and answers (`/classroom`)
  and a printable student worksheet (`/classroom/worksheet`) on the demo data. A backend
  test checks the answers against the API.
- The live smoke test also checks the usage counts and the tour, usage and classroom pages.

### Changed
- The interface design is complete against the apple-design skill: on phones the page
  steps back behind the steps sheet, which can be caught while closing and starts to
  move only after a 10 px drag; popovers and notices form as they arrive and never block
  clicks while leaving; the server notice floats instead of pushing the page down; the
  header edge softens instead of showing a line; light and dark ease into each other;
  text sizes follow the browser's text-size setting; small controls get touch margins;
  starting from an example can be undone; disabled buttons say why.
- Redesigned interface after Apple's fluid-interface guidance: a translucent header that
  content scrolls under, soft depth and rounder corners, spring motion that can be
  interrupted, press feedback, sliding segmented controls, popovers that grow from their
  button, and on phones a bottom sheet for the workspace steps that follows the finger
  and closes with a flick. Reduced motion, reduced transparency and higher contrast
  settings are respected. Titles use the system sans; landing screenshots retaken.
- The optimiser's reason for each holding sits in a full-width row under it, readable on
  phones; long calculations show elapsed seconds.
- Dependabot opens at most two pull requests per ecosystem a month and no longer bumps
  the Docker base images.
- Website tooling on ESLint 10, Vitest 5 and jsdom 30. TypeScript stays on 5.9 until
  typescript-eslint and openapi-typescript support TypeScript 7; the unused
  `@testing-library/jest-dom` was removed.
- The live smoke test also loads the glossary page.
- Choosing a real industry dataset lists its industries to pick from (it showed a ticker
  box meant for live data).
- Browser tests serve the Kenneth French files from a local stand-in.

### Fixed
- The API stopped answering after the last deploy: its image ran a Python version the
  project does not support. It runs on the tested version again, and CI now starts the
  image the way the host does, also after a restart, before anything is merged.
- Daily returns from weekly or monthly prices, or on calendar days, are refused instead of
  being annualised with the wrong number of periods; an unfinished last week or month is
  left out of weekly and monthly returns.
- Backtests with Black-Litterman market-capitalisation priors used today's
  capitalisations at every past rebalance; they now use those known at the time.
- One constant series no longer blanks the whole correlation matrix; undefined risk
  contributions and Compare figures show n/a with the reason instead of zero.
- Holdings explanations use the ESG-adjusted returns when a tilt is on, and name the
  binding constraint when it, not return and risk, keeps an asset out.
- A very wide CSV, many background jobs at once or a malformed provider download can no
  longer take the API down or break it for a day.
- Two requests at a first sign-in, account deletion leaving rate-limit counters, and dates
  outside 1900 to 2100 no longer cause errors or leftovers.
- Monte Carlo amounts are shown in the data's currency, and its assumptions say values
  are nominal and inputs come from the same window.
- Landing-page screenshots showed doubled frames, mismatched corners and a card cut off
  at the bottom; they now show whole cards with their own edges only. Nested panels
  use concentric corners.
- Opening the steps sheet on a phone flung it far past the top of the screen before it
  settled.
- Wide formulas on the methodology pages can be scrolled with the keyboard on phones.

### Security
- The database is closed to Supabase's public Data API: row-level security on every table
  and no access for its public roles, including on tables created later (migration 0007).
  Before this, anyone with the website's public key could read and change the tables.
- A second rate limit covers saves, uploads, deletions, sign-in and WikiRate lookups;
  rate-limited answers now reach the browser with their message.
- Request bodies are capped (1 MB; uploads 10 MB), as are saved settings (64 KB) and saved
  ESG overlays (100 per user).
- Security headers on the API (HSTS, Content-Security-Policy, cross-origin policies) and
  more on the website; developer sign-in no longer exists in production.
- CSV exports cannot carry spreadsheet formulas; outside links must be http(s); the sign-in
  page's return address only accepts paths on the site.
- Secret scanning of every commit (gitleaks), a build check for secret keys in browser
  files, weekly dependency audits and Dependabot updates. `SECURITY.md` explains how to
  report a problem and how each part is protected.
- Updated dependencies (FastAPI 0.142, Next.js 16.3.8, cryptography 50.0.2 and others);
  removed three unused frontend packages.

## [1.0.0]

First public release. The full release notes are in
[docs/releases/v1.0.0.md](docs/releases/v1.0.0.md).

### Portfolio construction
- Optimisation: minimum volatility, maximum Sharpe (exact convex reformulation),
  target return or volatility, mean-variance utility and minimum CVaR (historical,
  Rockafellar-Uryasev linear programme).
- Constraints: position bounds, exclusions, sector limits, gross exposure, tracking
  error, minimum ESG score and ESG preference. Solver output is checked against every
  constraint; infeasible problems are reported with the reason and a suggested fix.
- Estimation: historical and Bayes-Stein means, sample and Ledoit-Wolf covariance,
  Black-Litterman views with Idzorek confidences.
- Efficient frontiers: mean-variance, ESG-efficient and mean-CVaR.
- Explanations: why each holding is in the portfolio, binding constraints (KKT),
  risk decomposition and weight stability under resampling.

### Simulation and testing
- Seeded Monte Carlo (parametric, bootstrap, stationary block bootstrap) with
  contributions, withdrawals and the probability of running out of money.
- Walk-forward backtests with transaction costs and no look-ahead; Cariño-linked and
  Brinson-Fachler attribution; side-by-side portfolio comparison.

### Data
- Real US industry returns from the Kenneth R. French Data Library (from 1926),
  with the Fama-French T-bill or FRED three-month yield as the risk-free rate.
- Multi-currency universes at ECB reference rates, unhedged or hedged with a rolling
  one-month forward priced by covered interest parity from BIS policy rates.
- Open ESG scores from WikiRate (CC BY 4.0), matched by ISIN only, with composite
  scores from several metrics; missing scores are never filled in.
- CSV uploads with validation, and a labelled synthetic demo universe.

### Platform
- Accounts with Google sign-in, saved portfolios, CSV and JSON export, account export
  and deletion.
- Methodology section with the formulas, assumptions and references behind each
  calculation.
- Terms of Service, Privacy Policy, Cookie Policy and Licences pages; IP addresses are
  hashed in rate-limit counters.
- A guided tour of eight steps on the demo data, with no sign-in.
- Public, anonymous usage counts (calculations, saves and exports per day, nothing about
  who), shown on the Usage page.
- Accessible (WCAG 2.1 AA checks in light and dark themes) and usable at phone width.

### Research
- Three reproducible studies built on the engine (`research/`): the 1/N puzzle out
  of sample, dollar hedging for euro and sterling investors, and promised versus
  realised Sharpe ratios, with robust (HAC) Sharpe-ratio tests. A workflow reruns them
  on the latest public data.

### Quality
- About 350 backend tests (known answers, SciPy, scikit-learn, PyPortfolioOpt, brute
  force, KKT conditions, look-ahead invariance), API tests on PostgreSQL, and 52
  end-to-end browser tests.

[1.0.0]: https://github.com/sgfiscalreview-lab/ardentum/releases/tag/v1.0.0
