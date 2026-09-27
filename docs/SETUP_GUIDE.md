# Ardentum: setup guide for the founder

Everything you need to do to put Ardentum online, in order, with every click. Nothing here
needs a paid plan or a card. The API can run on Render (step 7A, no card, no terminal) or
on Google Cloud Run (step 7B, faster, but it needs a card for its free allowance and
commands in Cloud Shell).

Expect about 2 to 3 hours the first time. Dashboards change their wording from time to time;
if a button name differs slightly, look for the closest match.

## 0. Before you start

**Accounts you will use**

| Service | What it does for Ardentum | Cost |
|---|---|---|
| GitHub (you already have it) | Holds the code; runs tests; daily keep-alive | Free |
| Supabase | Database and sign-in | Free plan |
| Google Cloud | The Google sign-in button; the API too if you choose Cloud Run (7B) | Free; a card only for Cloud Run |
| Render | Runs the API (step 7A) | Free plan, no card |
| Cloudflare | Hosts the website (Cloudflare Pages); optional domain | Free (domain about $10/year) |
| FRED (St. Louis Fed) | 3-month Treasury-bill rate | Free |
| WikiRate | Open ESG data | Free |

**Keep a private notes file.** You will copy about a dozen values between dashboards. Make a
text file (not in the repository) with these lines and fill them in as you go:

```
SUPABASE_PROJECT_URL      = https://<ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY  = sb_publishable_...
SUPABASE_SECRET_KEY       = sb_secret_...          (secret)
SUPABASE_DB_PASSWORD      =                        (secret)
SUPABASE_POOLER_URL       = postgresql://postgres.<ref>:<password>@<host>:6543/postgres  (secret)
GOOGLE_CLIENT_ID          =
GOOGLE_CLIENT_SECRET      =                        (secret)
GITHUB_CLIENT_ID          =
GITHUB_CLIENT_SECRET      =                        (secret)
GCP_PROJECT_ID            =
GCP_PROJECT_NUMBER        =
REGION                    =
API_URL                   = https://ardentum-api.onrender.com  (Cloud Run: https://ardentum-api-<number>.<region>.run.app)
SITE_URL                  = https://<name>.pages.dev
FRED_API_KEY              =                        (secret)
WIKIRATE_API_KEY          =                        (secret)
```

Never paste values marked "secret" into the repository, a chat or an issue.

**Choose one region for everything**, close to your users. Matching pairs:

| Users mostly in | Supabase region | Cloud Run region (`REGION`) |
|---|---|---|
| India | South Asia (Mumbai) | `asia-south1` |
| Europe | Central EU (Frankfurt) | `europe-west3` |
| UK | West EU (London) | `europe-west2` |
| US East | East US (North Virginia) | `us-east4` |
| South-East Asia | Southeast Asia (Singapore) | `asia-southeast1` |
| Japan, Korea, East Asia | Northeast Asia (Tokyo) | `asia-northeast1` |

The Supabase region shows in the pooler address: `aws-0-ap-northeast-1` is Tokyo, so
`REGION=asia-northeast1`; `ap-southeast-1` is Singapore (`asia-southeast1`); `ap-south-1` is
Mumbai (`asia-south1`).

Render (step 7A) has five regions: Oregon, Ohio, Virginia, Frankfurt and Singapore.
`render.yaml` in the repository uses Singapore, the nearest to Asian Supabase regions. For
users in the Americas or Europe, change its `region:` line to `oregon`, `virginia` or
`frankfurt` (GitHub > the file > pencil icon > **Commit changes**) before step 7A.

**Choose the website name now.** Cloudflare gives the site the address
`https://<name>.pages.dev`. Pick a name (for example `ardentum`) and check that
`https://ardentum.pages.dev` does not already load a site; if it does, pick another, such
as `ardentum-app`. Write it as `SITE_URL`.

## 1. Put the finished code on the `main` branch

The work is on the branch `claude/ardentum-portfolio-platform-u2g53v`. The site and API will
be built from `main`.

1. Open https://github.com/sgfiscalreview-lab/ardentum.
2. A yellow banner may offer **Compare & pull request** for the branch; click it. If not:
   click **Pull requests** > **New pull request**, set **base: main** and
   **compare: claude/ardentum-portfolio-platform-u2g53v**, then **Create pull request**.
3. Give it a title such as "Ardentum platform" and click **Create pull request**.
4. Wait for the checks at the bottom to finish (about 10 to 15 minutes; CI runs the
   tests, the static build and the browser tests). All should be green.
