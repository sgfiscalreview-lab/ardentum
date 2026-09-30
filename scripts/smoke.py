#!/usr/bin/env python3
"""Smoke test for a deployed Ardentum: the API, the website and Supabase sign-in settings.

    python3 scripts/smoke.py --api https://<api> --site https://<site> \\
        [--supabase https://<ref>.supabase.co --publishable-key sb_publishable_...]

Checks what can be seen from outside: health, production settings, CORS for the site,
live data sources (Ken French, ECB rates via Frankfurter, BIS policy rates, WikiRate, FRED
if configured), a background calculation, the settings baked into the website at build time, and which
sign-in providers are switched on. Read-only apart from one anonymous background job,
which expires after a day. Standard library only. Exits 1 if a required check fails;
warnings are optional items.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

UA = "ardentum-smoke/1"
KF_UNIVERSE = {
    "dataset_id": "kf12",
    "tickers": ["NODUR", "HLTH", "MONEY"],
    "start": "2015-01-01",
    "frequency": "monthly",
}


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


def request(
    method: str,
    url: str,
    body: object | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60,
) -> Response:
    data = json.dumps(body).encode() if body is not None else None
    # Marked as monitoring so the check is left out of the public usage counts.
    h = {"User-Agent": UA, "X-Ardentum-Monitor": "1", **(headers or {})}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            return Response(r.status, hdrs, r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in e.headers.items()}
        return Response(e.code, hdrs, e.read().decode("utf-8", "replace"))


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, name: str, detail: str) -> None:
        self.rows.append((level, name, detail))
        print(f"{level:4}  {name}: {detail}", flush=True)

    def ok(self, name: str, detail: str = "") -> None:
        self.add("PASS", name, detail)

    def fail(self, name: str, detail: str) -> None:
        self.add("FAIL", name, detail)

    def warn(self, name: str, detail: str) -> None:
        self.add("WARN", name, detail)

    def check(self, name: str, fn: Any) -> Any:
        try:
            return fn()
        except Exception as e:  # a check that crashes is a failed check
            self.fail(name, f"{type(e).__name__}: {e}")
            return None

    @property
    def failed(self) -> bool:
        return any(level == "FAIL" for level, _, _ in self.rows)

    def summary_markdown(self) -> str:
        lines = ["| Result | Check | Detail |", "|---|---|---|"]
        for level, name, detail in self.rows:
            lines.append(f"| {level} | {name} | {detail.replace('|', '/')} |")
        return "\n".join(lines) + "\n"


def error_message(r: Response) -> str:
    try:
        return str(r.json()["error"]["message"])
    except Exception:
        return r.text[:200]


def describe(r: Response) -> str:
    """Status, serving host and the start of the page, to tell apart a wrong address,
    a missing deployment and a build without the expected files."""
    text = re.sub(r"<[^>]+>", " ", r.text)
    text = re.sub(r"\s+", " ", text).strip()[:160]
    server = r.headers.get("server", "?")
    return f"HTTP {r.status} from {server}: {text!r}"


def check_api(rep: Report, api: str, site: str) -> None:
    v1 = api.rstrip("/") + "/api/v1"

    def health() -> None:
        # A free Render instance may be asleep: the first request can take a minute.
        start = time.monotonic()
        r = request("GET", f"{v1}/health", timeout=180)
        waited = time.monotonic() - start
        if r.status != 200:
            rep.fail("API health", f"HTTP {r.status}: {r.text[:200]}")
            return
        rep.ok("API health", f"answered in {waited:.1f} s")

    def health_db() -> None:
        r = request("GET", f"{v1}/health/db", timeout=60)
        if r.status == 200 and r.json().get("database") == "ok":
            rep.ok("Database", "reachable")
        else:
            rep.fail("Database", f"HTTP {r.status}: {r.text[:200]}")

    def meta() -> None:
        r = request("GET", f"{v1}/meta")
        m = r.json()
        detail = f"version {m.get('version')}, environment {m.get('environment')}"
        if m.get("environment") == "production" and m.get("auth_mode") == "supabase":
            rep.ok("Production settings", detail + ", Supabase sign-in")
        else:
            rep.fail("Production settings", detail + f", auth {m.get('auth_mode')}")

    def cors() -> None:
        r = request(
            "OPTIONS",
            f"{v1}/optimise",
            headers={
                "Origin": site,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        allowed = r.headers.get("access-control-allow-origin")
        if r.status == 200 and allowed == site:
            rep.ok("CORS", f"the API accepts calls from {site}")
        else:
            rep.fail(
                "CORS",
                f"the API refuses calls from {site} (HTTP {r.status}, allowed: {allowed}). "
                f'Set ARDENTUM_CORS_ORIGINS to ["{site}"] on the API host and redeploy.',
            )

    def auth_guard() -> None:
        me = request("GET", f"{v1}/auth/me")
        dev = request("POST", f"{v1}/auth/dev-login", {"email": "smoke@example.com"})
        if me.status == 401 and dev.status != 200:
            rep.ok("Sign-in required", "account endpoints refuse anonymous and dev sign-in")
        else:
            rep.fail("Sign-in required", f"/auth/me HTTP {me.status}, dev-login HTTP {dev.status}")

    def ken_french() -> None:
        # The first analysis downloads and caches the industry returns.
        start = time.monotonic()
        r = request("POST", f"{v1}/analytics", {"universe": KF_UNIVERSE}, timeout=300)
        if r.status != 200:
            rep.fail("Ken French data", f"HTTP {r.status}: {error_message(r)}")
            return
        rep.ok("Ken French data", f"analytics on 3 industries in {time.monotonic() - start:.1f} s")

    def risk_free() -> None:
        r = request("POST", f"{v1}/risk-free", {"source": "kenfrench_rf", "start": "2015-01-01"})
        if r.status == 200:
            rep.ok("Risk-free rate (Fama-French)", f"{r.json()['rate']:.4f} a year since 2015")
        else:
            rep.fail("Risk-free rate (Fama-French)", f"HTTP {r.status}: {error_message(r)}")
        sources = {s["id"]: s for s in request("GET", f"{v1}/risk-free/sources").json()}
        if not sources.get("fred_dgs3mo", {}).get("available"):
            rep.warn("FRED", "no FRED key on the API (optional; guide step 10)")
            return
        r = request("POST", f"{v1}/risk-free", {"source": "fred_dgs3mo", "start": "2015-01-01"})
        if r.status == 200:
            rep.ok("FRED", f"3-month T-bill {r.json()['rate']:.4f} a year since 2015")
        else:
            rep.fail("FRED", f"HTTP {r.status}: {error_message(r)}")

    def fx() -> None:
        body = {"universe": {**KF_UNIVERSE, "base_currency": "EUR"}}
        r = request("POST", f"{v1}/analytics", body, timeout=180)
        if r.status == 200:
            rep.ok("ECB exchange rates (Frankfurter)", "analytics in EUR succeeded")
        else:
            rep.fail("ECB exchange rates (Frankfurter)", f"HTTP {r.status}: {error_message(r)}")
            return
        hedged = {"universe": {**KF_UNIVERSE, "base_currency": "EUR", "currency_hedged": True}}
        r = request("POST", f"{v1}/analytics", hedged, timeout=180)
        if r.status == 200:
            rep.ok("Policy rates for hedging (BIS)", "hedged analytics in EUR succeeded")
        else:
            rep.fail("Policy rates for hedging (BIS)", f"HTTP {r.status}: {error_message(r)}")

    def wikirate() -> None:
        r = request("GET", f"{v1}/esg/open/metrics?q=greenhouse&limit=5", timeout=120)
        if r.status == 200 and r.json():
            rep.ok("WikiRate open ESG data", f"{len(r.json())} metrics found for 'greenhouse'")
        elif r.status == 200:
            rep.fail("WikiRate open ESG data", "search returned no metrics")
        else:
            rep.fail("WikiRate open ESG data", f"HTTP {r.status}: {error_message(r)}")

    def optimise() -> None:
        r = request("POST", f"{v1}/optimise", {"universe": KF_UNIVERSE}, timeout=180)
        if r.status != 200:
            rep.fail("Optimisation", f"HTTP {r.status}: {error_message(r)}")
            return
        result = r.json()["result"]
        total = sum(h["weight"] for h in result["holdings"])
        if abs(total - 1) < 1e-6:
            rep.ok("Optimisation", f"weights sum to 1, solver {result['solver']}")
        else:
            rep.fail("Optimisation", f"weights sum to {total}")

    def background_job() -> None:
        body = {
            "kind": "montecarlo",
            "request": {
                "universe": KF_UNIVERSE,
                "weights": {"NODUR": 0.4, "HLTH": 0.3, "MONEY": 0.3},
                "n_paths": 1000,
                "horizon_years": 5,
                "seed": 7,
            },
        }
        start = time.monotonic()
        r = request("POST", f"{v1}/jobs", body)
        if r.status != 202:
            rep.fail("Background job", f"HTTP {r.status}: {error_message(r)}")
            return
        job = r.json()
        for _ in range(12):
            if job["status"] in ("succeeded", "failed"):
                break
            job = request("GET", f"{v1}/jobs/{job['id']}?wait=20", timeout=60).json()
        took = f"{time.monotonic() - start:.1f} s"
        if job["status"] == "succeeded" and "percentiles" in (job.get("result") or {}):
            rep.ok("Background job", f"Monte Carlo simulation finished in {took}")
        else:
            rep.fail("Background job", f"status {job['status']} after {took}: {job.get('error')}")

    def usage() -> None:
        r = request("GET", f"{v1}/usage")
        if r.status != 200:
            rep.fail("Usage counts", f"HTTP {r.status}: {error_message(r)}")
            return
        u = r.json()
        rep.ok("Usage counts", f"{u['total_calculations']} calculations counted since {u['since']}")

    rep.check("API health", health)
    if rep.rows and rep.rows[-1][:2] == ("FAIL", "API health"):
        return  # nothing else can work
    for name, fn in [
        ("Database", health_db),
        ("Production settings", meta),
        ("CORS", cors),
        ("Sign-in required", auth_guard),
        ("Ken French data", ken_french),
        ("Risk-free rate (Fama-French)", risk_free),
        ("ECB exchange rates (Frankfurter)", fx),
        ("WikiRate open ESG data", wikirate),
        ("Optimisation", optimise),
        ("Background job", background_job),
        ("Usage counts", usage),
    ]:
        rep.check(name, fn)


def check_site(rep: Report, site: str, api: str, supabase: str | None, key: str | None) -> None:
    base = site.rstrip("/")

    def pages() -> None:
        r = request("GET", base + "/")
        if r.status != 200 or "shows its working" not in r.text:
            # Tell apart "nothing deployed at this address" from a routing problem.
            index = request("GET", base + "/index.html")
            hint = (
                "no deployment is serving this address; check the project's address and "
                "its latest deployment in Cloudflare (Workers & Pages > project > Deployments)"
                if index.status == 404
                else f"/index.html gives HTTP {index.status}"
            )
            rep.fail("Website", f"landing page not found at {base}/; {describe(r)}; {hint}")
            return
        rep.ok("Website", "landing page loads")
        if "x-frame-options" in r.headers:
            rep.ok("Security headers", "public/_headers is applied")
        else:
            rep.warn("Security headers", "missing; check that the build output is `out`")

        # Settings are baked into the JavaScript at build time; look for them.
        scripts: set[str] = set()
        for path in ("/", "/app"):
            html = request("GET", base + path).text
            scripts |= set(re.findall(r'src="(/_next/static/[^"]+?\.js)"', html))
        code = "".join(request("GET", base + s).text for s in sorted(scripts))
        wanted = {
            "NEXT_PUBLIC_API_BASE": urlparse(api).netloc,
            "NEXT_PUBLIC_SUPABASE_URL": urlparse(supabase).netloc if supabase else None,
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": key,
        }
        for var, value in wanted.items():
            if value is None:
                continue
            if value in code:
                rep.ok(f"Build setting {var}", "present in the website's code")
            else:
                rep.fail(
                    f"Build setting {var}",
                    "not found in the website's code; set it in Cloudflare Pages > Settings > "
                    "Variables and Secrets, then retry the latest deployment",
                )

    def legal() -> None:
        for path, title in (
            ("/terms", "Terms of Service"),
            ("/privacy", "Privacy Policy"),
            ("/cookies", "Cookie Policy"),
            ("/licences", "Licences"),
        ):
            r = request("GET", base + path)
            if r.status != 200 or title not in r.text:
                rep.fail(f"Page {path}", f"HTTP {r.status}; heading '{title}' not found")
            elif "has not set its operator name" in r.text:
                rep.warn(
                    f"Page {path}",
                    "operator name, contact and governing law not set (NEXT_PUBLIC_LEGAL_*, "
                    "guide step 11)",
                )
            else:
                rep.ok(f"Page {path}", "legal details filled in")

    def public_pages() -> None:
        for path, heading in (
            ("/tour", "Ardentum in eight steps"),
            ("/usage", "How much Ardentum is used"),
        ):
            r = request("GET", base + path)
            if r.status == 200 and heading in r.text:
                rep.ok(f"Page {path}", "loads")
            else:
                rep.fail(f"Page {path}", f"HTTP {r.status}; heading '{heading}' not found")

    def screenshots() -> None:
        r = request("GET", base + "/screenshots/optimise-light.png")
        if r.status == 200:
            rep.ok("Screenshots", "landing-page images load")
        else:
            rep.fail("Screenshots", f"HTTP {r.status}")

    rep.check("Website", pages)
    rep.check("Legal pages", legal)
    rep.check("Tour and usage pages", public_pages)
    rep.check("Screenshots", screenshots)


def check_supabase(rep: Report, supabase: str, key: str) -> None:
    base = supabase.rstrip("/")

    def providers() -> None:
        r = request("GET", f"{base}/auth/v1/settings", headers={"apikey": key})
        if r.status != 200:
            rep.fail("Supabase", f"HTTP {r.status}: {r.text[:200]}")
            return
        external = r.json().get("external", {})
        for p in ("google", "github"):
            if external.get(p):
                rep.ok(f"Sign-in with {p.title()}", "switched on in Supabase")
            else:
                rep.fail(
                    f"Sign-in with {p.title()}",
                    "off; Supabase > Authentication > Sign In / Providers (guide step 6)",
                )

    def signing_keys() -> None:
        keys = request("GET", f"{base}/auth/v1/.well-known/jwks.json").json().get("keys", [])
        if keys:
            algs = sorted({k.get("alg", "?") for k in keys})
            rep.ok("Token signing keys", f"published ({', '.join(algs)}); the API verifies them")
        else:
            rep.fail(
                "Token signing keys",
                "the project still signs with the legacy shared secret, so the API cannot "
                "verify sign-ins unless ARDENTUM_SUPABASE_JWT_SECRET is set. Migrate: "
                "Supabase > Project Settings > JWT Keys (guide step 2.4)",
            )

    rep.check("Supabase", providers)
    rep.check("Token signing keys", signing_keys)


def plain_url(rep: Report, name: str, value: str) -> str:
    """Accept a value pasted as a Markdown link, [url](url), but flag it: other tools
    (the keep-alive's curl, the website build) would use it as written and fail."""
    m = re.fullmatch(r"\s*\[([^\]]+)\]\(([^)]+)\)\s*", value)
    if not m:
        return value.strip()
    rep.fail(
        f"Setting {name}",
        f"written as a Markdown link ({value}); change it to the plain address {m.group(2)}",
    )
    return m.group(2).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--api", required=True, help="API base URL")
    ap.add_argument("--site", required=True, help="website URL")
    ap.add_argument("--supabase", help="Supabase project URL")
    ap.add_argument("--publishable-key", help="Supabase publishable key (public)")
    args = ap.parse_args()

    rep = Report()
    api = plain_url(rep, "API_URL", args.api)
    site = plain_url(rep, "SITE_URL", args.site).rstrip("/")
    supabase = plain_url(rep, "SUPABASE_URL", args.supabase) if args.supabase else None
    check_api(rep, api, site)
    check_site(rep, site, api, supabase, args.publishable_key)
    if supabase and args.publishable_key:
        check_supabase(rep, supabase, args.publishable_key)

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Live smoke test\n\n" + rep.summary_markdown())
    n_fail = sum(1 for level, _, _ in rep.rows if level == "FAIL")
    n_warn = sum(1 for level, _, _ in rep.rows if level == "WARN")
    print(f"\n{len(rep.rows)} checks: {n_fail} failed, {n_warn} warnings")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
