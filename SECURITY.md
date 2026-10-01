# Security

## Reporting a vulnerability

Please report security problems privately through GitHub: open the repository's
**Security** tab and choose **Report a vulnerability**. Do not open a public issue. Reports
are acknowledged within a week. Only the latest release is supported.

## How Ardentum is protected

Each item names where it lives, so it can be checked. Decision record: DECISIONS.md D-038.

| Area | What is in place | Where |
|---|---|---|
| Database access | The API is the only way in. Every table has row-level security, and Supabase's public Data API roles have no access to any table, including future ones. A test recreates Supabase's grants and checks every table; the live smoke test asks the Data API for each table and fails if one answers. Production connections to a remote database require TLS. | `backend/migrations/versions/0007_close_public_data_api.py`, `tests/api/test_db_lockdown.py`, `db/session.py` |
| Authentication | Sign-in is handled by Supabase (Google and GitHub); the API never sees a password, so there are none to hash. The API verifies each token's signature (published ES256 keys), expiry, audience and issuer. Developer sign-in exists only in local development: production settings refuse it and the route is not registered. | `api/auth.py`, `config.py`, `tests/api/test_supabase_auth.py`, `test_security_headers.py` |
| Access to your data | Portfolios, datasets, ESG overlays, background jobs and account exports belong to one user. Every other caller gets "not found", whichever route they try. | `tests/api/test_access_control.py`, `test_jobs.py`, `test_open_esg_api.py` |
| Admin routes | There are none. Administration happens in the Supabase, Render and Cloudflare dashboards, behind their own sign-in. The API documentation (`/api/v1/docs`) is public on purpose: it describes the public API only. | `api/main.py` |
| Rate limiting | Two budgets per user or (hashed) address each minute: 60 calculations, and 60 writes or outside lookups (saves, uploads, deletions, sign-in, WikiRate). Shared across instances in PostgreSQL; forged forwarding headers do not help. | `api/ratelimit.py`, `tests/api/test_ratelimit.py`, `test_request_limits.py` |
| Input checks | Every request field has a type and bounds (Pydantic, unknown fields refused). Request bodies are capped at 1 MB (uploads: two files of 5 MB). Uploaded CSV files are parsed as data with row, column and size limits. Saved settings are capped at 64 KB, and each user has caps on portfolios, datasets and overlays. | `api/schemas.py`, `api/bodylimit.py`, `data/providers/csv_upload.py` |
| Cross-site scripting | React escapes all text; nothing renders user or outside HTML. Links from outside data (WikiRate) are kept only if they are http(s). The sign-in page returns only to paths on this site. A Content-Security-Policy limits scripts to the site itself. | `data/providers/wikirate.py`, `frontend/src/lib/redirect.ts`, `frontend/scripts/csp-policy.mjs` |
| Spreadsheet formulas | CSV exports write text that starts like a formula (=, +, -, @) as plain text, so a company name from an outside source cannot run in a spreadsheet. | `frontend/src/lib/csv.ts` |
| CORS | Only the website (and its preview builds, by an anchored pattern) may call the API from a browser; no credentials mode; a wildcard is refused in production. Refusals (429, 413, 500) still carry CORS headers so the browser shows their message. | `api/main.py`, `config.py`, `tests/api/test_request_limits.py` |
| Security headers | API: HSTS, a Content-Security-Policy that lets answers run nothing, nosniff, frame denial, no referrer, Cross-Origin-Resource and Opener policies, no caching of API answers, no server name. Website: HSTS, Content-Security-Policy, nosniff, frame denial, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-Policy. The live smoke test checks both. | `api/main.py`, `frontend/public/_headers`, `frontend/next.config.ts`, `scripts/smoke.py` |
| Errors and debug mode | No debug mode in production: unexpected errors return a generic message with a reference, and the details go only to the server log. The production settings check refuses development sign-in, SQLite and wildcard CORS. | `api/errors.py`, `config.py` |
| Secrets and API keys | Secrets live only in the hosts' settings (Render, Cloudflare, GitHub), never in the code. CI scans every commit with gitleaks; the build fails if a secret key reaches the files sent to browsers; the live smoke test checks the website's code too. `.env` files are ignored by Git and Docker. The website's Supabase key is the publishable one, which is public by design. | `.gitleaks.toml`, `.github/workflows/ci.yml`, `frontend/scripts/check-client-secrets.mjs`, `.gitignore`, `.dockerignore` |
| Exposed files | The website is a static export of built pages only (no source maps, no `.env`). The API serves only its routes; the container holds the installed package and migrations, runs as an unprivileged user, and excludes tests, local databases and env files. | `frontend/next.config.ts`, `backend/Dockerfile`, `.dockerignore` |
| Dependencies | Locked versions (uv.lock, package-lock.json). Weekly audits (pip-audit, npm audit) and Dependabot updates each month, with security fixes raised as soon as they are published. Unused packages are removed. | `.github/workflows/audit.yml`, `.github/dependabot.yml` |
| Privacy | No tracking or cookies. The API's request log leaves out client addresses; rate-limit counters hold them only as keyed hashes that change daily; usage counts are anonymous daily totals. | Privacy Policy, `api/ratelimit.py`, `services/usage.py`, `backend/docker-entrypoint.sh` |

## Settings outside the code (owner checklist)

These live in the hosts' dashboards, so they are not visible in the repository. Check them
once, and again after any change of account or host.

- [ ] **GitHub** > Settings > Code security: turn on **Private vulnerability reporting**,
  **Dependabot alerts**, **Dependabot security updates**, **Secret scanning** and **Push
  protection**.
- [ ] **GitHub** > Settings > Branches: protect `main` (pull requests and passing CI
  before merging).
- [ ] **Supabase** > Advisors > Security Advisor: no errors (after migration 0007 is
  deployed, "RLS disabled in public" should be gone).
- [ ] **Supabase** > Authentication > URL Configuration: only the website's addresses in
  Redirect URLs.
- [ ] **Accounts**: two-factor sign-in on GitHub, Supabase, Render, Cloudflare and Google.
- [ ] **If a secret was ever shared** (in a chat, an email or an issue): rotate it. That
  means the Supabase database password (then update `ARDENTUM_DATABASE_URL` on Render),
  the Supabase secret key, and the Google and GitHub OAuth client secrets (then update
  them in Supabase).
