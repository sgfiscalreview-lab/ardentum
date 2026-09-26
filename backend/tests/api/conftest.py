from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ardentum.api.main import create_app
from ardentum.config import AuthMode, Environment, Settings
from ardentum.db.models import Base

DEMO_TICKERS = [
    "NWS.SYN",
    "MDC.SYN",
    "ARB.SYN",
    "GRD.SYN",
    "HRV.SYN",
    "GOVB.SYN",
    "PTR.SYN",
    "SOL.SYN",
]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env=Environment.TEST,
        # Set ARDENTUM_TEST_DATABASE_URL to run the API suite against PostgreSQL.
        database_url=os.environ.get("ARDENTUM_TEST_DATABASE_URL", "sqlite://"),
        auth_mode=AuthMode.DEV,
        dev_jwt_secret="test-secret-that-is-long-enough-0123456789",
        cors_origins=["http://localhost:3000"],
        compute_rate_limit=0,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def login(client: TestClient, email: str = "analyst@example.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return login(client)


def universe(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": "demo",
        "tickers": DEMO_TICKERS,
        "start": "2016-01-01",
        "end": "2021-12-31",
    }
    base.update(kw)
    return base
