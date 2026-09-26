# TODO

Legend: **[F]** needs a founder decision/credential · **[E]** engineering

## Founder decisions (blocking production launch)
- [ ] **[F]** Market-data licence: Tiingo commercial plan vs. alternative vendor (DECISIONS D-004).
- [ ] **[F]** ESG data source: licensed provider (e.g. MSCI, Sustainalytics, LSEG) or user-supplied only.
- [ ] **[F]** Supabase project (URL, JWT keys) and hosting accounts (Vercel + Render/Fly/Cloud Run).
- [ ] **[F]** Domain name, privacy policy and terms of use (financial-information disclaimer).

## Engineering — next
- [ ] **[E]** Deploy to staging once accounts exist; run E2E against staging; manual acceptance pass.
- [ ] **[E]** Verify Docker builds in CI (first run) and live Tiingo/FRED calls with real keys.

## Engineering — backlog
- [ ] Persist Tiingo prices in PostgreSQL (currently in-process LRU cache).
- [ ] FRED risk-free rate selector in the UI (backend client exists).
- [ ] Contributions/withdrawals in Monte Carlo.
- [ ] Shared (edge/Redis) rate limiting for multi-instance deployments (in-process limiter exists).
- [ ] Background jobs for long backtests (currently synchronous; bounded by input limits).
- [ ] Black–Litterman views; CVaR optimisation.
- [ ] Multi-currency support (all data assumed single currency).
