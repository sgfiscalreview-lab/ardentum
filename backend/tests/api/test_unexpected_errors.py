"""Unexpected server errors reach the browser as readable, CORS-enabled JSON."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ardentum.api.main import create_app
from ardentum.config import Settings

SITE = "https://site.example"


def _client() -> TestClient:
    app = create_app(Settings(env="test", database_url="sqlite://", cors_origins=[SITE]))

    @app.get("/api/v1/boom")
    def boom() -> None:
        raise RuntimeError("internal detail that must not leak")

    return TestClient(app, raise_server_exceptions=False)


def test_unexpected_error_keeps_cors_and_reference() -> None:
    r = _client().get("/api/v1/boom", headers={"Origin": SITE, "X-Request-ID": "abc-123"})
    assert r.status_code == 500
    # Without this header the browser hides the response and reports a network error.
    assert r.headers["access-control-allow-origin"] == SITE
    assert r.headers["x-request-id"] == "abc-123"
    body = r.json()["error"]
    assert body["type"] == "internal_error"
    assert "abc-123" in body["message"]
    assert "internal detail" not in r.text


def test_malformed_request_id_is_replaced() -> None:
    r = _client().get("/api/v1/health", headers={"X-Request-ID": "x" * 200})
    assert r.status_code == 200
    rid = r.headers["x-request-id"]
    assert len(rid) == 16
    assert rid != "x" * 200