5. Click **Merge pull request** > **Confirm merge**.

If an earlier pull request from this branch is already merged, do the same again: the new
pull request contains only the newer changes. Merge it before steps 7 and 8, which build
from `main`.

If `main` does not exist yet (a brand-new repository), the branch can be made the default
instead: **Settings** > **General** > **Default branch** > switch to the Claude branch.
Then use that branch name wherever this guide says `main`.

## 2. Supabase: database and sign-in

### 2.1 Create the project

1. Go to https://supabase.com and **Sign in** (use **Continue with GitHub** for speed).
2. Click **New project**. Choose your organisation (create one if asked, plan **Free**).
3. **Project name**: `ardentum`. **Database password**: click **Generate a password**,
   then copy it into your notes as `SUPABASE_DB_PASSWORD`. **Region**: the Supabase region
   you chose in step 0.
4. Click **Create new project** and wait a minute or two until it is ready.

### 2.2 Copy the keys

1. Left sidebar: **Project Settings** (gear icon) > **API Keys**.
2. On the **Publishable and secret API keys** tab:
   - copy the **Publishable key** (`sb_publishable_...`) as `SUPABASE_PUBLISHABLE_KEY`;
   - under **Secret keys**, reveal and copy the default secret key (`sb_secret_...`) as
     `SUPABASE_SECRET_KEY`. Treat it like a password.
3. Your project URL is `https://<ref>.supabase.co`, where `<ref>` is the code in the
   dashboard's address bar (`supabase.com/dashboard/project/<ref>`). Save it as
   `SUPABASE_PROJECT_URL`. (It is also shown under **Project Settings** > **Data API**.)

### 2.3 Copy the database connection string

1. Click **Connect** at the top of the project page.
2. Choose **Transaction pooler** (port **6543**). This matters: the pooler works over IPv4,
   which Render and Cloud Run need; the direct connection does not.
3. Copy the URI. It looks like
   `postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:6543/postgres`.
4. Replace `[YOUR-PASSWORD]` with `SUPABASE_DB_PASSWORD` and save the result as
   `SUPABASE_POOLER_URL`. If the password contains `@`, `:` or `/`, generate a new password
   without them (**Project Settings** > **Database** > **Reset database password**). Other
   symbols are fine, written as they are or encoded (`?` as `%3F`).
5. A string copied from an ORM tab (Prisma) ends in `?pgbouncer=true`; the API ignores that
   option, so either form works. You do not need the `DIRECT_URL` (port 5432) string.

### 2.4 Use modern token signing (recommended)

1. **Project Settings** > **JWT Keys** (sometimes shown as **JWT signing keys**).
2. If the page says the project uses the **legacy JWT secret**, click **Migrate JWT secret**,
   then **Rotate keys**. Signing in keeps working throughout.
3. If you prefer not to, you can instead copy the legacy JWT secret and set it as
   `ARDENTUM_SUPABASE_JWT_SECRET` in step 7; the API accepts either.

Sign-in providers are configured in step 6, after you have the Google and GitHub keys.

## 3. Google Cloud: project (billing only for Cloud Run)

The Google sign-in button needs a Google Cloud project but no billing. Items 3 and 4 below
are only for running the API on Cloud Run (step 7B); skip them if you use Render (7A).

1. Go to https://console.cloud.google.com and sign in with the Google account you want
   to own the service.
2. Top bar: click the project picker > **New project**. **Project name**: `ardentum`.
   Click **Create**, then select the new project in the picker.
3. Open **Billing** (menu at top left, or search "Billing"). Link a billing account: click
   **Link a billing account** or **Create billing account**, add your card, confirm.
4. Still in **Billing**: **Budgets & alerts** > **Create budget**.
   - **Name**: `ardentum-1-dollar`. **Projects**: `ardentum`.
   - **Amount**: **Specified amount**, `1` (in your billing currency).
   - **Actions**: alert thresholds 50%, 90% and 100% of actual spend; email alerts to
     billing admins. **Finish**.
   A budget only sends emails; it does not stop the service. With the settings in step 7B
   the expected cost is zero or a few cents per month (image storage above 0.5 GB).
5. Open **IAM & Admin** > **Settings** (or the project picker) and copy the **Project ID**
   and **Project number** into your notes.

## 4. Google sign-in button (OAuth client)

