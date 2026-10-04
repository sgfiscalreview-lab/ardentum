"""Crisis replay, factor exposure and trade lists through the API (downloads mocked)."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.api.ratelimit import budget_for
from ardentum.data.providers import kenfrench as kf
from ardentum.services import market_data, usage
from ardentum.services.provider_cache import clear_memory
from tests.api.conftest import DEMO_TICKERS, universe
from tests.api.test_jobs import _wait
from tests.fixtures.kenfrench import factors_daily_text, industries_daily_text, zipped

KF = ["NODUR", "BUSEQ", "HLTH", "MONEY", "UTILS"]
KF_WEIGHTS = {"NODUR": 0.3, "BUSEQ": 0.3, "HLTH": 0.2, "MONEY": 0.1, "UTILS": 0.1}


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _mock_downloads() -> None:
    # Fixture data: 400 business days from 2020-01-02, covering the COVID-19 crash.
    respx.get(f"{kf.BASE_URL}{kf.FACTORS_DAILY}_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("f", factors_daily_text(n_days=400)))
    )
    respx.get(f"{kf.BASE_URL}12_Industry_Portfolios_daily_CSV.zip").mock(
        return_value=httpx.Response(200, content=zipped("d", industries_daily_text(n_days=400)))
    )


def _stress_body(**kw: object) -> dict[str, object]:
    body: dict[str, object] = {
        "universe": {"dataset_id": "kf12", "tickers": KF},
        "portfolio": {"name": "Five industries", "weights": KF_WEIGHTS},
    }
    body.update(kw)
    return body


@respx.mock
def test_crisis_replay_on_real_data(client: TestClient) -> None:
    _mock_downloads()
    r = client.post("/api/v1/stress", json=_stress_body())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["benchmark_ticker"] == "MKT"
    by_key = {e["key"]: e for e in d["episodes"]}
    assert len(by_key) == 7
    covid = by_key["covid_2020"]
    assert covid["available"] is True
    assert covid["dates"][0] == "2020-02-19"
    assert covid["dates"][-1] == "2020-03-23"
    assert covid["portfolio_path"][0] == 1.0
    assert len(covid["portfolio_path"]) == len(covid["dates"]) == len(covid["benchmark_path"])
    assert covid["trading_days"] == len(covid["dates"]) - 1
    contrib = sum(a["contribution"] for a in covid["assets"])
    assert contrib == pytest.approx(covid["total_return"], abs=1e-12)
    assert covid["portfolio_path"][-1] - 1 == pytest.approx(covid["total_return"], abs=1e-12)
    assert covid["max_drawdown"] <= min(0.0, covid["total_return"]) + 1e-12
    gfc = by_key["gfc_2007"]
    assert gfc["available"] is False
    assert "begins after this period started (2007-10-09)" in gfc["reason"]
    assert by_key["inflation_2022"]["available"] is False
    assert "data ends" in by_key["inflation_2022"]["reason"]
    assert d["source"].startswith("Peak and low dates")


@respx.mock
def test_custom_period_and_a_chosen_crisis(client: TestClient) -> None:
    _mock_downloads()
    body = _stress_body(
        episodes=["covid_2020"],
        custom={"name": "Spring 2021", "start": "2021-03-01", "end": "2021-05-28"},
    )
    d = client.post("/api/v1/stress", json=body).json()
    assert [e["key"] for e in d["episodes"]] == ["covid_2020", "custom"]
    custom = d["episodes"][1]
    assert custom["name"] == "Spring 2021"
    assert custom["available"] is True
    assert custom["dates"][0] == "2021-03-01"


def test_named_crises_need_real_data_but_own_dates_work_on_demo(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    body = {
        "universe": universe(),
        "portfolio": {"name": "Equal", "weights": w},
        "custom": {"start": "2018-01-26", "end": "2018-04-02"},
    }
    d = client.post("/api/v1/stress", json=body).json()
    named = [e for e in d["episodes"] if e["key"] != "custom"]
    assert all(not e["available"] and "synthetic" in e["reason"] for e in named)
    custom = d["episodes"][-1]
    assert custom["available"] is True
    assert custom["benchmark_path"] is not None  # the demo's synthetic market index
    # The same request as a background job gives the same answer.
    job = client.post("/api/v1/jobs", json={"kind": "stress", "request": body}).json()
    done = _wait(client, job["id"])
    assert done["status"] == "succeeded"
    # Stored as JSON in the database: PostgreSQL may round the last binary digit.
    assert done["result"]["episodes"][-1]["total_return"] == pytest.approx(
        custom["total_return"], rel=1e-12
    )


def test_crisis_list(client: TestClient) -> None:
    r = client.get("/api/v1/stress/crises")
    assert r.status_code == 200
    items = r.json()
    assert [i["key"] for i in items][:2] == ["crash_1929", "oil_1973"]
    assert items[-2]["start"] == "2020-02-19"
    assert budget_for("GET", "/api/v1/stress/crises") is None


def test_stress_input_errors_are_explained(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    base = {"universe": universe(), "portfolio": {"name": "Equal", "weights": w}}
    r = client.post("/api/v1/stress", json={**base, "episodes": ["moon_landing"]})
    assert r.status_code == 422
    assert "Unknown crisis: moon_landing" in r.json()["error"]["message"]
    r = client.post("/api/v1/stress", json={**base, "episodes": []})
    assert r.status_code == 422
    assert "at least one period" in r.json()["error"]["message"]
    r = client.post(
        "/api/v1/stress", json={**base, "custom": {"start": "2019-05-01", "end": "2019-01-01"}}
    )
    assert r.status_code == 422


@respx.mock
def test_factor_exposure_on_real_data(client: TestClient) -> None:
    _mock_downloads()
    body = {
        "universe": {"dataset_id": "kf12", "tickers": KF},
        "portfolio": {"name": "Five industries", "weights": KF_WEIGHTS},
    }
    r = client.post("/api/v1/factors", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert [f["key"] for f in d["factors"]] == ["MKT_RF", "SMB", "HML"]
    assert d["observations"] == 399
    # Linearity of least squares: the portfolio's loadings are the weighted asset loadings.
    for f in d["factors"]:
        weighted = sum(a["weight"] * a["loadings"][f["key"]] for a in d["assets"])
        assert f["loading"] == pytest.approx(weighted, abs=1e-10)
    split = d["alpha"] + sum(f["contribution"] for f in d["factors"])
    assert split == pytest.approx(d["mean_excess_return"], abs=1e-10)
    assert 0.0 <= d["r_squared"] <= 1.0
    assert "Kenneth R. French" in d["factor_source"]
    # Weekly returns use factors compounded over each week.
    weekly = client.post(
        "/api/v1/factors", json={**body, "universe": {**body["universe"], "frequency": "weekly"}}
    ).json()
    assert 70 <= weekly["observations"] <= 81


def test_factor_exposure_refuses_synthetic_data(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    r = client.post(
        "/api/v1/factors", json={"universe": universe(), "portfolio": {"name": "E", "weights": w}}
    )
    assert r.status_code == 422
    assert "synthetic" in r.json()["error"]["message"]


def test_trade_list(client: TestClient) -> None:
    body = {
        "holdings": {"A": 6000.0, "B": 4000.0, "OLD": 500.0},
        "target": {"name": "Target", "weights": {"A": 0.5, "B": 0.3, "C": 0.2}},
        "new_money": 1000.0,
        "transaction_cost_bps": 0,
    }
    r = client.post("/api/v1/trades", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    rows = {t["ticker"]: t for t in d["trades"]}
    assert [t["ticker"] for t in d["trades"]] == ["A", "B", "C", "OLD"]
    assert d["value_after"] == pytest.approx(11_500.0)
    assert rows["A"]["trade"] == pytest.approx(-250.0)
    assert rows["A"]["action"] == "sell"
    assert rows["C"]["action"] == "buy"
    assert rows["OLD"]["trade"] == pytest.approx(-500.0)
    assert rows["C"]["current_weight"] == 0.0
    with_costs = client.post("/api/v1/trades", json={**body, "transaction_cost_bps": 20}).json()
    assert with_costs["total_costs"] > 0
    assert with_costs["value_after"] + with_costs["total_costs"] == pytest.approx(11_500.0)
    assert np.isclose(with_costs["sold"] + 1000.0, with_costs["bought"] + with_costs["total_costs"])
    bad = client.post(
        "/api/v1/trades", json={**body, "target": {"name": "T", "weights": {"A": 0.5}}}
    )
    assert bad.status_code == 422
    assert "sum to 1" in bad.json()["error"]["message"]


def test_new_endpoints_count_as_calculations() -> None:
    for path in ("/api/v1/stress", "/api/v1/factors", "/api/v1/trades"):
        assert budget_for("POST", path) == "compute"
    assert usage.event_for("POST", "/api/v1/stress") == "stress"
    assert usage.event_for("POST", "/api/v1/factors") == "factors"
    assert usage.event_for("POST", "/api/v1/trades") == "trades"
