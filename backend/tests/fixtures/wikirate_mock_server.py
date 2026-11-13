"""A local stand-in for WikiRate and the Kenneth French Data Library (for E2E tests).

Run: ``uv run python -m tests.fixtures.wikirate_mock_server 8765`` and point the API at
it with ``ARDENTUM_WIKIRATE_BASE_URL=http://localhost:8765/rest/v1``, the keys
``ARDENTUM_WIKIRATE_PUBLISHABLE_KEY=pk-test`` and ``ARDENTUM_WIKIRATE_API_TOKEN=wr_test``, and
``ARDENTUM_KENFRENCH_BASE_URL=http://localhost:8765/kenfrench/``. The Ken French files
are the generated test fixtures (400 business days from 2020-01-02), not real data.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ardentum.data.providers import kenfrench as kf
from tests.fixtures.kenfrench import (
    factors_daily_text,
    industries_daily_text,
    industries_monthly_text,
    zipped,
)
from tests.fixtures.wikirate import FakeWikiRate, answer_row, company_row, metric_row

MID = 826615
MID2 = 900001  # a second numeric metric, for composite scores
PREFIX = "/rest/v1"
FAKE = FakeWikiRate(
    metrics=[
        metric_row(MID),
        metric_row(MID2, metric_name="Women on the board", unit="%"),
        metric_row(1, value_type="category", metric_name="Emissions report available"),
    ],
    companies=[
        company_row(100, "Apple Inc.", ["US0378331005"]),
        company_row(200, "Adidas AG", ["DE000A1EWWW0"], "Germany"),
        company_row(300, "Puma", ["DE0006969603"], "Germany"),
    ],
    answers=[
        answer_row(100, "Apple Inc.", 2023, "800"),
        answer_row(200, "Adidas AG", 2023, "Unknown"),
        answer_row(300, "Puma", 2023, "400"),
        answer_row(100, "Apple Inc.", 2023, "40", MID2),
        answer_row(200, "Adidas AG", 2023, "35", MID2),
        answer_row(300, "Puma", 2023, "20", MID2),
    ],
)


KENFRENCH = {
    f"/kenfrench/{kf.FACTORS_DAILY}_CSV.zip": lambda: zipped("f", factors_daily_text(400)),
    "/kenfrench/12_Industry_Portfolios_daily_CSV.zip": lambda: zipped(
        "d", industries_daily_text(400)
    ),
    "/kenfrench/12_Industry_Portfolios_CSV.zip": lambda: zipped("m", industries_monthly_text()),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path.startswith("/kenfrench/"):
            make = KENFRENCH.get(url.path)
            self.send_response(200 if make else 404)
            self.send_header("Content-Type", "application/zip")
            self.end_headers()
            self.wfile.write(make() if make else b"")
            return
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        headers = {k.lower(): v for k, v in self.headers.items()}
        status, body = FAKE.respond(url.path.removeprefix(PREFIX), query, headers)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