1. In the same Google Cloud project, search for **Google Auth Platform** and open it.
   If asked, click **Get started**.
2. **Branding**: **App name** `Ardentum`; **User support email**: your email. Continue.
3. **Audience**: choose **External**. Continue. **Contact information**: your email.
   Accept the policy and click **Create**.
4. **Data Access** > **Add or remove scopes**: tick `.../auth/userinfo.email`,
   `.../auth/userinfo.profile` and `openid`. **Update** > **Save**.
5. **Audience**: under **Publishing status**, click **Publish app** > **Confirm**. (While in
   "Testing", only listed test users can sign in. These basic scopes do not need Google's
   verification.)
6. **Clients** > **Create client**:
   - **Application type**: **Web application**. **Name**: `Ardentum web`.
   - **Authorized JavaScript origins**: add `SITE_URL` (e.g. `https://ardentum.pages.dev`)
     and `http://localhost:3000`.
   - **Authorized redirect URIs**: add `https://<ref>.supabase.co/auth/v1/callback` (your
     `SUPABASE_PROJECT_URL` followed by `/auth/v1/callback`).
   - Click **Create**. Copy the **Client ID** and **Client secret** into your notes.

## 5. GitHub sign-in button (OAuth app)

1. Go to https://github.com/settings/developers (GitHub > your avatar > **Settings** >
   **Developer settings** > **OAuth Apps**).
2. Click **New OAuth App** (or **Register a new application**).
   - **Application name**: `Ardentum`.
   - **Homepage URL**: `SITE_URL`.
   - **Authorization callback URL**: `https://<ref>.supabase.co/auth/v1/callback`.
   - Leave **Enable Device Flow** unticked. Click **Register application**.
3. Copy the **Client ID**. Click **Generate a new client secret** and copy it immediately
   (it is shown once).

## 6. Connect the sign-in providers in Supabase

