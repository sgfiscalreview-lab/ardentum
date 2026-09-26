"""Shared (database) rate limiting and client identification."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ardentum.api.main import create_app
from ardentum.api.ratelimit import DatabaseRateLimiter, client_ip
from ardentum.config import Settings
from ardentum.db.models import Base
from tests.api.conftest import login, universe


@pytest.fixture
def limiter() -> Iterator[DatabaseRateLimiter]:
    url = os.environ.get("ARDENTUM_TEST_DATABASE_URL", "sqlite://")
    kw = (
        {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        if url.startswith("sqlite")
        else {}
    )
    engine = create_engine(url, **kw)  # type: ignore[arg-type]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield DatabaseRateLimiter(sessionmaker(bind=engine), limit=10, window=60, purge_every=1)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_sliding_window_counter(limiter: DatabaseRateLimiter) -> None:
    t0 = 60_000.0  # start of a window
    for i in range(10):
        assert limiter.check("a", t0 + i) is None
    wait = limiter.check("a", t0 + 10)
    assert wait == pytest.approx(50.0)  # the whole remaining window (prev = 0)
    assert limiter.check("b", t0 + 10) is None  # keys are independent
    # Half-way through the next window the previous 11 hits weigh 5.5, leaving room for 4.
    t1 = t0 + 90
    assert all(limiter.check("a", t1) is None for _ in range(4))
    wait = limiter.check("a", t1)
    assert wait is not None
    assert 0 < wait < 30


def test_fails_open_when_database_is_down() -> None:
    engine = create_engine("sqlite://")  # no tables: every statement fails
    lim = DatabaseRateLimiter(sessionmaker(bind=engine), limit=1)
    assert lim.check("a") is None
    assert lim.check("a") is None


def test_client_ip() -> None:
    assert client_ip("6.6.6.6", "10.0.0.1", 0) == "10.0.0.1"  # header ignored
    assert client_ip("6.6.6.6, 203.0.113.9", "10.0.0.1", 1) == "203.0.113.9"
    assert client_ip("203.0.113.9, 35.1.1.1", "10.0.0.1", 2) == "203.0.113.9"
    assert client_ip(None, "10.0.0.1", 1) == "10.0.0.1"


@pytest.fixture
def limited(settings: Settings) -> Iterator[TestClient]:
    s = settings.model_copy(update={"compute_rate_limit": 2, "rate_limit_store": "database"})
    app = create_app(s)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def test_api_limits_per_verified_user(limited: TestClient) -> None:
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    alice, bob = login(limited, "alice@example.com"), login(limited, "bob@example.com")
    assert limited.post("/api/v1/analytics", json=body, headers=alice).status_code == 200
    assert limited.post("/api/v1/analytics", json=body, headers=alice).status_code == 200
    r = limited.post("/api/v1/analytics", json=body, headers=alice)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert r.json()["error"]["type"] == "rate_limited"
    # Another user is unaffected, and a fresh token for Alice does not reset her limit.
    assert limited.post("/api/v1/analytics", json=body, headers=bob).status_code == 200
    again = login(limited, "alice@example.com")
    assert limited.post("/api/v1/analytics", json=body, headers=again).status_code == 429


def test_forged_forwarded_for_does_not_bypass(limited: TestClient) -> None:
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    codes = [
        limited.post(
            "/api/v1/analytics", json=body, headers={"X-Forwarded-For": f"198.51.100.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]
    # Non-compute endpoints are not limited.
    assert limited.get("/api/v1/datasets").status_code == 200
