"""Open ESG data (WikiRate) through the API: match, score, save and use in analyses."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.data.providers import wikirate as wr
from ardentum.services import market_data, open_esg
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
