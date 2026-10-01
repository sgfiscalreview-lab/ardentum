# Changelog

All notable changes to Ardentum are recorded here. Versions follow
[Semantic Versioning](https://semver.org/); dates are the GitHub release dates.

## [Unreleased]

### Added
- Classroom kit: a teacher guide with a 45-minute lesson plan and answers (`/classroom`)
  and a printable student worksheet (`/classroom/worksheet`) on the demo data. A backend
  test checks the answers against the API.
- The live smoke test also checks the usage counts and the tour, usage and classroom pages.

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
