"""One user's data is invisible to everyone else, through every route that can reach it.

Alice saves a portfolio and uploads a dataset. Bob, signed in, and an anonymous caller
try every way in: reading, changing, deleting, exporting, analysing (directly and as a
background job). Each answer is "not found", never the data, and Alice's data survives.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import login
from tests.api.test_api_auth_portfolios import META, PORTFOLIO, PRICES


def _wait(client: TestClient, job_id: str, headers: dict[str, str]) -> dict[str, Any]:
    for _ in range(40):
        r = client.get(f"/api/v1/jobs/{job_id}?wait=5", headers=headers)
        if r.status_code != 200 or r.json()["status"] in ("succeeded", "failed"):
            return {"http": r.status_code, **(r.json() if r.status_code == 200 else {})}
    raise AssertionError("job did not finish")


def test_another_user_cannot_reach_your_data(client: TestClient) -> None:
    alice = login(client, "alice@example.com")
    pid = client.post("/api/v1/portfolios", json=PORTFOLIO, headers=alice).json()["id"]
    ds = client.post(
        "/api/v1/datasets",
        data={"name": "Alice's data"},
        files={"prices": ("p.csv", PRICES, "text/csv"), "metadata": ("m.csv", META, "text/csv")},
        headers=alice,
    ).json()["id"]

    bob = login(client, "bob@example.com")
    for headers in (bob, {}):
        anonymous = not headers
        expected = 401 if anonymous else 404
        assert client.get(f"/api/v1/portfolios/{pid}", headers=headers).status_code == expected
        changed = {**PORTFOLIO, "name": "taken"}
        r = client.put(f"/api/v1/portfolios/{pid}", json=changed, headers=headers)
        assert r.status_code == expected
        r = client.get(f"/api/v1/portfolios/{pid}/export?format=json", headers=headers)
        assert r.status_code == expected
        assert client.delete(f"/api/v1/portfolios/{pid}", headers=headers).status_code == expected
        assert client.delete(f"/api/v1/datasets/{ds}", headers=headers).status_code == expected

        # Datasets can be read anonymously when they are public (demo data), so these
        # answer "not found" for everyone but the owner.
        assert client.get(f"/api/v1/datasets/{ds}", headers=headers).status_code == 404
        listed = client.get("/api/v1/datasets", headers=headers).json()
        assert ds not in {d["id"] for d in listed}
        body = {"universe": {"dataset_id": ds, "tickers": ["AAA", "BBB"]}}
        assert client.post("/api/v1/analytics", json=body, headers=headers).status_code == 404
        r = client.post(
            "/api/v1/jobs", json={"kind": "analytics", "request": body}, headers=headers
        )
        if r.status_code == 202:
            job = _wait(client, r.json()["id"], headers)
            assert job["status"] == "failed"
            assert job["error"]["status"] == 404
            assert job["result"] is None
        else:
            assert r.status_code == 404

    # Bob's account export holds only Bob's (empty) data.
    me = client.get("/api/v1/auth/me/export", headers=bob).json()
    assert me["portfolios"] == []
    assert me["datasets"] == []

    # Nothing of Alice's changed.
    assert client.get(f"/api/v1/portfolios/{pid}", headers=alice).json()["name"] == "Core"
    assert client.get(f"/api/v1/datasets/{ds}", headers=alice).status_code == 200