1. Supabase project > **Authentication** > **Sign In / Providers** (or **Providers**).
2. **Google**: switch on, paste `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, **Save**.
3. **GitHub**: switch on, paste `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`, **Save**.
4. **Email** can stay off. (Turning it on needs a custom SMTP sender; the site shows only
   Google and GitHub unless `NEXT_PUBLIC_AUTH_EMAIL_ENABLED=true`.)
5. **Authentication** > **URL Configuration**:
   - **Site URL**: `SITE_URL`.
   - **Redirect URLs** > **Add URL**: `SITE_URL/**` (e.g. `https://ardentum.pages.dev/**`)
     and `http://localhost:3000/**`. Add your custom domain here later if you get one.
   - **Save**.

## 7. Deploy the API

Choose one:

- **7A. Render (recommended)**: no card and no terminal; it redeploys by itself when `main`
  changes. The free plan has 512 MB of memory (Ardentum uses about 250 MB at peak) and a
  small share of a CPU, so long calculations take several times longer than on Cloud Run.
  It sleeps after 15 idle minutes; the keep-alive in step 9 prevents that.
- **7B. Google Cloud Run**: faster, but needs billing with a card (step 3) and commands in
  Cloud Shell.

### 7A. Render (no card)

The second pull request (step 1) must be merged first: Render reads `render.yaml` from
`main`.

1. Go to https://dashboard.render.com and click **Sign up** > **GitHub**. The free plan does
   not ask for a card.
2. Top right: **New** > **Blueprint**.
3. Connect the repository: click **GitHub** (or **Configure account**) and allow access to
   `sgfiscalreview-lab/ardentum`, then click **Connect** next to it. (It is a public
   repository, so pasting `https://github.com/sgfiscalreview-lab/ardentum` as a public Git
   repository also works.)
4. **Blueprint Name**: `ardentum`. **Branch**: `main`. Render lists the service it will
   create, **ardentum-api** (Free, Singapore), and asks for four values:

   | Variable | Value |
   |---|---|
   | `ARDENTUM_SUPABASE_URL` | `SUPABASE_PROJECT_URL` |
   | `ARDENTUM_CORS_ORIGINS` | `SITE_URL` inside brackets and double quotes, e.g. `["https://ardentum.pages.dev"]` |
   | `ARDENTUM_DATABASE_URL` | `SUPABASE_POOLER_URL` (with the password filled in) |
   | `ARDENTUM_SUPABASE_SERVICE_KEY` | `SUPABASE_SECRET_KEY` |

5. Click **Deploy Blueprint** (or **Apply**). The first build takes 5 to 10 minutes; follow
   it under **ardentum-api** > **Logs**.
6. The service page shows its address at the top, e.g. `https://ardentum-api.onrender.com`
   (Render adds a few characters if the name is taken). Copy it as `API_URL`. Open
   `API_URL/api/v1/health/db`; it should show `{"status":"ok","database":"ok"}`. The first
   start also creates the database tables.

To change a value later: **ardentum-api** > **Environment** > **Edit** > change it >
**Save, rebuild, and deploy** (or **Save and deploy**).

If the Blueprint cannot be created, make the service by hand: **New** > **Web Service** >
the repository > **Language** `Docker`, **Branch** `main`, **Region** `Singapore`, **Root
Directory** `backend`, **Instance Type** `Free`. Under **Environment Variables** add the four
values above plus `ARDENTUM_ENV` = `production`, `ARDENTUM_AUTH_MODE` = `supabase`,
`ARDENTUM_TRUSTED_PROXY_HOPS` = `1`, `ARDENTUM_RATE_LIMIT_STORE` = `database` and
`WEB_CONCURRENCY` = `1`. Under **Advanced**, **Health Check Path** `/api/v1/health`. Click
**Deploy Web Service**.

If you tried Cloud Run earlier and now use Render, nothing needs deleting. To be sure Google
never charges you: Google Cloud console > **Billing** > **Account management** > the
`ardentum` project > **Actions** > **Disable billing**. Google sign-in keeps working.

### 7B. Google Cloud Run (card required)

You will use **Cloud Shell**, a terminal inside the browser with everything installed.

1. In the Google Cloud console, make sure the `ardentum` project is selected, then click
   the **Activate Cloud Shell** icon (a `>_` symbol) at the top right. Wait for the
   terminal to open at the bottom.
2. Set your region and enable the services (copy, edit `REGION`, paste, press Enter):

   ```bash
   export REGION=asia-south1
   gcloud config set run/region $REGION
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
     artifactregistry.googleapis.com secretmanager.googleapis.com
   ```

3. Store the secrets. Each command asks for a value; paste it (nothing is shown while you
   paste) and press Enter:

   ```bash
   read -rsp "Supabase pooler URL: " V && printf '%s' "$V" | gcloud secrets create ardentum-db-url --data-file=- ; echo
   read -rsp "Supabase secret key: " V && printf '%s' "$V" | gcloud secrets create ardentum-supabase-secret --data-file=- ; echo
   ```

   Then allow Cloud Run to read them:

   ```bash
   PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
   for s in ardentum-db-url ardentum-supabase-secret; do
     gcloud secrets add-iam-policy-binding $s \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   done
   ```

4. Get the code and write the settings file (edit the two `https://` lines first):

   ```bash
   git clone https://github.com/sgfiscalreview-lab/ardentum.git && cd ardentum
   cat > cloudrun.env.yaml <<'EOF'
   ARDENTUM_ENV: production
   ARDENTUM_AUTH_MODE: supabase
   ARDENTUM_SUPABASE_URL: https://<ref>.supabase.co
   ARDENTUM_CORS_ORIGINS: '["https://ardentum.pages.dev"]'
   ARDENTUM_TRUSTED_PROXY_HOPS: "1"
   ARDENTUM_RATE_LIMIT_STORE: database
   WEB_CONCURRENCY: "1"
   EOF
   ```

   In the file, `https://<ref>.supabase.co` is your `SUPABASE_PROJECT_URL` and
   `https://ardentum.pages.dev` is your `SITE_URL`. If the terminal keeps showing a `>`
   prompt after pasting, type `EOF` on its own line and press Enter. To check or fix the
   file: `nano cloudrun.env.yaml` (save with Ctrl+O, Enter; exit with Ctrl+X).

5. Deploy (takes 5 to 10 minutes the first time; answer `Y` if asked to create a
   repository or enable an API):

   ```bash
   gcloud run deploy ardentum-api --source backend \
     --allow-unauthenticated --min-instances 0 --max-instances 2 \
     --cpu 1 --memory 1Gi --concurrency 20 --timeout 60 \
     --env-vars-file cloudrun.env.yaml \
     --set-secrets "ARDENTUM_DATABASE_URL=ardentum-db-url:latest,ARDENTUM_SUPABASE_SERVICE_KEY=ardentum-supabase-secret:latest"
   ```

6. At the end it prints **Service URL**. Copy it into your notes as `API_URL`. Check it:
   open `API_URL/api/v1/health/db` in a browser; it should show
   `{"status":"ok","database":"ok"}`. The first start also creates the database tables.
7. Keep image storage inside the free 0.5 GB: console > **Artifact Registry** > repository
   **cloud-run-source-deploy** > **Edit** (or **Cleanup policies**) > add a policy
   **Keep most recent versions**, count `2`, and switch off dry run. **Save**.

## 8. Deploy the website to Cloudflare Pages

1. Go to https://dash.cloudflare.com and sign up / sign in (Free plan).
2. Left sidebar: **Workers & Pages** > **Create application** > **Pages** >
   **Connect to Git**.
3. Connect your GitHub account when asked and give Cloudflare access to the
   `sgfiscalreview-lab/ardentum` repository. Select it and click **Begin setup**.
4. **Project name**: the name you chose in step 0 (this sets `https://<name>.pages.dev`).
   **Production branch**: `main`.
5. **Build settings**:
   - **Framework preset**: **None**.
   - **Build command**: `npm ci && npm run build`
   - **Build output directory**: `out`
   - **Root directory (advanced)** > **Path**: `frontend`
6. **Environment variables (advanced)** > add each of these (**Add variable**):

   | Variable name | Value |
   |---|---|
   | `NODE_VERSION` | `22` |
   | `NEXT_OUTPUT` | `export` |
   | `NEXT_PUBLIC_API_BASE` | `API_URL` (no trailing slash) |
   | `NEXT_PUBLIC_SUPABASE_URL` | `SUPABASE_PROJECT_URL` |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `SUPABASE_PUBLISHABLE_KEY` |
   | `NEXT_PUBLIC_LEGAL_OPERATOR` | your legal name or company name (see step 11) |
   | `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL` | an email address for privacy and legal requests |
   | `NEXT_PUBLIC_LEGAL_GOVERNING_LAW` | e.g. `India`, `England and Wales`, `the State of Delaware, USA` |
   | `NEXT_PUBLIC_LEGAL_LAST_UPDATED` | today's date, `YYYY-MM-DD` |

7. Click **Save and Deploy**. The first build takes 3 to 5 minutes. When it finishes, open
   the `https://<name>.pages.dev` address. If Cloudflare shows a different address than
   `SITE_URL`, use the one shown: update `SITE_URL` in your notes and repeat the parts of
   steps 4, 5, 6 and 7 that use it (7A: change `ARDENTUM_CORS_ORIGINS` on Render's
   **Environment** page; 7B: edit `cloudrun.env.yaml` and re-run the deploy command).

Every later push to `main` rebuilds the website automatically. To change a variable:
**Workers & Pages** > your project > **Settings** > **Variables and Secrets** (or
**Environment variables**), then **Deployments** > the latest one > **Retry deployment**.

## 9. Keep the free database and API awake

Supabase pauses free projects after a week without activity, and Render's free plan stops
the API after 15 idle minutes (the next visitor then waits about a minute). A job in the
repository pings the API's database check every 10 minutes, which prevents both; it is free
for public repositories.

1. GitHub repository > **Settings** > **Secrets and variables** > **Actions** >
   **Variables** tab > **New repository variable**.
2. **Name**: `API_URL`. **Value**: your `API_URL`. **Add variable**.
3. Test it: **Actions** tab > **keepalive** (left list) > **Run workflow** > **Run workflow**.
   After a minute it should show a green tick.

If the API is down, GitHub emails you about the failed runs, which doubles as an alert.
GitHub switches scheduled jobs off after 60 days without any change to the repository; if
you get that email, open the **Actions** tab > **keepalive** > **Enable workflow**.

If Supabase pauses the project anyway, open it in the Supabase dashboard and click
**Restore project**; nothing is lost.

## 10. Optional free data keys

**FRED (3-month Treasury bill as the risk-free rate)**

1. https://fredaccount.stlouisfed.org > **Create New Account**; confirm your email.
2. https://fredaccount.stlouisfed.org/apikeys > **Request API Key**; describe the use
   ("risk-free rate for a portfolio-analysis web app"), accept the terms. The key appears
   at once.

**WikiRate (open ESG data)** may work without a key; a key avoids refusals.

1. Sign up at https://wikirate.org.
2. Open your profile page, tab **Accounts**, and generate an API key.

**Add them to the API**, in Cloud Shell (reopen it; run `cd ardentum` first). If you have
only one of the two keys, leave out the lines and the `--update-secrets` entry for the other:

```bash
read -rsp "FRED key: " V && printf '%s' "$V" | gcloud secrets create ardentum-fred --data-file=- ; echo
read -rsp "WikiRate key: " V && printf '%s' "$V" | gcloud secrets create ardentum-wikirate --data-file=- ; echo
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
for s in ardentum-fred ardentum-wikirate; do
  gcloud secrets add-iam-policy-binding $s \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
gcloud run services update ardentum-api \
  --update-secrets "ARDENTUM_FRED_API_KEY=ardentum-fred:latest,ARDENTUM_WIKIRATE_API_KEY=ardentum-wikirate:latest"
```

## 11. Legal texts

The site has a Terms of Service (`/terms`) and a Privacy Policy (`/privacy`) that describe
exactly what the software does. They show the operator name, contact email and governing law
from the variables you set in step 8.

1. Decide who operates the site (you personally, or your company) and which country's law
   applies (usually where you or your company are based).
2. Use an email address you check. With a custom domain (step 13), Cloudflare **Email
   Routing** can forward `privacy@yourdomain` to your inbox for free.
3. Read both pages on your live site. **Have a lawyer or a qualified adviser review them**
   before a public launch, especially if you have users in the EU/UK (GDPR), California
   (CCPA) or India (DPDP Act). Changes to the wording are code changes in
   `frontend/src/app/terms/page.tsx` and `frontend/src/app/privacy/page.tsx`.
4. When you change them, update `NEXT_PUBLIC_LEGAL_LAST_UPDATED` in Cloudflare and redeploy.

## 12. Ask Prof. French about the data library (before charging money)

The Kenneth French Data Library is free to use and widely cited, but it has no written
licence for commercial redistribution. Before you charge users or advertise commercially,
email Prof. French (address on his faculty page at Tuck, Dartmouth). A short message works:

> Dear Professor French, I run Ardentum, a portfolio-analysis web application at
> `SITE_URL`. It downloads your daily industry portfolio returns and the Fama/French factors
> to let users analyse historical portfolios, and cites the Data Library on every result.
> May I use the data in this way in a product that may become commercial? Thank you.

Keep the reply. Until then the site is free, so this is not urgent.

## 13. Optional: your own domain (about $10/year)

1. Cloudflare dashboard > **Domain Registration** > **Register Domains**; search, buy
   (Cloudflare charges the registry price without mark-up).
2. **Workers & Pages** > your project > **Custom domains** > **Set up a custom domain** >
   enter e.g. `ardentum.com` (and `www.ardentum.com`) > **Continue** > **Activate domain**.
3. Update everything that lists the site address:
   - Supabase: **Authentication** > **URL Configuration**: Site URL and Redirect URLs.
   - Google Auth Platform > **Clients** > your client > **Authorized JavaScript origins**.
   - GitHub OAuth app > **Homepage URL**.
   - The API's `ARDENTUM_CORS_ORIGINS` must list both addresses, e.g.
     `["https://ardentum.com","https://ardentum.pages.dev"]`. Render: **Environment** page.
     Cloud Run: edit `cloudrun.env.yaml` (the value inside single quotes there) and run the
     deploy command from step 7B.5 again.

## 14. Final check

1. Open `API_URL/api/v1/meta`: it should show `"environment": "production"` and
   `"auth_mode": "supabase"`.
2. Open `SITE_URL`. The landing page shows screenshots; **Open the workspace** loads the
   synthetic demo.
3. Click **Sign in** > **Continue with Google**; you return signed in. Try GitHub too.
4. On **Universe**, choose **US industries: 12 portfolios (Kenneth French)** (the first
   load downloads the data), then **Optimise** and **Save**. Reload the page and find it
   under **Portfolios**.
5. Run a **Monte Carlo** simulation and a **Backtest**.
6. On **Universe**, under Risk-free rate, choose the Fama-French source and click **Use**.
7. Visit `/terms`, `/privacy` and `/account`. On **Account**, **Download JSON** works;
   delete a test account to check deletion.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Website says "Cannot reach the Ardentum API" | `NEXT_PUBLIC_API_BASE` wrong or has a trailing slash; or the site address is missing from `ARDENTUM_CORS_ORIGINS` (step 7A.4 or 7B.4, then redeploy). |
| Google sign-in says "Access blocked" or works only for your own account; the client dialog said "OAuth access is restricted to the test users" | The app is still in Testing: **Google Auth Platform** > **Audience** > **Publish app** > **Confirm** (step 4.5). |
| Google sign-in shows "redirect_uri_mismatch" | The redirect URI in step 4.6 must be exactly `https://<ref>.supabase.co/auth/v1/callback`. |
| After sign-in you land on the wrong site or get "requested path is invalid" | Supabase **URL Configuration** (step 6.5) needs `SITE_URL/**` in Redirect URLs. |
| Signed in, but saving says "Invalid authentication token" | Do step 2.4 (JWT signing keys), or set `ARDENTUM_SUPABASE_JWT_SECRET` to the legacy secret. |
| Render: the Blueprint finds no `render.yaml` | Merge the second pull request (step 1); Render reads `main`. |
| Render: the deploy fails | **ardentum-api** > **Logs**, first red line. `invalid connection option "pgbouncer"`: the second pull request is not merged yet. `password authentication failed`: wrong password in the URL. `Tenant or user not found`: the user part of the URL must be `postgres.<ref>`. |
| The first visit after a quiet spell takes about a minute | Render was asleep. Check that step 9 is set up and its runs are green. |
| `health/db` shows an error | Check the pooler URL (port 6543, password filled in, no brackets). Render: fix `ARDENTUM_DATABASE_URL` on the **Environment** page. Cloud Run: store a corrected value with `read -rsp "URL: " V && printf '%s' "$V" \| gcloud secrets versions add ardentum-db-url --data-file=-`, then restart with `gcloud run services update ardentum-api --region $REGION --update-env-vars RESTARTED_AT=$(date +%s)`. |
| Cloudflare build fails | Check the root directory is `frontend`, output `out`, `NODE_VERSION` 22; open the build log for the first red line. |
| A budget email arrives | Cloud Run: **ardentum-api** > **Metrics**; Billing > **Reports** shows which service cost money. Lower `--max-instances` to 1 if needed. |

## If a secret was exposed

If a value marked "secret" ended up somewhere public or shared (a chat, a screenshot, an
issue, a commit), replace it. Doing this before step 7 is quickest, because nothing uses the
old values yet. Put the new values straight into the dashboards and Cloud Shell; do not
share them.

| Secret | Replace it | Then update |
|---|---|---|
| `SUPABASE_DB_PASSWORD` | Supabase > **Project Settings** > **Database** > **Reset database password**. Type your own long password of letters and digits (24 or more) so the URL needs no escaping. | Build the new `SUPABASE_POOLER_URL`. If the API is deployed: Render, `ARDENTUM_DATABASE_URL` on the **Environment** page; Cloud Run, the `health/db` command in Troubleshooting. |
| `SUPABASE_SECRET_KEY` | Supabase > **Project Settings** > **API Keys** > **Secret keys**: add a new secret key, then delete the old one from its menu. | If deployed: Render, `ARDENTUM_SUPABASE_SERVICE_KEY` on the **Environment** page; Cloud Run, `read -rsp "Secret key: " V && printf '%s' "$V" \| gcloud secrets versions add ardentum-supabase-secret --data-file=-`, then the restart command from Troubleshooting. |
| `GOOGLE_CLIENT_SECRET` | Google Auth Platform > **Clients** > **Ardentum web** > **Add secret**; copy it, then disable and delete the old secret. | Supabase > **Authentication** > **Sign In / Providers** > **Google**: paste the new secret, **Save**. |
| `GITHUB_CLIENT_SECRET` | GitHub > **Settings** > **Developer settings** > **OAuth Apps** > **Ardentum** > **Generate a new client secret**; copy it, then delete the old one. | Supabase > **Sign In / Providers** > **GitHub**: paste the new secret, **Save**. |

The publishable key, project URL and client IDs are public by design and need no action.

## Updating later

- **Website**: push to `main`; Cloudflare rebuilds automatically.
- **API on Render**: nothing to do; each new commit on `main` that touches `backend/` is
  deployed once CI has passed.
- **API on Cloud Run**: in Cloud Shell, `cd ardentum && git pull && gcloud run deploy ardentum-api --source backend --env-vars-file cloudrun.env.yaml` (secrets and other settings are kept). Database migrations run automatically on start.
- **Screenshots on the landing page**: run the app locally and `npm run screenshots` in
  `frontend/` (see `frontend/scripts/capture-screenshots.mjs`).
