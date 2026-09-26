# Deployment

Target topology (see DECISIONS D-013 and TODO for the founder decisions involved):

| Component | Recommended host | Artifact |
|---|---|---|
| Database + authentication | Supabase (managed PostgreSQL + Auth) | — |
| API | Any container host: Render, Fly.io, Google Cloud Run | `backend/Dockerfile` |
| Web | Vercel (or any Node host / container) | `frontend/` or `frontend/Dockerfile` |

## 1. Supabase

1. Create a project. Note the **project URL** and the **anon (public) key**.
2. Authentication → Providers → enable **Email** (password). Configure the site URL to the web app's URL.
3. The API verifies Supabase access tokens via the project's JWKS endpoint
   (`<URL>/auth/v1/.well-known/jwks.json`). Legacy projects that still sign with HS256
   must also set `ARDENTUM_SUPABASE_JWT_SECRET`.
4. Database → connection string (use the pooled connection for the API):
   `postgresql://postgres.<ref>:<password>@<host>:6543/postgres`.

## 2. API container

Environment variables (production):

| Variable | Value |
|---|---|
| `ARDENTUM_ENV` | `production` |
| `ARDENTUM_DATABASE_URL` | Supabase PostgreSQL URL |
| `ARDENTUM_AUTH_MODE` | `supabase` (required; the app refuses to start otherwise) |
| `ARDENTUM_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `ARDENTUM_CORS_ORIGINS` | `["https://<web-domain>"]` (only needed for direct browser calls) |
| `ARDENTUM_TIINGO_API_KEY` | optional — requires an appropriate licence |
| `WEB_CONCURRENCY` | worker processes (default 2) |

The entrypoint runs `alembic upgrade head` before starting (set
`ARDENTUM_SKIP_MIGRATIONS=1` to disable). Health check: `GET /api/v1/health`.

Example (Render): New → Web Service → Docker, root directory `backend`, add the
variables above, health-check path `/api/v1/health`.

## 3. Web app

The web app proxies `/api/v1/*` to the API, so the browser only talks to one origin.

| Variable (build time) | Value |
|---|---|
| `API_URL` | public URL of the API, e.g. `https://ardentum-api.onrender.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |

Vercel: import the repository, set the root directory to `frontend`, keep "Include
files outside the root directory" enabled (the build reads `docs/methodology`), and add
the variables. Container alternative:
`docker build -f frontend/Dockerfile --build-arg API_URL=... -t ardentum-web .`

## 4. Verify

1. `GET https://<api>/api/v1/meta` → `auth_mode: supabase`, `environment: production`.
2. Open the web app, create an account, run an optimisation, save it, reload, and
   confirm it appears under **Portfolios**.
3. Run the Playwright suite against staging if desired (`baseURL` override).

## Security checklist

- Production refuses dev sign-in, SQLite, wildcard CORS and missing Supabase config (enforced in settings).
- Secrets only in the host's secret store; `.env*` files are git-ignored.
- The API is stateless apart from PostgreSQL; ownership is enforced on every portfolio/dataset query.
- Uploads are limited to 5 MB, parsed strictly, and stored per user.
