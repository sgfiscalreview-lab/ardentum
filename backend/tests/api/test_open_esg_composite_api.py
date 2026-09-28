"""Composite ESG scores from several open WikiRate metrics: combine, never impute, save, use."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.data.providers import wikirate as wr
from ardentum.services import market_data
from ardentum.services.provider_cache import clear_memory
from tests.api.test_open_esg_api import MID, _mock_wikirate, _upload
from tests.fixtures.wikirate import answer_item, answers_payload, metric_card

MID2 = 900001
LINEAR_LOWER = {"method": "linear", "lower": 0, "upper": 1000, "higher_is_better": False}
LINEAR_HIGHER = {"method": "linear", "lower": 0, "upper": 100, "higher_is_better": True}


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _mock_second_metric() -> None:
    card = json.loads(metric_card(MID2))
    card["title"] = "Board gender diversity"
    card["name"] = "Example Designer+Board gender diversity"
    respx.get(f"{wr.BASE_URL}/~{MID2}.json").mock(
        return_value=httpx.Response(200, content=json.dumps(card).encode())
    )
    respx.get(f"{wr.BASE_URL}/~{MID2}+Answers.json").mock(
        return_value=httpx.Response(
            200,
            content=answers_payload(
                answer_item("Apple Inc.", 2023, "50", MID2),
                answer_item("Adidas AG", 2023, "30", MID2),
                answer_item("Puma", 2022, "20", MID2),
            ),
        )
    )


def _body(ds: str, **kw: object) -> dict[str, object]:
    body: dict[str, object] = {
        "dataset_id": ds,
        "tickers": ["AAA", "BBB", "CCC"],
        "company_overrides": {"CCC": 300},
        "components": [
            {"metric_id": MID, "weight": 3, "transform": LINEAR_LOWER},
            {"metric_id": MID2, "weight": 1, "transform": LINEAR_HIGHER},
        ],
    }
    body.update(kw)
    return body


@respx.mock
def test_composite_is_the_weighted_average_and_never_imputes(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth)
    _mock_wikirate()
    _mock_second_metric()
    r = client.post("/api/v1/esg/open/composite-preview", json=_body(ds), headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert [c["weight"] for c in out["components"]] == pytest.approx([0.75, 0.25])
    rows = {e["ticker"]: e for e in out["entries"]}
    # Apple: emissions 800 on 0-1000 (lower better) -> 20; diversity 50 -> 50.
    assert rows["AAA"]["score"] == pytest.approx(0.75 * 20 + 0.25 * 50)
    # Puma (chosen by the user): 400 -> 60; 20 -> 20.
    assert rows["CCC"]["score"] == pytest.approx(0.75 * 60 + 0.25 * 20)
    assert rows["CCC"]["matched_by"] == "user"
    # Adidas has no numeric emissions answer: no composite, never an average of the rest.
    assert rows["BBB"]["score"] is None
    assert rows["BBB"]["status"] == "incomplete"
    assert "1 of 2 metrics" in rows["BBB"]["note"]
    assert "Direct greenhouse gas" in rows["BBB"]["note"]
    parts = {p["metric_id"]: p for p in rows["BBB"]["parts"]}
    assert parts[MID]["status"] == "not_numeric"
    assert parts[MID2]["score"] == pytest.approx(30.0)
    assert rows["AAA"]["year"] == 2023
    assert out["scored"] == 2
    assert "Board gender diversity" in out["attribution"]
    assert "CC BY 4.0" in out["attribution"]


@respx.mock
def test_composite_validation(client: TestClient, auth: dict[str, str]) -> None:
    ds = _upload(client, auth)
    one = _body(ds, components=[{"metric_id": MID, "weight": 1}])
    assert client.post("/api/v1/esg/open/composite-preview", json=one).status_code == 422
    dup = _body(ds, components=[{"metric_id": MID, "weight": 1}, {"metric_id": MID, "weight": 2}])
    r = client.post("/api/v1/esg/open/composite-preview", json=dup)
    assert r.status_code == 422
    assert "only once" in r.json()["error"]["message"]
    zero = _body(ds, components=[{"metric_id": MID, "weight": 0}, {"metric_id": MID2, "weight": 1}])
    assert client.post("/api/v1/esg/open/composite-preview", json=zero).status_code == 422
    both = {"name": "x", "preview": {"dataset_id": ds, "tickers": ["AAA"], "metric_id": MID}}
    both["composite"] = _body(ds)
    r = client.post("/api/v1/esg/overlays", json=both, headers=auth)
    assert r.status_code == 422
    assert "not both" in r.json()["error"]["message"]


@respx.mock
def test_save_composite_and_use_it(client: TestClient, auth: dict[str, str]) -> None:
    ds = _upload(client, auth)
    _mock_wikirate()
    _mock_second_metric()
    r = client.post(
        "/api/v1/esg/overlays", json={"name": "Blend", "composite": _body(ds)}, headers=auth
    )
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["metric"] is None
    assert saved["transform"] is None
    assert [c["metric"]["id"] for c in saved["components"]] == [MID, MID2]
    oid = saved["id"]
    listed = client.get("/api/v1/esg/overlays", headers=auth).json()
    assert listed[0]["metric_title"].startswith("Composite: Direct greenhouse gas")
    assert (listed[0]["scored"], listed[0]["total"]) == (2, 3)
    detail = client.get(f"/api/v1/esg/overlays/{oid}", headers=auth).json()
    assert detail["entries"] == saved["entries"]

    universe = {"dataset_id": ds, "tickers": ["AAA", "BBB", "CCC"], "esg_overlay_id": oid}
    a = client.post("/api/v1/analytics", json={"universe": universe}, headers=auth)
    assert a.status_code == 200, a.text
    assets = {x["ticker"]: x for x in a.json()["assets"]}
    assert assets["AAA"]["esg_score"] == pytest.approx(27.5)
    assert assets["CCC"]["esg_score"] == pytest.approx(50.0)
    assert assets["BBB"]["esg_score"] is None
    notes = a.json()["data"]["provenance"]["notes"]
    assert any("Board gender diversity" in n and "CC BY 4.0" in n for n in notes)
    impact = client.post(
        "/api/v1/esg/impact",
        json={
            "universe": universe,
            "constraints": {"min_esg_score": 30, "exclude_unscored_assets": True},
        },
        headers=auth,
    )
    assert impact.status_code == 200, impact.text
    sources = " ".join(impact.json()["esg_data_notes"])
    assert "composite for Apple Inc." in sources
    assert "(75% weight, 2023 answer, score 20" in sources
    assert "Board gender diversity (25% weight, 2023 answer, score 50" in sources


@respx.mock
def test_composite_with_no_complete_asset_cannot_be_saved(
    client: TestClient, auth: dict[str, str]
) -> None:
    ds = _upload(client, auth)
    _mock_wikirate()
    _mock_second_metric()
    body = _body(ds, company_overrides={}, tickers=["BBB", "CCC"])
    r = client.post("/api/v1/esg/overlays", json={"name": "x", "composite": body}, headers=auth)
    assert r.status_code == 422
    assert "no composite score exists" in r.json()["error"]["message"]
