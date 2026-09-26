"""Account export and deletion (privacy): everything the user stored goes."""

from __future__ import annotations

import uuid

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ardentum.api.auth import Principal
from ardentum.config import AuthMode, Settings
from ardentum.db.models import Dataset, Portfolio, User
from ardentum.services import account
from tests.api.conftest import login
from tests.api.test_api_auth_portfolios import META, PORTFOLIO, PRICES


def _seed(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/v1/portfolios", json=PORTFOLIO, headers=auth).status_code == 201
    r = client.post(
        "/api/v1/datasets",
        data={"name": "Mine"},
        files={"prices": ("p.csv", PRICES, "text/csv"), "metadata": ("m.csv", META, "text/csv")},
        headers=auth,
    )
    assert r.status_code == 201, r.text


def test_export_contains_the_users_data_only(client: TestClient, auth: dict[str, str]) -> None:
    _seed(client, auth)
    other = login(client, "other@example.com")
    _seed(client, other)
    r = client.get("/api/v1/auth/me/export", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["email"] == "analyst@example.com"
    assert len(out["portfolios"]) == 1
    assert out["portfolios"][0]["weights"] == PORTFOLIO["weights"]
    assert out["datasets"][0]["name"] == "Mine"
    assert client.get("/api/v1/auth/me/export").status_code == 401


def test_delete_account_removes_everything(client: TestClient, auth: dict[str, str]) -> None:
    _seed(client, auth)
    other = login(client, "other@example.com")
    _seed(client, other)
    r = client.delete("/api/v1/auth/me", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["portfolios"], out["datasets"]) == (1, 1)
    assert out["identity_deleted"] is False  # dev mode: no identity provider
    assert "sign-in record" in out["message"]
    factory = client.app.state.sessionmaker  # type: ignore[attr-defined]
    with factory() as session:
        assert session.scalar(select(func.count(User.id))) == 1  # only the other user
        assert session.scalar(select(func.count(Portfolio.id))) == 1
        assert session.scalar(select(func.count(Dataset.id))) == 1
    # Signing in again starts an empty account.
    assert client.get("/api/v1/portfolios", headers=auth).json() == []
    # The other user's data is untouched.
    assert len(client.get("/api/v1/portfolios", headers=other).json()) == 1


@respx.mock
def test_supabase_identity_deleted_when_configured(settings: Settings) -> None:
    uid = uuid.uuid4()
    principal = Principal(user_id=uid, email="a@example.com")
    configured = settings.model_copy(
        update={
            "auth_mode": AuthMode.SUPABASE,
            "supabase_url": "https://proj.supabase.co",
            "supabase_service_key": "sb_secret_x",
        }
    )
    route = respx.delete(f"https://proj.supabase.co/auth/v1/admin/users/{uid}").mock(
        return_value=httpx.Response(200, json={})
    )
    assert account._delete_identity(configured, principal) is True
    assert route.calls.last.request.headers["apikey"] == "sb_secret_x"
    route.mock(return_value=httpx.Response(500))
    assert account._delete_identity(configured, principal) is False
    without_key = configured.model_copy(update={"supabase_service_key": None})
    assert account._delete_identity(without_key, principal) is False
