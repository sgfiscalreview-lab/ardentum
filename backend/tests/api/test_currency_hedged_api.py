"""Currency-hedged universes through the API (ECB and BIS hosts mocked)."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.data.providers import bis, fx
from ardentum.services import market_data
from ardentum.services.provider_cache import clear_memory
from tests.api.test_currency_riskfree_api import AAA, DAYS, RATES, _upload

US_RATE, EU_RATE = 0.05, 0.02


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _bis_csv(area: str, rate: float) -> bytes:
    rows = [f"D,{area},{d.isoformat()},{rate * 100}" for d in DAYS if d.weekday() < 5]
    rows.insert(0, f"D,{area},{DAYS[0].replace(day=1).isoformat()},{rate * 100}")
    rows.append(f"D,{area},{DAYS[-1].isoformat()},NaN")  # missing values are skipped
    return ("FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n" + "\n".join(rows)).encode()


def _mock_hosts() -> dict[str, respx.Route]:
    respx.get(f"{fx.BASE_URL}/v1/1999-01-04..", params={"base": "EUR"}).mock(
        return_value=httpx.Response(200, json={"amount": 1.0, "base": "EUR", "rates": RATES})
    )
    return {
        "US": respx.get(f"{bis.BASE_URL}/D.US/all").mock(
            return_value=httpx.Response(200, content=_bis_csv("US", US_RATE))
        ),
        "XM": respx.get(f"{bis.BASE_URL}/D.XM/all").mock(
            return_value=httpx.Response(200, content=_bis_csv("XM", EU_RATE))
        ),
    }


def _fx_on(day_index: int) -> float:
    """ECB rate carried forward over weekends, as in the conversion."""
    for i in range(day_index, -1, -1):
        key = DAYS[i].isoformat()
        if key in RATES:
            return float(RATES[key]["USD"])
    return 1.04  # the Friday before the first Monday


@respx.mock
def test_hedged_returns_follow_covered_interest_parity(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth).json()["id"]
    routes = _mock_hosts()
    universe = {
        "dataset_id": ds,
        "tickers": ["AAA", "BBB"],
        "base_currency": "USD",
        "currency_hedged": True,
    }
    r = client.post("/api/v1/analytics", json={"universe": universe}, headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert routes["US"].called
    assert routes["XM"].called
    params = routes["XM"].calls.last.request.url.params
    assert params["detail"] == "dataonly"
    notes = " ".join(out["data"]["provenance"]["notes"])
    assert "currency-hedged" in notes
    assert "Bank for International Settlements" in notes

    # Independent recomputation, one calendar day per period.
    carry = (1 + US_RATE / 365) / (1 + EU_RATE / 365) - 1
    wealth = 1.0
    for i in range(1, len(DAYS)):
        r_l = AAA[i] / AAA[i - 1] - 1
        r_x = _fx_on(i) / _fx_on(i - 1) - 1
        wealth *= 1 + r_l * (1 + r_x) + carry
    aaa = next(a for a in out["assets"] if a["ticker"] == "AAA")
    assert aaa["performance"]["total_return"] == pytest.approx(wealth - 1, rel=1e-9)

    unhedged = {**universe, "currency_hedged": False}
    u = client.post("/api/v1/analytics", json={"universe": unhedged}, headers=auth).json()
    u_aaa = next(a for a in u["assets"] if a["ticker"] == "AAA")
    assert u_aaa["performance"]["total_return"] != pytest.approx(wealth - 1, rel=1e-6)
    # BBB is already in USD: identical either way.
    bbb = [
        next(a for a in x["assets"] if a["ticker"] == "BBB")["performance"]["total_return"]
        for x in (out, u)
    ]
    assert bbb[0] == pytest.approx(bbb[1], rel=1e-12)


@respx.mock
def test_hedging_needs_a_base_currency_and_a_policy_rate(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth).json()["id"]
    _mock_hosts()
    body = {"universe": {"dataset_id": ds, "tickers": ["BBB"], "currency_hedged": True}}
    r = client.post("/api/v1/analytics", json=body, headers=auth)
    assert r.status_code == 422
    assert "needs a base currency" in r.json()["error"]["message"]
    meta = "ticker,name,currency\nAAA,Alpha,SGD\nBBB,Beta,USD\n"
    ds2 = _upload(client, auth, meta).json()["id"]
    body = {
        "universe": {
            "dataset_id": ds2,
            "tickers": ["AAA", "BBB"],
            "base_currency": "USD",
            "currency_hedged": True,
        }
    }
    respx.get(f"{fx.BASE_URL}/v1/1999-01-04..", params={"base": "SGD"}).mock(
        return_value=httpx.Response(200, json={"rates": RATES})
    )
    r = client.post("/api/v1/analytics", json=body, headers=auth)
    assert r.status_code == 422
    assert "No central-bank policy rate is available for SGD" in r.json()["error"]["message"]
