import datetime as dt
import uuid

import jwt
from fastapi.testclient import TestClient

from ardentum.api.auth import DEV_ISSUER
from tests.api.conftest import login

PORTFOLIO = {
    "name": "Core",
    "dataset_id": "demo",
    "weights": {"NWS.SYN": 0.4, "GOVB.SYN": 0.6},
    "spec": {"objective": "min_volatility"},
}


def test_protected_endpoints_require_auth(client: TestClient) -> None:
    r = client.get("/api/v1/portfolios")
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "unauthorized"
    r = client.get("/api/v1/portfolios", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    r = client.get("/api/v1/portfolios", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_expired_and_forged_tokens_rejected(client: TestClient) -> None:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "sub": str(uuid.uuid4()),
        "aud": "authenticated",
        "iss": DEV_ISSUER,
        "exp": int((now - dt.timedelta(minutes=1)).timestamp()),
    }
    expired = jwt.encode(claims, "test-secret-that-is-long-enough-0123456789", algorithm="HS256")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert "expired" in r.json()["error"]["message"]
    claims["exp"] = int((now + dt.timedelta(hours=1)).timestamp())
    forged = jwt.encode(claims, "some-other-secret-that-is-long-enough-000", algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code
        == 401
    )
    none_alg = jwt.encode(claims, key=None, algorithm="none")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {none_alg}"}).status_code
        == 401
    )


def test_portfolio_crud_and_isolation(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post("/api/v1/portfolios", json=PORTFOLIO, headers=auth)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get("/api/v1/portfolios", headers=auth).json()[0]["id"] == pid
    upd = {**PORTFOLIO, "name": "Core v2", "weights": {"NWS.SYN": 0.5, "GOVB.SYN": 0.5}}
    r = client.put(f"/api/v1/portfolios/{pid}", json=upd, headers=auth)
    assert r.status_code == 200
    assert r.json()["name"] == "Core v2"
    assert r.json()["weights"] == {"NWS.SYN": 0.5, "GOVB.SYN": 0.5}

    other = login(client, "someone-else@example.com")
    assert client.get(f"/api/v1/portfolios/{pid}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/portfolios/{pid}", headers=other).status_code == 404
    assert client.get("/api/v1/portfolios", headers=other).json() == []

    csv = client.get(f"/api/v1/portfolios/{pid}/export?format=csv", headers=auth)
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == "ticker,weight"
    js = client.get(f"/api/v1/portfolios/{pid}/export?format=json", headers=auth)
    assert js.json()["name"] == "Core v2"

    assert client.delete(f"/api/v1/portfolios/{pid}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/portfolios/{pid}", headers=auth).status_code == 404


def test_portfolio_validation(client: TestClient, auth: dict[str, str]) -> None:
    bad = {**PORTFOLIO, "weights": {"NWS.SYN": 0.4, "GOVB.SYN": 0.4}}
    r = client.post("/api/v1/portfolios", json=bad, headers=auth)
    assert r.status_code == 422
    assert "sum to 1" in r.json()["error"]["message"]


PRICES = "date,AAA,BBB,CCC\n" + "\n".join(
    f"{(dt.date(2023, 1, 2) + dt.timedelta(days=i)).isoformat()},{100 + i * 0.1 + (i % 7) * 0.3:.4f},"
    f"{50 + (i % 11) * 0.2 + i * 0.05:.4f},{20 + (i % 5) * 0.1 + i * 0.02:.4f}"
    for i in range(120)
)
META = "ticker,name,sector,esg_score,esg_source\nAAA,Alpha,Tech,70,VendorX\nBBB,Beta,Energy,30,VendorX\n"


def test_dataset_upload_and_use(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/v1/datasets",
        data={"name": "My data"},
        files={"prices": ("p.csv", PRICES, "text/csv"), "metadata": ("m.csv", META, "text/csv")},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    ds = r.json()
    assert ds["is_synthetic"] is False
    assert {a["ticker"] for a in ds["assets"]} == {"AAA", "BBB", "CCC"}
    aaa = next(a for a in ds["assets"] if a["ticker"] == "AAA")
    assert aaa["esg_source"] == "VendorX"
    listed = client.get("/api/v1/datasets", headers=auth).json()
    assert any(d["id"] == ds["id"] and d["owned"] for d in listed)
    # Anonymous callers cannot see it.
    assert client.get(f"/api/v1/datasets/{ds['id']}").status_code == 404

    body = {
        "universe": {"dataset_id": ds["id"], "tickers": ["AAA", "BBB", "CCC"]},
        "objective": {"objective": "min_volatility"},
    }
    r = client.post("/api/v1/optimise", json=body, headers=auth)
    assert r.status_code == 200, r.text
    # CCC has no ESG score: an ESG constraint must fail loudly, not silently.
    body["constraints"] = {"min_esg_score": 50}
    r = client.post("/api/v1/optimise", json=body, headers=auth)
    assert r.status_code == 422
    assert "CCC" in r.json()["error"]["message"]
    body["constraints"] = {"min_esg_score": 50, "exclude_unscored_assets": True}
    r = client.post("/api/v1/optimise", json=body, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["excluded_unscored"] == ["CCC"]

    assert client.delete(f"/api/v1/datasets/{ds['id']}", headers=auth).status_code == 204


def test_upload_rejects_bad_csv(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/v1/datasets",
        data={"name": "bad"},
        files={"prices": ("p.csv", "date,AAA\n01/02/2024,1\n", "text/csv")},
        headers=auth,
    )
    assert r.status_code == 422
    r = client.post(
        "/api/v1/datasets", data={"name": "x"}, files={"prices": ("p.csv", PRICES, "text/csv")}
    )
    assert r.status_code == 401
