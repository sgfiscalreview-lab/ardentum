"""Multi-currency universes and public risk-free sources through the API (hosts mocked)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.data.providers import fx
from ardentum.data.providers import kenfrench as kf
from ardentum.services import market_data
from ardentum.services.provider_cache import clear_memory
from tests.fixtures.kenfrench import factors_daily_text, zipped

START = dt.date(2023, 1, 2)
N = 120
DAYS = [START + dt.timedelta(days=i) for i in range(N)]
AAA = [100 + i * 0.1 + (i % 7) * 0.3 for i in range(N)]
PRICES = "date,AAA,BBB\n" + "\n".join(
    f"{d.isoformat()},{a:.4f},{50 + (i % 11) * 0.2 + i * 0.05:.4f}"
    for i, (d, a) in enumerate(zip(DAYS, AAA, strict=True))
)
META = "ticker,name,currency,isin\nAAA,Alpha,EUR,US0378331005\nBBB,Beta,USD,\n"
# ECB rates exist on business days only; weekends are carried forward.
RATES = {d.isoformat(): {"USD": 1.05 + 0.001 * i} for i, d in enumerate(DAYS) if d.weekday() < 5}
RATES[(START - dt.timedelta(days=3)).isoformat()] = {"USD": 1.04}  # covers the first Monday


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _upload(client: TestClient, auth: dict[str, str], meta: str = META) -> httpx.Response:
    return client.post(
        "/api/v1/datasets",
        data={"name": "Two currencies"},
        files={"prices": ("p.csv", PRICES, "text/csv"), "metadata": ("m.csv", meta, "text/csv")},
        headers=auth,
    )


def test_metadata_currency_and_isin_are_validated(client: TestClient, auth: dict[str, str]) -> None:
    r = _upload(client, auth)
    assert r.status_code == 201, r.text
    a = next(x for x in r.json()["assets"] if x["ticker"] == "AAA")
    assert a["currency"] == "EUR"
    assert a["isin"] == "US0378331005"
    bad = _upload(client, auth, "ticker,isin\nAAA,US0378331006\n")
    assert bad.status_code == 422
    assert "not a valid ISIN" in bad.json()["error"]["message"]
    bad = _upload(client, auth, "ticker,currency\nAAA,euro\n")
    assert bad.status_code == 422
    assert "ISO 4217" in bad.json()["error"]["message"]


@respx.mock
def test_mixed_currencies_need_a_base_and_convert_unhedged(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth).json()["id"]
    body: dict[str, object] = {"universe": {"dataset_id": ds, "tickers": ["AAA", "BBB"]}}
    r = client.post("/api/v1/analytics", json=body, headers=auth)
    assert r.status_code == 422
    assert "choose a base currency" in r.json()["error"]["message"]

    route = respx.get(f"{fx.BASE_URL}/v1/1999-01-04..", params={"base": "EUR"}).mock(
        return_value=httpx.Response(200, json={"amount": 1.0, "base": "EUR", "rates": RATES})
    )
    body["universe"] = {"dataset_id": ds, "tickers": ["AAA", "BBB"], "base_currency": "USD"}
    r = client.post("/api/v1/analytics", json=body, headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["data"]["currency"] == "USD"
    assert any("unhedged" in n for n in out["data"]["provenance"]["notes"])
    assert route.calls.last.request.url.params["base"] == "EUR"

    # Independent check: total USD return of AAA = local growth x currency growth,
    # with the last Friday rate used on the final Sunday.
    last_rate = next(RATES[d.isoformat()]["USD"] for d in reversed(DAYS) if d.isoformat() in RATES)
    first_rate = RATES[DAYS[0].isoformat()]["USD"]
    expected = AAA[-1] / AAA[0] * last_rate / first_rate - 1
    aaa = next(a for a in out["assets"] if a["ticker"] == "AAA")
    assert aaa["performance"]["total_return"] == pytest.approx(expected, rel=1e-9)

    # Expressing everything in EUR converts BBB instead, with USD->EUR rates.
    route2 = respx.get(f"{fx.BASE_URL}/v1/1999-01-04..", params={"base": "USD"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "rates": {d: {"EUR": 1 / v["USD"]} for d, v in RATES.items()},
            },
        )
    )
    body["universe"] = {"dataset_id": ds, "tickers": ["AAA", "BBB"], "base_currency": "EUR"}
    r = client.post("/api/v1/analytics", json=body, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["currency"] == "EUR"
    assert route2.called


def test_single_currency_universe_reports_its_currency(client: TestClient) -> None:
    body = {"universe": {"dataset_id": "demo", "tickers": ["NWS.SYN", "GOVB.SYN"]}}
    r = client.post("/api/v1/analytics", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["currency"] == "USD"
    body["universe"]["base_currency"] = "XYZ"  # type: ignore[index]
    r = client.post("/api/v1/analytics", json=body)
    assert r.status_code == 422
    assert "no ECB reference rate" in r.json()["error"]["message"]


@respx.mock
def test_kenfrench_risk_free_rate(client: TestClient) -> None:
    respx.get(f"{kf.BASE_URL}{kf.FACTORS_DAILY}_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("f", factors_daily_text(n_days=400)))
    )
    sources = {s["id"]: s for s in client.get("/api/v1/risk-free/sources").json()}
    assert sources["kenfrench_rf"]["available"] is True
    assert sources["fred_dgs3mo"]["available"] is False

    r = client.post("/api/v1/risk-free", json={"source": "kenfrench_rf"})
    assert r.status_code == 200, r.text
    out = r.json()
    # The fixture's RF is 0.008% per day: (1.00008)^252 - 1.
    assert out["rate"] == pytest.approx(1.00008**252 - 1, rel=1e-9)
    assert out["observations"] == 400
    assert "Fama-French" in out["label"]

    r = client.post(
        "/api/v1/risk-free",
        json={"source": "kenfrench_rf", "start": "1990-01-01", "end": "1990-12-31"},
    )
    assert r.status_code == 422
    assert "Choose a longer or earlier window" in r.json()["error"]["message"]


@respx.mock
def test_fred_risk_free_rate(client: TestClient) -> None:
    r = client.post("/api/v1/risk-free", json={"source": "fred_dgs3mo"})
    assert r.status_code == 503
    assert "Kenneth French" in r.json()["error"]["message"]

    app = client.app
    app.state.settings = app.state.settings.model_copy(update={"fred_api_key": "k"})  # type: ignore[attr-defined]
    obs = [
        {"date": (dt.date(2024, 1, 1) + dt.timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(["5.00", ".", "5.00"] * 20)
    ]
    route = respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(200, content=json.dumps({"observations": obs}).encode())
    )
    r = client.post("/api/v1/risk-free", json={"source": "fred_dgs3mo"})
    assert r.status_code == 200, r.text
    assert r.json()["rate"] == pytest.approx((1 + 0.05 * 91 / 365) ** (365 / 91) - 1)
    assert r.json()["observations"] == 40
    assert route.calls.last.request.url.params["series_id"] == "DGS3MO"
    # Served from the cache the second time.
    client.post("/api/v1/risk-free", json={"source": "fred_dgs3mo"})
    assert route.call_count == 1


def test_risk_free_source_is_echoed(client: TestClient) -> None:
    body = {
        "universe": {"dataset_id": "demo", "tickers": ["NWS.SYN", "GOVB.SYN", "SOL.SYN"]},
        "estimation": {"risk_free_rate": 0.03, "risk_free_source": "Fama-French RF 2019-2024"},
    }
    r = client.post("/api/v1/optimise", json=body)
    assert r.status_code == 200, r.text
    est = r.json()["estimation"]
    assert est["risk_free_rate"] == 0.03
    assert est["risk_free_source"] == "Fama-French RF 2019-2024"
    default = client.post("/api/v1/optimise", json={"universe": body["universe"]}).json()
    assert default["estimation"]["risk_free_source"] == "Entered by the user"
