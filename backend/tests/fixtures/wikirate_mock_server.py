"""A local stand-in for the WikiRate API, serving the test fixtures (for E2E tests).

Run: ``uv run python -m tests.fixtures.wikirate_mock_server 8765`` and point the API at
it with ``ARDENTUM_WIKIRATE_BASE_URL=http://localhost:8765``.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from tests.fixtures.wikirate import (
    answer_item,
    answers_payload,
    companies_payload,
    company_card,
    company_item,
    metric_card,
    metric_item,
    metrics_payload,
)

MID = 826615
MID2 = 900001  # a second numeric metric, for composite scores
COMPANIES = [
    company_item(100, "Apple Inc.", ["US0378331005"]),
    company_item(200, "Adidas AG", ["DE000A1EWWW0"], "Germany"),
    company_item(300, "Puma", ["DE0006969603"], "Germany"),
]


def respond(path: str, query: dict[str, list[str]]) -> bytes | None:
    if path == "/Metrics.json":
        return metrics_payload(
            metric_item(MID),
            metric_item(MID2, title="Women on the board", unit="%"),
            metric_item(1, value_type="Category", title="Report available"),
        )
    if path == f"/~{MID}.json":
        return metric_card(MID)
    if path == f"/~{MID2}.json":
        card = json.loads(metric_card(MID2))
        card["title"] = "Women on the board"
        return json.dumps(card).encode()
    if path == "/~300.json":
        return company_card(300, "Puma")
    if path == "/Companies.json":
        ids = query.get("filter[company_identifier[value]]", [""])[0]
        name = query.get("filter[name]", [""])[0].lower()
        hits = (
            [
                c
                for c in COMPANIES
                if any(i in ids for i in c["international_securities_identification_number"])
            ]
            if ids
            else [c for c in COMPANIES if name and name in c["name"].lower()]
        )
        return companies_payload(*hits)
    if path == f"/~{MID}+Answers.json":
        return answers_payload(
            answer_item("Apple Inc.", 2023, "800"),
            answer_item("Adidas AG", 2023, "Unknown"),
            answer_item("Puma", 2023, "400"),
        )
    if path == f"/~{MID2}+Answers.json":
        return answers_payload(
            answer_item("Apple Inc.", 2023, "40", MID2),
            answer_item("Adidas AG", 2023, "35", MID2),
            answer_item("Puma", 2023, "20", MID2),
        )
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlparse(self.path)
        body = respond(url.path, parse_qs(url.query))
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body or b"{}")

    def log_message(self, *_args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
