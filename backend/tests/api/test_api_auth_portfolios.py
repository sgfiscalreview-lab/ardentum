import datetime as dt
import io
import uuid

import httpx
import jwt
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ardentum.api.auth import DEV_ISSUER
from ardentum.db.models import User
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


# Trading days: daily statistics assume 252 a year, so calendar-day prices are refused.
TRADING_DAYS = [d.date() for d in pd.bdate_range("2023-01-02", periods=120)]
PRICES = "date,AAA,BBB,CCC\n" + "\n".join(
    f"{TRADING_DAYS[i].isoformat()},{100 + i * 0.1 + (i % 7) * 0.3:.4f},"
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


def _upload_with_cash(client: TestClient, auth: dict[str, str]) -> tuple[str, str]:
    lines = PRICES.split("\n")
    prices = "\n".join([lines[0] + ",CASH", *(f"{line},100" for line in lines[1:])])
    up = client.post(
        "/api/v1/datasets",
        data={"name": "With cash"},
        files={"prices": ("p.csv", prices, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 201, up.text
    return up.json()["id"], prices


def test_a_constant_asset_does_not_blank_the_other_correlations(
    client: TestClient, auth: dict[str, str]
) -> None:
    dataset_id, prices = _upload_with_cash(client, auth)
    tickers = ["AAA", "BBB", "CASH"]
    universe = {"dataset_id": dataset_id, "tickers": tickers}
    r = client.post("/api/v1/analytics", json={"universe": universe}, headers=auth)
    assert r.status_code == 200, r.text
    corr = r.json()["correlation"]
    returns = pd.read_csv(io.StringIO(prices), index_col=0)[tickers].pct_change().dropna()
    assert corr[0][1] == pytest.approx(returns["AAA"].corr(returns["BBB"]))
    assert corr[2] == [None, None, None]
    assert "CASH" in r.json()["correlation_note"]


def test_a_first_sign_in_racing_another_request_is_not_an_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = login(client, "race@example.com")
    assert client.get("/api/v1/portfolios", headers=headers).status_code == 200  # row created
    # Another request inserted the user between this request's read and its insert.
    real_get = Session.get

    def miss_users(self: Session, entity: object, ident: object, **kw: object) -> object:
        return None if entity is User else real_get(self, entity, ident, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(Session, "get", miss_users)
    r = client.get("/api/v1/portfolios", headers=headers)
    assert r.status_code == 200, r.text


def test_undefined_figures_are_na_with_a_reason_not_zero(
    client: TestClient, auth: dict[str, str]
) -> None:
    dataset_id, _ = _upload_with_cash(client, auth)
    universe = {"dataset_id": dataset_id, "tickers": ["AAA", "BBB", "CASH"]}
    # Sample covariance keeps cash riskless (shrinkage would give it some variance).
    sample = {"covariance_estimator": "sample"}
    body = {
        "universe": universe,
        "estimation": sample,
        "portfolios": [
            {"name": "Cash", "weights": {"CASH": 1.0}},
            {"name": "Mix", "weights": {"AAA": 0.5, "BBB": 0.5}},
        ],
    }
    r = client.post("/api/v1/compare", json=body, headers=auth)
    assert r.status_code == 200, r.text
    cash, mix = r.json()["portfolios"]
    assert cash["sharpe_ratio"] is None
    assert cash["top_risk_contributors"] == []
    assert any(n.startswith("Sharpe ratio n/a") for n in cash["notes"])
    assert any(n.startswith("Largest risk contributors n/a") for n in cash["notes"])
    assert any("no ESG score for CASH" in n for n in cash["notes"])
    assert mix["sharpe_ratio"] is not None
    assert len(mix["top_risk_contributors"]) == 2
    assert "Cash" in r.json()["return_correlation_note"]

    # Risk contributions of a riskless portfolio are n/a with the reason, not zeros.
    opt = {
        "universe": {**universe, "tickers": ["CASH"]},
        "estimation": sample,
        "objective": {"objective": "min_volatility"},
    }
    r = client.post("/api/v1/optimise", json=opt, headers=auth)
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["holdings"][0]["risk_contribution_pct"] is None
    assert "zero volatility" in result["risk_contributions_note"]


def test_upload_says_which_return_frequencies_the_prices_support(
    client: TestClient, auth: dict[str, str]
) -> None:
    def upload(dates: pd.DatetimeIndex) -> httpx.Response:
        rows = "\n".join(
            f"{d.date()},{100 + i * 0.1 + (i % 3) * 0.2:.4f}" for i, d in enumerate(dates)
        )
        return client.post(
            "/api/v1/datasets",
            data={"name": "Frequencies"},
            files={"prices": ("p.csv", "date,AAA\n" + rows, "text/csv")},
            headers=auth,
        )

    r = upload(pd.bdate_range("2023-01-02", periods=120))
    assert r.status_code == 201, r.text
    assert r.json()["frequencies"] == ["daily", "weekly", "monthly"]
    assert r.json()["notes"] == []

    # Calendar days: daily statistics would assume 252 of them a year.
    r = upload(pd.date_range("2023-01-02", periods=400, freq="D"))
    assert r.json()["frequencies"] == ["weekly", "monthly"]
    assert "weekend" in r.json()["notes"][0]

    # Quarterly prices cannot give any supported frequency: refused at upload.
    r = upload(pd.date_range("2000-03-31", periods=60, freq="QE"))
    assert r.status_code == 422
    assert "At least monthly prices are needed" in r.json()["error"]["message"]
