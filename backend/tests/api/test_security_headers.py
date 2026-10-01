"""Security headers on every answer, and no developer sign-in outside development."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ardentum.api.main import create_app
from ardentum.config import AuthMode, Settings


def test_answers_carry_security_headers(client: TestClient) -> None:
    for r in (client.get("/api/v1/health"), client.get("/api/v1/no-such-thing")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["strict-transport-security"].startswith("max-age=")
        assert r.headers["cross-origin-resource-policy"] == "same-origin"
        assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert client.get("/api/v1/meta").headers["cache-control"] == "no-store"


def test_api_documentation_may_load_swagger_ui(client: TestClient) -> None:
    r = client.get("/api/v1/docs")
    assert r.status_code == 200
    assert "https://cdn.jsdelivr.net" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_developer_sign_in_exists_only_in_dev_mode(settings: Settings) -> None:
    prod_like = settings.model_copy(
        update={"auth_mode": AuthMode.SUPABASE, "supabase_url": "https://example.supabase.co"}
    )
    with TestClient(create_app(prod_like)) as c:
        assert c.post("/api/v1/auth/dev-login", json={"email": "a@b.co"}).status_code == 404
        assert "/api/v1/auth/dev-login" not in c.get("/api/v1/openapi.json").json()["paths"]
    with TestClient(create_app(settings)) as c:
        assert "/api/v1/auth/dev-login" in c.get("/api/v1/openapi.json").json()["paths"]
