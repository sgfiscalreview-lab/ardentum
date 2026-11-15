# Launch plan (from 15 November 2026)

Everything left before a public launch is an owner task: accounts, settings, legal and
people. Work through the steps in order; each one says what it needs from the step before.
Detailed click paths for setup already live in [SETUP_GUIDE.md](SETUP_GUIDE.md) and
[SECURITY.md](../SECURITY.md); this page links to them rather than repeating them. The
steps for GitHub, Render, Cloudflare and Zenodo were checked against their documentation on
13 November 2026; menus move, so each step ends with a way to check that it worked.

| Week | Steps | Time |
|---|---|---|
| 1 (from 15 Nov) | 1 Two-factor sign-in, 2 WikiRate keys, 3 Domain and email | about 2 hours |
| 2 | 4 Connect the services to the repository, 5 Repository security, 6 Rotate secrets, 7 Legal texts, 8 FRED key, 9 Ask Prof. French | about 3 hours, plus waiting for replies |
| 3 onwards | 10 Outside review by a company | 2 to 6 weeks, mostly waiting |

Step 4 can be done before step 3: it keeps the site's `pages.dev` address.

Today's addresses (replace them as you go):

```
SITE_URL  = https://ardentum-frontend.pages.dev
API_URL   = https://ardentum-api.onrender.com
REPO      = https://github.com/clumstantine/ardentum
```

---

## 1. Two-factor sign-in (first, before anything moves)

Turn on two-factor sign-in (an authenticator app, not text messages) on GitHub, Supabase,
Render, Cloudflare and Google. Store the recovery codes somewhere offline. Do this first:
the next steps hand control of the project to these accounts.

## 2. WikiRate keys (10 minutes; open ESG data is off until this is done)

WikiRate replaced its API in autumn 2026: it now answers only requests that carry a free
account's keys, so the Open ESG data page on the live site says the feature is switched
off, and the daily live check has reported it since early November. The rest of the site
is unaffected.

