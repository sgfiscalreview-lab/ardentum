"""Open ESG data (WikiRate) through the API: match, score, save and use in analyses."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import httpx
import pandas as pd
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ardentum.data.providers import wikirate as wr
from ardentum.db.models import ProviderCache
from ardentum.services import market_data, open_esg, provider_cache
from ardentum.services.provider_cache import clear_memory
from tests.api.conftest import login
from tests.api.test_api_auth_portfolios import PRICES
from tests.fixtures.wikirate import (
    answer_item,
    answers_payload,
    companies_payload,
    company_card,
    company_item,
    metric_card,
    metrics_payload,
)

MID = 826615
META = "ticker,name,isin\nAAA,Apple,US0378331005\nBBB,Adidas,DE000A1EWWW0\nCCC,Puma,\n"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _mock_wikirate(value_type: str = "Number") -> dict[str, respx.Route]:
    return {
        "metric": respx.get(f"{wr.BASE_URL}/~{MID}.json").mock(
            return_value=httpx.Response(200, content=metric_card(MID, value_type))
        ),
        "companies": respx.get(f"{wr.BASE_URL}/Companies.json").mock(
            return_value=httpx.Response(
                200,
                content=companies_payload(
                    company_item(100, "Apple Inc.", ["US0378331005", "US0378331088"]),
                    company_item(200, "Adidas AG", ["DE000A1EWWW0"], "Germany"),
                ),
            )
        ),
        "puma": respx.get(f"{wr.BASE_URL}/~300.json").mock(
            return_value=httpx.Response(200, content=company_card(300, "Puma"))
        ),
        "answers": respx.get(f"{wr.BASE_URL}/~{MID}+Answers.json").mock(
            return_value=httpx.Response(
                200,
                content=answers_payload(
                    answer_item("Apple Inc.", 2022, "1000"),
                    answer_item("Apple Inc.", 2023, "800"),
                    answer_item("Adidas AG", 2023, "Unknown"),
                    answer_item("Puma", 2023, "400"),
                ),
            )
        ),
    }


def _upload(client: TestClient, auth: dict[str, str]) -> str:
    r = client.post(
        "/api/v1/datasets",
        data={"name": "Brands"},
        files={"prices": ("p.csv", PRICES, "text/csv"), "metadata": ("m.csv", META, "text/csv")},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _preview(ds: str, **kw: object) -> dict[str, object]:
    body: dict[str, object] = {
        "dataset_id": ds,
        "tickers": ["AAA", "BBB", "CCC"],
        "metric_id": MID,
        "transform": {"method": "percentile", "higher_is_better": False},
    }
    body.update(kw)
    return body


@respx.mock
def test_search_metrics_and_companies(client: TestClient) -> None:
    respx.get(f"{wr.BASE_URL}/Metrics.json").mock(
        return_value=httpx.Response(200, content=metrics_payload())
    )
    r = client.get("/api/v1/esg/open/metrics?q=emissions")
    assert r.status_code == 200, r.text
    assert r.json()[0]["numeric"] is True
    assert r.json()[0]["unit"] == "tonnes CO2 equivalent"
    _mock_wikirate()
    r = client.get("/api/v1/esg/open/companies?q=apple")
    assert r.json()[0]["isins"][0] == "US0378331005"
    # Free-text searches are kept in memory only: a row per distinct query would grow forever.
    engine = client.app.state.engine  # type: ignore[attr-defined]
    with engine.connect() as conn:
        assert conn.execute(ProviderCache.__table__.select()).all() == []


def test_old_rows_of_growing_providers_are_purged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider_cache, "PURGE_EVERY", 1)
    engine = client.app.state.engine  # type: ignore[attr-defined]
    old = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)
    with engine.begin() as conn:
        for provider in ("wikirate", "kenfrench"):
            conn.execute(
                ProviderCache.__table__.insert().values(
                    provider=provider, key="old", fetched_at=old, payload=b""
                )
            )
    with Session(engine) as session:
        provider_cache.ProviderCache(session).get_or_fetch(
            "wikirate", "new", dt.timedelta(days=1), lambda: b"{}"
        )
    with engine.connect() as conn:
        rows = {(r.provider, r.key) for r in conn.execute(ProviderCache.__table__.select())}
    # Ken French keeps its old copy (the fallback when the source is down).
    assert rows == {("wikirate", "new"), ("kenfrench", "old")}


@respx.mock
def test_preview_matches_by_isin_only_and_never_imputes(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth)
    routes = _mock_wikirate()
    # With one numeric value, percentile ranks are undefined: no scores and a warning (the
    # table is still returned so the user can match more companies), never a guess.
    r = client.post("/api/v1/esg/open/preview", json=_preview(ds), headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["scored"] == 0
    assert "percentile ranks are undefined" in r.json()["warnings"][0]
    assert all(e["score"] is None for e in r.json()["entries"])
    linear = {"method": "linear", "lower": 0, "upper": 1000, "higher_is_better": False}
    r = client.post("/api/v1/esg/open/preview", json=_preview(ds, transform=linear), headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    rows = {e["ticker"]: e for e in out["entries"]}
    assert rows["AAA"]["matched_by"] == "isin"
    assert rows["AAA"]["year"] == 2023  # latest answer
    assert rows["AAA"]["raw_value"] == 800
    assert rows["BBB"]["status"] == "not_numeric"
    assert rows["BBB"]["score"] is None
    assert rows["CCC"]["status"] == "no_company"  # no ISIN: no automatic name matching
    assert "choose the company manually" in rows["CCC"]["note"]
    assert rows["AAA"]["score"] == pytest.approx(20.0)  # 800 on a 0-1000 scale, lower better
    assert out["scored"] == 1
    assert "CC BY 4.0" in out["attribution"]
    q = routes["companies"].calls.last.request.url.params["filter[company_identifier[value]]"]
    assert "US0378331005" in q
    assert "DE000A1EWWW0" in q


@respx.mock
def test_user_confirmed_company_and_scores(client: TestClient, auth: dict[str, str]) -> None:
    ds = _upload(client, auth)
    _mock_wikirate()
    body = _preview(ds, company_overrides={"CCC": 300})
    out = client.post("/api/v1/esg/open/preview", json=body, headers=auth).json()
    rows = {e["ticker"]: e for e in out["entries"]}
    assert rows["CCC"]["matched_by"] == "user"
    assert rows["CCC"]["company"] == "Puma"
    # Lower emissions are better: Puma (400) ranks first, Apple (800) last.
    assert rows["CCC"]["score"] == 100
    assert rows["AAA"]["score"] == 0
    assert out["scored"] == 2

    # A scale that ends below Apple's 800 scores it at the end point, and says so.
    body = _preview(
        ds,
        company_overrides={"CCC": 300},
        transform={"method": "linear", "lower": 0, "upper": 500, "higher_is_better": False},
    )
    out = client.post("/api/v1/esg/open/preview", json=body, headers=auth).json()
    rows = {e["ticker"]: e for e in out["entries"]}
    assert rows["AAA"]["score"] == 0
    assert "outside the scale" in rows["AAA"]["note"]
    assert rows["CCC"]["score"] == pytest.approx(20.0)  # Puma's 400 is inside
    assert "outside the scale" not in rows["CCC"]["note"]
    assert "1 of 2 values fall outside the scale (0 to 500)" in out["warnings"][0]

    # As of 2022 only Apple has an answer; a linear scale still works.
    body = _preview(
        ds,
        company_overrides={"CCC": 300},
        year=2022,
        transform={"method": "linear", "lower": 0, "upper": 2000, "higher_is_better": False},
    )
    out = client.post("/api/v1/esg/open/preview", json=body, headers=auth).json()
    rows = {e["ticker"]: e for e in out["entries"]}
    assert rows["AAA"]["raw_value"] == 1000
    assert rows["AAA"]["score"] == 50
    assert rows["CCC"]["status"] == "no_answer"
    body["transform"] = {"method": "percentile"}
    r = client.post("/api/v1/esg/open/preview", json=body, headers=auth)
    assert r.json()["scored"] == 0
    assert "linear scale" in r.json()["warnings"][0]
    save = client.post("/api/v1/esg/overlays", json={"name": "x", "preview": body}, headers=auth)
    assert save.status_code == 422
    assert "nothing to save" in save.json()["error"]["message"]


@respx.mock
def test_refusals(client: TestClient, auth: dict[str, str]) -> None:
    _mock_wikirate()
    r = client.post("/api/v1/esg/open/preview", json=_preview("demo", tickers=["NWS.SYN"]))
    assert r.status_code == 422
    assert "fictional" in r.json()["error"]["message"]
    r = client.post("/api/v1/esg/open/preview", json=_preview("kf12", tickers=["NODUR"]))
    assert "not companies" in r.json()["error"]["message"]
    ds = _upload(client, auth)
    respx.get(f"{wr.BASE_URL}/~{MID}.json").mock(
        return_value=httpx.Response(200, content=metric_card(MID, "Category"))
    )
    r = client.post("/api/v1/esg/open/preview", json=_preview(ds), headers=auth)
    assert r.status_code == 422
    assert "only numeric metrics" in r.json()["error"]["message"]


@respx.mock
def test_save_overlay_and_use_it_in_optimisation(client: TestClient, auth: dict[str, str]) -> None:
    ds = _upload(client, auth)
    _mock_wikirate()
    body = {
        "name": "Scope 1 (lower better)",
        "preview": _preview(ds, company_overrides={"CCC": 300}),
    }
    assert client.post("/api/v1/esg/overlays", json=body).status_code == 401
    r = client.post("/api/v1/esg/overlays", json=body, headers=auth)
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    listed = client.get("/api/v1/esg/overlays", headers=auth).json()
    assert listed[0]["scored"] == 2
    assert listed[0]["total"] == 3

    universe = {"dataset_id": ds, "tickers": ["AAA", "BBB", "CCC"], "esg_overlay_id": oid}
    a = client.post("/api/v1/analytics", json={"universe": universe}, headers=auth).json()
    scores = {x["ticker"]: x["esg_score"] for x in a["assets"]}
    assert scores == {"AAA": 0, "BBB": None, "CCC": 100}
    assert any("WikiRate" in n for n in a["data"]["provenance"]["notes"])

    opt = {
        "universe": universe,
        "objective": {"objective": "min_volatility"},
        "constraints": {"min_esg_score": 50, "exclude_unscored_assets": True},
    }
    r = client.post("/api/v1/optimise", json=opt, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["excluded_unscored"] == ["BBB"]
    assert r.json()["result"]["esg_score"] >= 50 - 1e-6

    # Private to the owner, and tied to its dataset.
    other = login(client, "other@example.com")
    assert (
        client.post("/api/v1/analytics", json={"universe": universe}, headers=other).status_code
        == 404
    )
    wrong = {**universe, "dataset_id": "demo", "tickers": ["NWS.SYN", "GOVB.SYN"]}
    r = client.post("/api/v1/analytics", json={"universe": wrong}, headers=auth)
    assert r.status_code == 422
    assert "another dataset" in r.json()["error"]["message"]
    assert client.delete(f"/api/v1/esg/overlays/{oid}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/esg/overlays/{oid}", headers=auth).status_code == 404


@respx.mock
def test_saved_overlays_per_user_are_capped(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(open_esg, "MAX_OVERLAYS_PER_USER", 1)
    ds = _upload(client, auth)
    _mock_wikirate()
    body = {"name": "Scope 1", "preview": _preview(ds, company_overrides={"CCC": 300})}
    assert client.post("/api/v1/esg/overlays", json=body, headers=auth).status_code == 201
    r = client.post("/api/v1/esg/overlays", json=body, headers=auth)
    assert r.status_code == 422
    assert "at most 1 ESG overlays" in r.json()["error"]["message"]


@respx.mock
def test_backtests_use_only_the_esg_scores_known_at_each_rebalance(
    client: TestClient, auth: dict[str, str]
) -> None:
    days = pd.bdate_range("2023-01-02", periods=450)
    prices = "date,AAA,CCC\n" + "\n".join(
        f"{d.date()},{100 + i * 0.1 + (i % 7) * 0.3:.4f},{20 + (i % 5) * 0.1 + i * 0.02:.4f}"
        for i, d in enumerate(days)
    )
    meta = "ticker,name,isin\nAAA,Apple,US0378331005\nCCC,Puma,\n"
    up = client.post(
        "/api/v1/datasets",
        data={"name": "Two brands"},
        files={"prices": ("p.csv", prices, "text/csv"), "metadata": ("m.csv", meta, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 201, up.text
    ds = up.json()["id"]
    _mock_wikirate()
    linear = {"method": "linear", "lower": 0, "upper": 2000, "higher_is_better": False}
    preview = _preview(ds, tickers=["AAA", "CCC"], company_overrides={"CCC": 300}, transform=linear)

    # Every year's answer is scored: Apple 1000 (2022) and 800 (2023), Puma 400 (2023).
    out = client.post("/api/v1/esg/open/preview", json=preview, headers=auth).json()
    history = {e["ticker"]: e["history"] for e in out["entries"]}
    assert history == {
        "AAA": [{"year": 2022, "score": 50.0}, {"year": 2023, "score": 60.0}],
        "CCC": [{"year": 2023, "score": 80.0}],
    }
    saved = client.post(
        "/api/v1/esg/overlays", json={"name": "Scope 1", "preview": preview}, headers=auth
    )
    assert saved.status_code == 201, saved.text

    def backtest(start: str) -> list[str]:
        body = {
            "universe": {
                "dataset_id": ds,
                "tickers": ["AAA", "CCC"],
                "esg_overlay_id": saved.json()["id"],
                "start": start,
            },
            "strategy": {
                "type": "optimised",
                "objective": {"objective": "min_volatility"},
                "constraints": {"min_esg_score": 55},
            },
            "lookback_years": 0.25,
            "benchmark": None,
        }
        r = client.post("/api/v1/backtest", json=body, headers=auth)
        assert r.status_code == 200, r.text
        return r.json()["assumptions"]  # type: ignore[no-any-return]

    # Puma's 2023 answer counts from 30 June 2024: a backtest deciding earlier uses
    # today's scores and says so; one deciding later uses only what was known.
    early = " ".join(backtest("2023-02-01"))
    assert "today's at every rebalance: AAA, CCC had no score yet" in early
    assert "all are known from 30 Jun 2024" in early
    late = " ".join(backtest("2024-04-15"))
    assert "ESG scores are point in time" in late
    assert "30 June of the next year" in late
