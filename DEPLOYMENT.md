# Deployment (free tier)

Technical reference. For click-by-click instructions (accounts, keys, OAuth apps, Cloud
Shell commands, troubleshooting) follow [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

Approved topology (DECISIONS D-017). Every component has a free tier; the only possible
cost is an optional domain name.

| Component | Host | Free-tier notes (check current terms) |
|---|---|---|
| Web app (static) | **Cloudflare Pages** (fallback: Netlify) | Static files, unlimited bandwidth, 500 builds/month |
| API (container) | **Render** free web service via `render.yaml` (no card), or **Google Cloud Run** | Render: 512 MB, small CPU share, sleeps after 15 idle minutes (the keep-alive prevents it). Cloud Run: ~2M requests, 180k vCPU-s, 360k GiB-s per month; card required, budget alert recommended |
| PostgreSQL + sign-in | **Supabase** | 500 MB database; pauses after 7 idle days (prevented by the keep-alive) |
| Keep-alive | GitHub Actions (`.github/workflows/keepalive.yml`) | `GET /api/v1/health/db` every 5 minutes |
| Data | Built in, no keys | Ken French industries and risk-free rate, ECB FX (Frankfurter), WikiRate open ESG data |
| Optional keys | FRED (free), WikiRate (free account) | Only needed for FRED's T-bill series, or if WikiRate requires a key |
| Optional domain | Cloudflare Registrar | About $10/year for a `.com` |

Order: Supabase → API → web app → OAuth redirect URLs → keep-alive → verify.

## 1. Supabase (database and sign-in)

1. Create a free project at supabase.com; choose the region closest to your users and
   note the database password.
2. **Project Settings → API Keys** (tab *Publishable and secret API keys*): copy the
   **publishable key** (`sb_publishable_...`, for the web app) and a **secret key**
   (`sb_secret_...`, optional, lets account deletion also remove the sign-in record). The
   project URL is `https://<ref>.supabase.co`.
3. **Connect → Transaction pooler**: copy the connection string (port **6543**):
   `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`.
   The API disables server-side prepared statements, so the transaction pooler is safe.
   ORM-only options such as Prisma's `?pgbouncer=true` are dropped before connecting.
4. **Authentication → Providers**:
   - **Google**: in Google Cloud Console → APIs & Services → Credentials, create an
     *OAuth client ID* (Web application) with authorised redirect URI
     `https://<ref>.supabase.co/auth/v1/callback`; paste the client ID and secret into
     Supabase.
   - **GitHub**: GitHub → Settings → Developer settings → OAuth Apps → New, with callback
     URL `https://<ref>.supabase.co/auth/v1/callback`; paste the ID and secret.
   - Email/password is optional (set `NEXT_PUBLIC_AUTH_EMAIL_ENABLED=true` on the web app
     to show it). OAuth avoids handling password resets and email delivery.
5. **Authentication → URL Configuration**: set *Site URL* to the web app URL (step 3) and
   add it to *Redirect URLs* (also `http://localhost:3000/**` for local testing).

The API verifies Supabase tokens with the project's JWKS
(`<URL>/auth/v1/.well-known/jwks.json`); legacy HS256 projects also need
`ARDENTUM_SUPABASE_JWT_SECRET`.

## 2. API on Google Cloud Run or Render

One-time setup (Google Cloud Console or `gcloud`):

1. Create a project and link billing (Cloud Run's free tier still needs an account).
   **Billing → Budgets & alerts → Create budget**: $1, alerts at 50/90/100%.
2. Enable **Cloud Run**, **Cloud Build** and **Artifact Registry**.
3. Create `cloudrun.env.yaml` (not committed; it holds no secrets, but keep it local):

```yaml
ARDENTUM_ENV: production
ARDENTUM_AUTH_MODE: supabase
ARDENTUM_SUPABASE_URL: https://<ref>.supabase.co
ARDENTUM_CORS_ORIGINS: '["https://<project>.pages.dev"]'
ARDENTUM_TRUSTED_PROXY_HOPS: "1"
ARDENTUM_RATE_LIMIT_STORE: database
WEB_CONCURRENCY: "1"
```

4. Deploy from source (the `backend/Dockerfile` is used):

```bash
gcloud run deploy ardentum-api --source backend --region europe-west1 \
  --allow-unauthenticated --min-instances 0 --max-instances 2 \
  --cpu 1 --memory 1Gi --concurrency 20 --timeout 60 \
  --env-vars-file cloudrun.env.yaml \
  --set-secrets "ARDENTUM_DATABASE_URL=ardentum-db-url:latest,ARDENTUM_SUPABASE_SERVICE_KEY=ardentum-supabase-secret:latest"
```

Create the secret first: **Secret Manager → Create secret** `ardentum-db-url` with the
pooler URL from step 1.3, and grant the Cloud Run service account *Secret Accessor*.

| Variable | Value |
|---|---|
| `ARDENTUM_ENV` | `production` (enforces Supabase auth, PostgreSQL and explicit CORS) |
| `ARDENTUM_DATABASE_URL` | Supabase transaction-pooler URL (secret) |
| `ARDENTUM_AUTH_MODE` / `ARDENTUM_SUPABASE_URL` | `supabase` / project URL |
| `ARDENTUM_CORS_ORIGINS` | `["https://<project>.pages.dev"]` plus any custom domain (a plain comma-separated list also works; trailing slashes are ignored) |
| `ARDENTUM_CORS_ORIGIN_REGEX` | optional, for preview deployments, e.g. `^https://[a-z0-9-]+\.<project>\.pages\.dev$` |
| `ARDENTUM_TRUSTED_PROXY_HOPS` | `1` on Cloud Run and Render (client IP for rate limits); `2` behind an extra load balancer |
| `ARDENTUM_RATE_LIMIT_STORE` | `database`: limits shared by all instances |
| `WEB_CONCURRENCY` | `1` per vCPU |
| `ARDENTUM_FRED_API_KEY` | optional (free at fred.stlouisfed.org) |
| `ARDENTUM_WIKIRATE_API_KEY` | optional (free WikiRate account) |
| `ARDENTUM_TIINGO_API_KEY` | optional; commercial use needs a paid licence (D-004) |

The container runs `alembic upgrade head` on start (`ARDENTUM_SKIP_MIGRATIONS=1` disables
it). Health checks: `/api/v1/health` (process) and `/api/v1/health/db` (database).

Long calculations run as background jobs that are long-polled by the browser (D-025).
Cloud Run's request-based billing only allocates CPU while a request is open, and the
polls keep one open, so no "CPU always allocated" setting (which costs money) is needed.
Keep `--timeout` above 25 s.

**Without a card: Render** (D-028). Dashboard → New → Blueprint → this repository.
`render.yaml` defines the free Docker service (region Singapore, health check
`/api/v1/health`, deploys each commit on `main` that changes `backend/`) and the fixed
variables; Render asks once for `ARDENTUM_SUPABASE_URL`, `ARDENTUM_CORS_ORIGINS`,
`ARDENTUM_DATABASE_URL` and `ARDENTUM_SUPABASE_SERVICE_KEY`. Free instances sleep after 15
idle minutes (the first request then takes about a minute); the keep-alive below pings
every 5 minutes. Peak memory with one worker is about 250 MB of the 512 MB.

## 3. Web app on Cloudflare Pages

Workers & Pages → Create → Pages → Connect to Git → this repository:

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Output directory | `out` |
| `NEXT_OUTPUT` | `export` (static export; automatic when `CF_PAGES=1`, i.e. on Cloudflare Pages) |
| `NEXT_PUBLIC_API_BASE` | Cloud Run URL, e.g. `https://ardentum-api-xxxxx.a.run.app` |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | from step 1.2 (the legacy `NEXT_PUBLIC_SUPABASE_ANON_KEY` also works) |
| `NEXT_PUBLIC_LEGAL_OPERATOR`, `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL`, `NEXT_PUBLIC_LEGAL_GOVERNING_LAW`, `NEXT_PUBLIC_LEGAL_LAST_UPDATED` | shown in the Terms of Service, Privacy Policy and site footer |
| `NEXT_PUBLIC_LEGAL_ADDRESS`, `NEXT_PUBLIC_LEGAL_REGISTRATION` | optional postal address and company registration, shown with the operator name |
| `NODE_VERSION` | `22` |

The build reads `../docs/methodology` for the Research section (the whole repository is
checked out). Security headers are in `frontend/public/_headers`. Add the Pages URL to
`ARDENTUM_CORS_ORIGINS` and to Supabase's Site URL and Redirect URLs.

**Netlify fallback:** base directory `frontend`, build `npm run build`, publish `out`,
with the same variables (copy `public/_headers` rules to Netlify headers if needed).

A Node-server deployment (for example `frontend/Dockerfile`, which proxies `/api/v1`)
remains possible but is not needed for the free stack.

## 4. Keep-alive

GitHub → repository → Settings → Secrets and variables → Actions → **Variables** → add
`API_URL` = the Render or Cloud Run URL. The `keepalive` workflow pings `/api/v1/health/db`
every 5 minutes, which keeps the Supabase project from pausing and a Render free instance
from sleeping.

## 5. Optional custom domain

Cloudflare → Domain Registration → register a domain (at-cost). Then Pages → Custom
domains → add it; update `ARDENTUM_CORS_ORIGINS` and Supabase URL configuration.

## 6. Verify

1. `GET <api>/api/v1/meta` → `environment: production`, `auth_mode: supabase`.
2. `GET <api>/api/v1/health/db` → `{"status": "ok", "database": "ok"}`.
3. Open the web app, sign in with Google or GitHub, select **US industries: 12
   portfolios** (the first load downloads and caches the Ken French files), optimise,
   save the portfolio, reload and find it under **Portfolios**.
4. Run a Monte Carlo simulation (a background job) and a backtest.
5. On the Universe page, fetch a risk-free rate (Fama-French RF). With an uploaded
   dataset that has ISINs, build an ESG overlay on **ESG data**.
6. Optionally run the Playwright suite against the deployment (`baseURL` override).

`scripts/smoke.py` automates the outside checks (health, production settings, CORS for
the site, Ken French, ECB rates, WikiRate, FRED when configured, a background job, the
settings baked into the website, legal details, Supabase providers and signing keys). The
**Live smoke test** workflow runs it daily and on demand against the production addresses.

## Security checklist

- Production refuses dev sign-in, SQLite, wildcard CORS and missing Supabase settings.
- Secrets live only in the host's secret store; `.env*` files are git-ignored.
- Ownership is enforced on every portfolio, dataset, job and ESG overlay query.
- Compute endpoints are rate limited per verified user or client IP across instances;
  forwarded headers are trusted only for the configured number of proxy hops.
- Uploads are limited to 5 MB, parsed strictly and stored per user.
- External data is cached in PostgreSQL; if a source is down, the last good copy is
  served and labelled as stale.
