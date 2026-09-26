"""Kenneth French datasets through the API, with downloads mocked (hosts are external)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.data.providers import kenfrench as kf
from ardentum.db.models import ProviderCache
from ardentum.services import market_data
from ardentum.services.provider_cache import clear_memory
from tests.fixtures.kenfrench import (
    factors_daily_text,
    industries_daily_text,
    industries_monthly_text,
    zipped,
)

TICKERS = ["NODUR", "BUSEQ", "HLTH", "MONEY", "UTILS"]


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _mock_downloads() -> respx.Route:
    respx.get(f"{kf.BASE_URL}{kf.FACTORS_DAILY}_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("f", factors_daily_text(n_days=400)))
    )
    respx.get(f"{kf.BASE_URL}12_Industry_Portfolios_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("m", industries_monthly_text()))
    )
    return respx.get(f"{kf.BASE_URL}12_Industry_Portfolios_daily_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("d", industries_daily_text(n_days=400)))
    )


def test_listed_without_network(client: TestClient) -> None:
    ids = [d["id"] for d in client.get("/api/v1/datasets").json()]
    assert "kf12" in ids
    assert "kf49" in ids
    d = client.get("/api/v1/datasets/kf12").json()
    assert d["is_synthetic"] is False
    assert len(d["assets"]) == 13
    assert any(a["ticker"] == "MKT" and a["is_benchmark"] for a in d["assets"])


@respx.mock
def test_optimise_on_kenfrench_and_cache_persists(client: TestClient) -> None:
    daily = _mock_downloads()
    body = {
        "universe": {"dataset_id": "kf12", "tickers": TICKERS},
        "objective": {"objective": "min_volatility"},
    }
    r = client.post("/api/v1/optimise", json=body)
    assert r.status_code == 200, r.text
    prov = r.json()["data"]["provenance"]
    assert prov["source"].startswith("Kenneth R. French")
    assert prov["is_synthetic"] is False
    assert daily.call_count == 1

    # A second instance (empty memory) is served from PostgreSQL, not the network.
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    assert client.post("/api/v1/optimise", json=body).status_code == 200
    assert daily.call_count == 1


@respx.mock
def test_stale_copy_served_when_source_down(client: TestClient) -> None:
    _mock_downloads()
    body = {"universe": {"dataset_id": "kf12", "tickers": TICKERS}}
    assert client.post("/api/v1/analytics", json=body).status_code == 200
    # Age the cache and make the source fail.
    engine = client.app.state.engine  # type: ignore[attr-defined]
    with engine.begin() as conn:
        conn.execute(
            ProviderCache.__table__.update().values(
                fetched_at=dt.datetime(2000, 1, 1, tzinfo=dt.UTC)
            )
        )
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    respx.get(f"{kf.BASE_URL}12_Industry_Portfolios_daily_CSV.zip").mock(
        return_value=httpx.Response(503)
    )
    respx.get(f"{kf.BASE_URL}{kf.FACTORS_DAILY}_CSV.zip").mock(return_value=httpx.Response(503))
    r = client.post("/api/v1/analytics", json=body)
    assert r.status_code == 200, r.text
    assert any("last cached copy" in n for n in r.json()["data"]["provenance"]["notes"])


@respx.mock
def test_source_down_without_cache_is_clear_error(client: TestClient) -> None:
    respx.get(url__startswith=kf.BASE_URL).mock(side_effect=httpx.ConnectError("boom"))
    r = client.post(
        "/api/v1/analytics", json={"universe": {"dataset_id": "kf12", "tickers": TICKERS}}
    )
    assert r.status_code == 502
    assert "unreachable" in r.json()["error"]["message"]
