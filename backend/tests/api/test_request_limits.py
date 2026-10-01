"""Request limits: per-client budgets, body size caps and refusals browsers can read."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ardentum.api.bodylimit import JSON_BODY_LIMIT
from ardentum.api.main import create_app
from ardentum.api.ratelimit import budget_for
from ardentum.config import Settings
from ardentum.db.models import Base
from tests.api.conftest import login, universe

ORIGIN = {"Origin": "http://localhost:3000"}


def _portfolio(name: str, **kw: object) -> dict[str, object]:
    return {"name": name, "dataset_id": "demo", "weights": {"NWS.SYN": 1.0}, **kw}


@pytest.fixture
def limited(settings: Settings) -> Iterator[TestClient]:
    s = settings.model_copy(update={"compute_rate_limit": 2, "write_rate_limit": 3})
    app = create_app(s)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def test_budgets() -> None:
    assert budget_for("POST", "/api/v1/optimise") == "compute"
    assert budget_for("POST", "/api/v1/jobs") == "compute"
    assert budget_for("POST", "/api/v1/portfolios") == "write"
    assert budget_for("PUT", "/api/v1/portfolios/x") == "write"
    assert budget_for("DELETE", "/api/v1/auth/me") == "write"
    assert budget_for("POST", "/api/v1/datasets") == "write"
    assert budget_for("GET", "/api/v1/esg/open/companies") == "write"  # calls WikiRate
    assert budget_for("GET", "/api/v1/portfolios") is None
    assert budget_for("GET", "/api/v1/jobs/abc") is None  # polling a job is free
    assert budget_for("POST", "/somewhere-else") is None


def test_writes_have_their_own_budget(limited: TestClient) -> None:
    alice = login(limited)
    codes = [
        limited.post("/api/v1/portfolios", json=_portfolio(f"p{i}"), headers=alice).status_code
        for i in range(4)
    ]
    assert codes == [201, 201, 201, 429]
    r = limited.post("/api/v1/portfolios", json=_portfolio("again"), headers=alice)
    assert r.json()["error"]["message"].startswith("Too many requests")
    # Reads stay free, and calculations count against their own budget.
    assert limited.get("/api/v1/portfolios", headers=alice).status_code == 200
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    assert limited.post("/api/v1/analytics", json=body, headers=alice).status_code == 200


def test_refusals_carry_cors_headers(limited: TestClient) -> None:
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    for _ in range(2):
        limited.post("/api/v1/analytics", json=body, headers=ORIGIN)
    r = limited.post("/api/v1/analytics", json=body, headers=ORIGIN)
    assert r.status_code == 429
    # Without these the browser hides the message and reports a network error.
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()


def test_oversized_bodies_are_refused(client: TestClient) -> None:
    big = b"x" * (JSON_BODY_LIMIT + 1)
    headers = {**ORIGIN, "Content-Type": "application/json"}
    r = client.post("/api/v1/analytics", content=big, headers=headers)
    assert r.status_code == 413
    assert r.json()["error"]["type"] == "payload_too_large"
    assert "at most 1 MB" in r.json()["error"]["message"]
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]

    # A body without a declared length is counted as it arrives.
    def chunks() -> Iterator[bytes]:
        for _ in range(JSON_BODY_LIMIT // 65536 + 2):
            yield b"x" * 65536

    r = client.post("/api/v1/analytics", content=chunks(), headers=headers)
    assert r.status_code == 413
    assert r.json()["error"]["type"] == "payload_too_large"


def test_uploads_may_be_larger(client: TestClient, settings: Settings) -> None:
    # A file bigger than the general cap passes the size check (and then needs a sign-in)...
    r = client.post(
        "/api/v1/datasets",
        data={"name": "big"},
        files={"prices": ("p.csv", b"x" * (2 * JSON_BODY_LIMIT), "text/csv")},
    )
    assert r.status_code == 401
    # ...but not more than that.
    r = client.post(
        "/api/v1/datasets",
        content=b"x" * (2 * settings.max_upload_bytes + 128 * 1024),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )
    assert r.status_code == 413


def test_framework_errors_use_the_error_format(client: TestClient) -> None:
    r = client.get("/api/v1/no-such-thing")
    assert r.status_code == 404
    assert r.json()["error"]["type"] == "not_found"
    r = client.delete("/api/v1/meta")
    assert r.status_code == 405
    assert r.json()["error"]["type"] == "method_not_allowed"
    assert "GET" in r.headers["allow"]


def test_saved_settings_are_bounded(client: TestClient, auth: dict[str, str]) -> None:
    spec = {"note": "x" * (70 * 1024)}
    r = client.post("/api/v1/portfolios", json=_portfolio("big", spec=spec), headers=auth)
    assert r.status_code == 422
    assert "64 KB" in r.json()["error"]["message"]
    ok = {"objective": {"objective": "max_sharpe"}, "universe": universe()}
    r = client.post("/api/v1/portfolios", json=_portfolio("fine", spec=ok), headers=auth)
    assert r.status_code == 201, r.text
