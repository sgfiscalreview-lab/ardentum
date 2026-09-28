"""Mean-CVaR frontier endpoint and background job."""

from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from tests.api.conftest import universe


def test_cvar_frontier_endpoint(client: TestClient) -> None:
    r = client.post(
        "/api/v1/frontier/cvar",
        json={"universe": universe(), "n_points": 8, "cvar_confidence": 0.95},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["frequency"] == "daily"
    assert body["cvar_confidence"] == 0.95
    assert body["observations"] > 100
    pts = body["points"]
    assert len(pts) == 8
    assert all(b["expected_return"] > a["expected_return"] for a, b in itertools.pairwise(pts))
    assert all(b["cvar"] >= a["cvar"] - 1e-9 for a, b in itertools.pairwise(pts))
    assert all(p["cvar"] >= p["var"] - 1e-12 for p in pts)
    assert all(abs(sum(p["weights"].values()) - 1) < 1e-6 for p in pts)
    # The minimum-CVaR portfolio has the lowest CVaR of any portfolio shown, and no
    # mean-variance portfolio has lower CVaR than the mean-CVaR frontier at or below its
    # return (the frontier is nondecreasing, so this holds on the grid).
    mv = body["mean_variance_points"]
    assert mv
    min_cvar = body["min_cvar"]["cvar"]
    for q in mv:
        assert q["cvar"] >= min_cvar - 1e-9
        below = [p["cvar"] for p in pts if p["expected_return"] <= q["expected_return"] + 1e-12]
        if below:
            assert max(below) <= q["cvar"] + 1e-7
    assert {a["ticker"] for a in body["assets"]} == set(universe()["tickers"])  # type: ignore[arg-type]


def test_cvar_frontier_validation(client: TestClient) -> None:
    r = client.post("/api/v1/frontier/cvar", json={"universe": universe(), "cvar_confidence": 0.3})
    assert r.status_code == 422
    r = client.post(
        "/api/v1/frontier/cvar",
        json={"universe": universe(start="2021-10-01"), "cvar_confidence": 0.995},
    )
    assert r.status_code == 422
    assert "observations" in r.json()["error"]["message"]


def test_cvar_frontier_as_background_job(client: TestClient) -> None:
    req = {"universe": universe(), "n_points": 5}
    r = client.post("/api/v1/jobs", json={"kind": "cvar_frontier", "request": req})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{job_id}?wait=5").json()
        if job["status"] in ("succeeded", "failed"):
            break
    assert job["status"] == "succeeded", job
    sync = client.post("/api/v1/frontier/cvar", json=req).json()
    assert job["result"]["points"] == sync["points"]
