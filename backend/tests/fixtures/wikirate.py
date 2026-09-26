"""Payloads in the WikiRate API formats (list views and nested single-card views).

Shapes follow responses recorded by the wikirate4py client; the values are made up
for tests.
"""

from __future__ import annotations

import json
from typing import Any

LICENSE = "Wikirate.org, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0)."
BASE = "https://wikirate.org"


def _collection(items: list[dict[str, Any]], nxt: str | None = None) -> bytes:
    return json.dumps(
        {
            "id": 1,
            "name": "x",
            "type": "Cardtype",
            "items": items,
            "paging": {"next": nxt} if nxt else {},
            "license": LICENSE,
        }
    ).encode()


def metric_item(mid: int = 826615, value_type: str = "Number", **kw: Any) -> dict[str, Any]:
    d = {
        "id": mid,
        "name": "Global Reporting Initiative+Direct greenhouse gas (GHG) emissions (Scope 1)",
        "type": "Metric",
        "url": f"{BASE}/Global_Reporting_Initiative+Direct_GHG_Scope_1.json",
        "designer": "Global Reporting Initiative",
        "title": "Direct greenhouse gas (GHG) emissions (Scope 1)",
        "metric_type": "Researched",
        "value_type": value_type,
        "unit": " tonnes CO2 equivalent",
        "range": None,
        "answer": 5271,
        "topics": ["Wikirate ESG Topics+Environment", "Wikirate ESG Topics+Climate Change"],
    }
    d.update(kw)
    return d


def metrics_payload(*items: dict[str, Any]) -> bytes:
    return _collection(list(items) or [metric_item()])


def metric_card(
    mid: int = 826615, value_type: str | None = "Number", rng: str | None = None
) -> bytes:
    """Single-card view: fields are nested cards with the value under 'content'."""

    def nested(name: str, content: Any, typ: str = "Pointer") -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": 1,
            "name": f"GRI+Scope 1+{name}",
            "type": typ,
            "url": f"{BASE}/x.json",
        }
        if content is not None:
            d["content"] = content
        return d

    return json.dumps(
        {
            "id": mid,
            "name": "Global Reporting Initiative+Direct greenhouse gas (GHG) emissions (Scope 1)",
            "type": {
                "id": 43576,
                "name": "Metric",
                "type": "Cardtype",
                "url": f"{BASE}/Metric.json",
            },
            "url": f"{BASE}/~{mid}.json",
            "designer": "Global Reporting Initiative",
            "title": "Direct greenhouse gas (GHG) emissions (Scope 1)",
            "metric_type": nested("*metric type", "Researched"),
            "value_type": nested("value type", [value_type] if value_type else None),
            "unit": nested("unit", "tonnes CO2 equivalent", "Phrase"),
            "range": nested("Range", rng, "Phrase"),
            "topics": nested("Topic", None, "List"),
            "answer": 5271,
            "license": LICENSE,
        }
    ).encode()


def company_item(
    cid: int, name: str, isins: list[str], hq: str = "United States"
) -> dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "type": "Company",
        "url": f"{BASE}/{name.replace(' ', '_')}.json",
        "headquarters": hq,
        "alias": [name],
        "international_securities_identification_number": isins,
    }


def companies_payload(*items: dict[str, Any]) -> bytes:
    return _collection(list(items))


def company_card(cid: int, name: str) -> bytes:
    return json.dumps(
        {
            "id": cid,
            "name": name,
            "type": {"id": 651, "name": "Company", "type": "Cardtype"},
            "headquarters": {
                "id": 2,
                "name": f"{name}+Headquarters",
                "type": "Pointer",
                "content": ["Germany"],
            },
            "international_securities_identification_number": {
                "id": 3,
                "name": f"{name}+ISIN",
                "type": "RichText",
                "content": ["DE0006969603"],
            },
        }
    ).encode()


def answer_item(company: str, year: int, value: str, mid: int = 826615) -> dict[str, Any]:
    slug = company.replace(" ", "_")
    return {
        "id": hash((company, year)) % 10**7,
        "name": f"GRI+Scope 1+{company}+{year}",
        "type": "Answer",
        "url": f"{BASE}/GRI+Scope_1+{slug}+{year}.json",
        "metric": "Global Reporting Initiative+Direct greenhouse gas (GHG) emissions (Scope 1)",
        "company": company,
        "year": year,
        "value": value,
        "sources": ["Source-000217552"],
        "answer_url": f"{BASE}/GRI+Scope_1+{slug}.json",
    }


def answers_payload(*items: dict[str, Any], nxt: str | None = None) -> bytes:
    return _collection(list(items), nxt)
