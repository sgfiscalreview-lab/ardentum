# Changelog

All notable changes to Ardentum are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); dates are the GitHub release dates.

## [Unreleased]

### Added
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