1. Follow SETUP_GUIDE [step 10](SETUP_GUIDE.md#10-optional-free-data-keys), "WikiRate":
   create the account, copy the publishable key, generate a personal token, and add both
   to **ardentum-api** > **Environment** on Render.
2. **Check**: GitHub > **Actions** > **Live smoke test** > **Run workflow**. The line
   "WikiRate open ESG data" should pass, naming Adidas AG. Then on the site: **ESG data** >
   search "emissions".

The new connection was written from WikiRate's documentation and tested against a stand-in;
it could not be tried against WikiRate itself without an account. This check is its first
real trial. If the line fails, its message says which request was refused; send it on.

## 3. Domain and email

1. **Buy**: SETUP_GUIDE [step 13](SETUP_GUIDE.md#13-optional-your-own-domain-about-10year),
   1 and 2 (Cloudflare Registrar, about $10 a year; add both `yourdomain` and
   `www.yourdomain` to the Pages project under **Custom domains** > **Set up a domain**).
2. **Email**: in the Cloudflare dashboard open **Email Routing** (search for it; it sits
   under Email Service), choose **Onboard Domain** and pick your domain. Add your own inbox
   under **Destination Addresses** and confirm the email Cloudflare sends. Then **Routing
   Rules** > **Create routing rule**: `privacy` at your domain, action **Send to an email**,
   your inbox. Repeat for `hello` if you like. Test it from a different email account.
   Step 7 uses this address.
3. **Update every place that lists the site address** (SETUP_GUIDE step 13.3): Supabase
   Site URL and Redirect URLs; Google Auth Platform authorized JavaScript origins (and
   **Branding** > authorized domains, home page and privacy policy links); GitHub OAuth app
   homepage; Render `ARDENTUM_CORS_ORIGINS` with every address, for example
   `["https://yourdomain","https://www.yourdomain","https://ardentum-frontend.pages.dev"]`.
4. **GitHub Actions variable** `SITE_URL` = `https://yourdomain`, so the daily live check
   tests the address people use.
5. **Code links** (one pull request): the live link in `README.md`.
6. **Check**: open `https://yourdomain`, sign in with Google and GitHub, save a portfolio,
   run the live smoke test.

Optional: an API address such as `api.yourdomain`. Render > **ardentum-api** >
**Settings** > **Custom Domains** > **Add Custom Domain**; in Cloudflare add a `CNAME`
record `api` pointing at `ardentum-api.onrender.com` with **Proxy status: DNS only**, set
**SSL/TLS** to **Full**, then **Verify** on Render. Not needed; if you do it, set
`NEXT_PUBLIC_API_BASE` in Cloudflare Pages and the `API_URL` Actions variable to it, then
redeploy the site.

## 4. Connect the services to the repository

The code lives at https://github.com/clumstantine/ardentum. Each service reaches it
through a GitHub app installed on that account. The API keeps running throughout; the
website is offline for a few minutes while its project is recreated.

| Service | What to do | How to check |
|---|---|---|
| **GitHub Actions** | Repository > **Settings** > **Secrets and variables** > **Actions** > **Variables** > **New repository variable**: `API_URL` = `https://ardentum-api.onrender.com`. The other addresses have defaults in the workflows; add `SITE_URL` once you have your own domain. **Actions** tab: if a banner says workflows are disabled, enable them. | **Actions** > **Live smoke test** > **Run workflow** passes. |
| **Render** (API) | Open https://github.com/apps/render/installations/new, choose the account and give the Render app the `ardentum` repository. Then Render > **ardentum-api** > **Settings** > **Build & Deploy** > **Repository** > **Edit**: pick `clumstantine/ardentum`, branch `main`, and keep the same Docker settings. If deploys fail to start, the same page has **Git Credentials**. | **Manual Deploy** > **Deploy latest commit** succeeds. |
| **Cloudflare Pages** (site) | A Pages project cannot be pointed at another repository, so it is recreated under the same name, which keeps its address. First copy every entry under **ardentum-frontend** > **Settings** > **Variables and Secrets** into a note, with the build settings. Then **Settings** > **Delete project**, and create it again: **Create application** > **Pages** > **Connect to Git**, add the GitHub account, pick `ardentum`, name the project `ardentum-frontend`, and enter the settings and variables as in SETUP_GUIDE step 8. If you already use your own domain, add it again under **Custom domains**. | The site loads at its usual address and shows the latest commit; sign in once. |
| **Zenodo** (DOI), if set up | zenodo.org > your name > **GitHub** > **Sync now**, then switch the repository on. | The repository is listed as enabled. |

Point a local copy at the address with
`git remote set-url origin https://github.com/clumstantine/ardentum.git`.

## 5. Repository security

A new repository starts with these switched off. Turn on the GitHub items of the owner
checklist in
[SECURITY.md](../SECURITY.md#settings-outside-the-code-owner-checklist): private
vulnerability reporting, Dependabot alerts and security updates, secret scanning, push
protection, and protecting `main` (pull requests and passing CI before merging). For an
organisation, also: **Settings** > **Authentication security** > **Require two-factor
authentication**.

## 6. Rotate secrets

If any value marked "secret" was ever pasted outside the hosts' own settings (a chat, an
email, an issue, a screenshot), replace it with the table in SETUP_GUIDE,
[If a secret was exposed](SETUP_GUIDE.md#if-a-secret-was-exposed). Afterwards run the live
smoke test and sign in once with Google and once with GitHub.

## 7. Legal texts

Needs the email address from step 3.

1. Decide the operator (you, or your company) and the governing law (where you or the
   company are based).
2. Cloudflare > **ardentum-frontend** > **Settings** > **Variables and Secrets**
   (Production). The live check reports that the legal details are filled in today; make
   sure each still says what you want, with the new email address:

   | Variable | Example |
   |---|---|
   | `NEXT_PUBLIC_LEGAL_OPERATOR` | your full name, or the company's registered name |
   | `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL` | `privacy@yourdomain` |
   | `NEXT_PUBLIC_LEGAL_GOVERNING_LAW` | for example "the laws of England and Wales" |
   | `NEXT_PUBLIC_LEGAL_ADDRESS` | postal address (needed in the EU and UK for a company) |
   | `NEXT_PUBLIC_LEGAL_REGISTRATION` | company number, if a company |
   | `NEXT_PUBLIC_LEGAL_LAST_UPDATED` | the date you publish, `YYYY-MM-DD` |

   Then **Deployments** > **Retry deployment** and read `/terms` and `/privacy`.
3. **Review by a lawyer** before a public launch. Send them both pages and
   [SECURITY.md](../SECURITY.md) (what is stored and where). Ask specifically: GDPR and UK
   GDPR (if anyone in Europe may use it), the "not investment advice" wording, the
   liability limits, and data-transfer wording for Supabase, Render and Cloudflare. Cheaper
   routes: a university law clinic, or a startup programme's legal hours. Changes to the
   wording are edits to `frontend/src/app/terms/page.tsx` and `privacy/page.tsx`.

## 8. FRED key (optional, 5 minutes)

SETUP_GUIDE [step 10](SETUP_GUIDE.md#10-optional-free-data-keys). It adds the
three-month Treasury bill as a risk-free rate; the daily live check skips FRED until it
is set.

## 9. Ask Prof. French about the data library

Only needed before charging money, but replies take time, so send it now. The message is
in SETUP_GUIDE [step 12](SETUP_GUIDE.md#12-ask-prof-french-about-the-data-library-before-charging-money);
use the new domain as the site address. Keep the reply with your records.

---

## 10. Outside review by a company

Goal: one organisation that knows portfolio construction checks that the numbers are right
and the product is usable, and agrees to say so in writing. Do it after steps 3 and 7, so
reviewers see the final address and legal pages.

### 10.1 Who to ask (pick one route)

| Route | Cost | What you get | Where to find them |
|---|---|---|---|
| **A finance or statistics department** (a professor or researcher in asset pricing, portfolio theory or financial econometrics) | usually free | The strongest check of the methods; a named academic reviewer | Authors of the papers the methodology cites (references page); your own or a nearby university's finance faculty |
| **A small investment firm, family office or ESG fund** (pilot user) | free | Real use: is it useful, what is missing, would they rely on it | Local CFA Society events, ESG investing meet-ups, LinkedIn |
| **A model-validation or quant consultancy** | paid (expect a quote) | A formal validation report in the style banks use | Search "independent model validation" consultancies; ask for a fixed-scope quote |

The first two are free and enough for a credible first review. A paid validation makes
sense once there are paying users.

### 10.2 What to send them (the review pack)

All of it is in the repository; send links, not attachments:

1. The live site and a one-paragraph description (the top of `README.md`).
2. Methodology: `docs/methodology/` (01 to 11), especially
   [09 How calculations are validated](methodology/09-validation.md).
3. Evidence: `PROGRESS.md` (what is done, test counts), the latest green CI run on GitHub
   (Actions > CI), and the research studies in `research/results/` with `research/README.md`.
4. Design decisions and known limits: `DECISIONS.md`, "Interpreting the results" in
   methodology 05 and "Known limitations and biases" in methodology 07.
5. The review tasks below and the feedback questions.

### 10.3 Review tasks (about two hours)

Each task has an answer the reviewer can check by hand, in a spreadsheet or in their own code.

1. **Minimum variance, two assets.** Upload two return series (or use the demo), run
   minimum variance with no position limits, and compare the weights with
   w1 = (s2^2 - s12) / (s1^2 + s2^2 - 2 s12) from the sample covariance.
2. **Sharpe ratio and its interval.** Take any result's portfolio returns and recompute the
   annualised Sharpe ratio (mean excess return / standard deviation, times the square root
   of 252, 52 or 12). The interval should be close to Lo's (2002) for roughly independent
   returns, and wider when returns are autocorrelated.
3. **Efficient frontier.** Check that no portfolio on the frontier has a higher Sharpe ratio
   than the maximum-Sharpe portfolio, and that the frontier is concave in
   (volatility, return).
4. **Backtest, no look-ahead.** Run a backtest, then change only the prices after a chosen
   date: the weights chosen before that date must not change.
5. **ESG constraint.** With the maximum-Sharpe objective, set a minimum portfolio ESG
   score: the result's score meets it and its Sharpe ratio is no higher than without it.
6. **Factor exposure.** Regress a portfolio's excess returns on the Fama-French three
   factors in their own tool and compare loadings and Newey-West t-statistics.
7. **Crisis replay.** Pick one crisis and check the buy-and-hold return from the industry
   returns by hand.

### 10.4 Feedback questions

1. Did any number disagree with your own calculation? Which, and by how much?
2. Is any method or default (estimation window, shrinkage, costs, rebalancing) one you
   would not use? What would you use instead?
3. Is anything stated with more confidence than the data supports?
4. What is missing that you would need before using it for real decisions?
5. Would you allow us to name you or your organisation, and to quote a sentence?

### 10.5 First email (adapt it)

> Subject: Request for a short expert review of an open-source portfolio tool
>
> Dear <name>,
>
> I have built Ardentum (<SITE_URL>), a free, open-source portfolio-analysis tool:
> mean-variance and CVaR optimisation, ESG constraints, Monte Carlo, walk-forward
> backtests and factor exposure, each documented and tested against known answers.
>
> Because of your work on <their topic>, I would value about two hours of your review:
> seven short checks with answers you can verify yourself, and five questions. The
> methodology and test evidence are here: <REPO>/tree/main/docs/methodology.
>
> If you agree, I would credit you as a reviewer only with your permission. Would you be
> willing, or could you suggest a colleague?
>
> Kind regards,
> <name>

### 10.6 Agreeing the terms (short, in writing; an email reply is enough)

- What they review (the tasks and questions above) and by when.
- Unpaid, or the fixed fee.
- Whether you may name them and quote them, and that they see the quote before it appears.
- Their findings are advice to you, not an endorsement of any investment, and they carry
  no liability for the product.
- Anything they tell you about their own firm stays confidential.

### 10.7 After the review

- Fix every number they found wrong, with a test reproducing their case.
- Record each finding and what was done in `DECISIONS.md` (a new D- entry) and
  `CHANGELOG.md`.
- With permission, add a "Reviewed by" line to `README.md` and the methodology overview.

---

## Done when

- [ ] Two-factor sign-in on every account
- [ ] WikiRate keys set; the live check's WikiRate line passes
- [ ] Site on the custom domain; sign-in, saving and the live smoke test pass there
- [ ] Render, Cloudflare and Actions working from the repository
- [ ] Repository security settings on; `main` protected
- [ ] Secrets rotated where needed
- [ ] Legal details checked; lawyer's comments applied
- [ ] FRED key set (optional)
- [ ] Email to Prof. French sent; reply kept
- [ ] One outside review received, its findings fixed and recorded
