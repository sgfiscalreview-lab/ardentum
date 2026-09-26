# TODO

Legend: **[F]** needs a founder decision/credential · **[E]** engineering

## Founder decisions (blocking production launch)
- [x] **[F]** Market data: free Ken French industry data built in (D-018). Tiingo/other licensed vendors remain optional for individual securities (D-004).
- [ ] **[F]** Confirm Ken French Data Library terms with Prof. French before commercial launch (D-018).
- [x] **[F]** ESG data source: user-supplied plus open WikiRate data (CC BY 4.0, D-026). A licensed provider remains optional.
- [ ] **[F]** Create free accounts and follow DEPLOYMENT.md: Supabase (+ Google/GitHub OAuth apps), Google Cloud (Cloud Run, $1 budget alert), Cloudflare Pages; set the `API_URL` Actions variable.
- [ ] **[F]** Optional free keys: FRED API key; WikiRate account (only if its API requires a key).
- [ ] **[F]** Optional domain (~$10/yr, Cloudflare Registrar); privacy policy and terms of use (financial-information disclaimer, CC BY 4.0 attribution for WikiRate data).

## Engineering — next
- [ ] **[E]** Deploy to staging once accounts exist; run E2E against staging; manual acceptance pass.
- [ ] **[E]** Verify Docker builds in CI (first run) and live calls to Ken French, Frankfurter, WikiRate and FRED from the deployed API.

## Engineering — backlog
- [x] Persist provider payloads (Ken French, Tiingo, FRED, FX) in PostgreSQL (D-019).
- [x] Risk-free rate from Fama-French RF or FRED DGS3MO, selectable in the UI (D-020).
- [x] Contributions/withdrawals and depletion probability in Monte Carlo.
- [x] Shared rate limiting across instances via PostgreSQL (D-024).
- [x] Background jobs with long-polling for long calculations (D-025).
- [x] Black–Litterman views (D-022); minimum-CVaR optimisation (D-023).
- [ ] Mean-CVaR efficient frontier.
- [ ] Open ESG overlays from several metrics combined into one composite score (weights chosen by the user).
- [x] Multi-currency universes, unhedged conversion at ECB rates (D-021).
- [ ] Currency-hedged returns (needs a free source of forward points or daily interest differentials).
