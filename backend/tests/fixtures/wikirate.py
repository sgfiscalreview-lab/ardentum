"""Rows in the WikiRate REST API format, and a stand-in that answers its queries.

Shapes follow the API documentation (https://wikirate.org/api); the values are made up
for tests.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import respx

from ardentum.data.providers import wikirate as wr

CC_BY = {
    "id": 1,
    "name": "Creative Commons Attribution 4.0 International",
    "abbreviation": "CC BY 4.0",
    "reference_url": "https://creativecommons.org/licenses/by/4.0/",
}
MID = 826615
HEADERS = {"apikey": "pk-test", "x-api-token": "wr_test"}


def metric_row(mid: int = MID, value_type: str | None = "number", **kw: Any) -> dict[str, Any]:
    d = {
        "id": mid,
        "metric_name": "Direct greenhouse gas (GHG) emissions (Scope 1)",
        "metric_designer": "Global Reporting Initiative",
        "question": "What are the company's direct greenhouse gas emissions?",
        "metric_type": "researched",
        "value_type": value_type,
        "value_options": None,
        "unit": "tonnes CO2 equivalent",
        "range": None,
        "assessment_type": "self_reported",
    }
    d.update(kw)
    return d


def company_row(cid: int, name: str, isins: list[str], hq: str = "United States") -> dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "headquarters": {"id": 2, "name": hq, "type": "region", "country_code": "XX"},
        "type": "company",
        "company_identifiers": {"lei": "LEI" + str(cid), "isin": isins},
        "website": "https://example.com",
    }


def answer_row(
    company_id: int,
    company: str,
    year: int,
    value: str,
    mid: int = MID,
    license: Any = CC_BY,
    **kw: Any,
) -> dict[str, Any]:
    slug = company.replace(" ", "-").lower()
    d = {
        "id": company_id * 10_000 + year + mid % 1000 * 100_000_000,
        "company_id": company_id,
        "company": company,
        "metric_id": mid,
        "value": value,
        "year": year,
        "sources": [
            {
                "id": 9,
                "name": f"{company} report {year}",
                "original_url": f"https://example.com/{slug}-{year}.pdf",
                "file_url": "https://data.wikirate.org/storage/v1/object/public/sources/9.pdf",
            }
        ],
        "license_id": 1,
        "license": license,
    }
    d.update(kw)
    return d


def payload(*rows: dict[str, Any]) -> bytes:
    return json.dumps(list(rows)).encode()


def _matches(row: Mapping[str, Any], column: str, test: str) -> bool:
    op, _, arg = test.partition(".")
    if "->>" in column:
        outer, inner = column.split("->>")
        value: Any = row.get(outer, {}).get(inner)
        value = value if isinstance(value, str) else json.dumps(value)
    else:
        value = row.get(column)
    if op == "eq":
        return str(value) == arg
    if op == "in":
        return str(value) in arg.strip("()").split(",")
    if op in ("like", "ilike"):
        pattern = ".*".join(re.escape(part) for part in arg.split("*"))
        return bool(re.fullmatch(pattern, str(value), re.IGNORECASE if op == "ilike" else 0))
    raise ValueError(f"unsupported operator {op!r}")


class FakeWikiRate:
    """The parts of the API that Ardentum uses, over rows held in memory."""

    def __init__(
        self,
        metrics: Sequence[dict[str, Any]] = (),
        companies: Sequence[dict[str, Any]] = (),
        answers: Sequence[dict[str, Any]] = (),
    ) -> None:
        self.tables = {
            "/v1_metrics": list(metrics),
            "/v1_companies": list(companies),
            "/v1_answers": list(answers),
        }
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.refuse_or = False  # answer HTTP 400 to combined ("or") filters

    def respond(
        self, path: str, params: Mapping[str, str], headers: Mapping[str, str]
    ) -> tuple[int, bytes]:
        self.requests.append((path, dict(params)))
        if any(headers.get(k) != v for k, v in HEADERS.items()):
            return 401, b'{"message": "Invalid API token"}'
        if headers.get("accept-profile") != "api" or path not in self.tables:
            return 404, b'{"message": "Not found"}'
        rows = self.tables[path]
        for column, test in params.items():
            if column in ("select", "order", "limit", "offset"):
                continue
            if column == "or":
                if self.refuse_or:
                    return 400, b'{"message": "failed to parse logic tree"}'
                tests = [t.split(".", 1) for t in test.strip("()").split(",")]
                rows = [r for r in rows if any(_matches(r, c, t) for c, t in tests)]
            else:
                rows = [r for r in rows if _matches(r, column, test)]
        order = params.get("order")
        if order:
            rows = sorted(rows, key=lambda r: r[order])
        offset = int(params.get("offset", 0))
        if offset and offset >= len(rows):
            return 416, b'{"message": "Requested range not satisfiable"}'
        rows = rows[offset : offset + int(params.get("limit", 1000))]
        columns = params.get("select")
        if columns:
            rows = [{c: r.get(c) for c in columns.split(",")} for r in rows]
        return 200, json.dumps(rows).encode()

    def install(self) -> respx.Route:
        """Answer the provider's requests inside a ``respx.mock`` test."""

        def handle(request: httpx.Request) -> httpx.Response:
            path = request.url.path.removeprefix(httpx.URL(wr.BASE_URL).path)
            status, body = self.respond(path, dict(request.url.params), request.headers)
            return httpx.Response(status, content=body)

        return respx.route(url__startswith=wr.BASE_URL).mock(side_effect=handle)

    def params(self, path: str) -> dict[str, str]:
        """The query of the latest request to one endpoint."""
        return next(q for p, q in reversed(self.requests) if p == path)
