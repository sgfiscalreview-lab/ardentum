"""WikiRate parsing and client behaviour against the documented formats."""

from __future__ import annotations

import httpx
import pytest
import respx

from ardentum.data.errors import DataProviderError
from ardentum.data.providers import wikirate as wr
from tests.fixtures.wikirate import (
    CC_BY,
    HEADERS,
    FakeWikiRate,
    answer_row,
    company_row,
    metric_row,
    payload,
)


def test_parse_metrics() -> None:
    [m] = wr.parse_metrics(payload(metric_row()))
    assert m.id == 826615
    assert m.designer == "Global Reporting Initiative"
    assert m.unit == "tonnes CO2 equivalent"
    assert m.answers is None
    assert m.numeric
    # The page address follows the names, as on wikirate.org.
    assert m.url == (
        "https://wikirate.org/Global_Reporting_Initiative"
        "+Direct_greenhouse_gas_GHG_emissions_Scope_1"
    )
    assert wr.parse_metric(payload(metric_row(range={"min": 0, "max": 10}))).range == "0-10"
    assert wr.parse_metric(payload(metric_row(range={"something": "else"}))).range is None
    assert not wr.parse_metric(payload(metric_row(value_type="category"))).numeric
    assert wr.parse_metric(payload(metric_row(value_type=None, metric_type="score"))).numeric
    with pytest.raises(DataProviderError, match="no such metric"):
        wr.parse_metric(b"[]")
    # A malformed row is skipped, not fatal.
    assert len(wr.parse_metrics(payload({"id": "x"}, metric_row()))) == 1


def test_parse_companies() -> None:
    [c] = wr.parse_companies(payload(company_row(7, "Adidas AG", ["de000a1ewww0"], "Germany")))
    assert c.isins == ("DE000A1EWWW0",)
    assert c.headquarters == "Germany"
    assert c.url == "https://wikirate.org/Adidas_AG"
    bare = {"id": 9, "name": "Puma", "headquarters": None, "company_identifiers": {"isin": "x1"}}
    [p] = wr.parse_companies(payload(bare))
    assert p.isins == ("X1",)  # a single identifier given as text
    assert p.headquarters is None
    assert (
        wr.parse_companies(payload({"id": 1, "name": "A", "company_identifiers": None}))[0].isins
        == ()
    )


def test_parse_answers_and_numbers() -> None:
    [a] = wr.parse_answers(payload(answer_row(100, "Apple Inc.", 2023, "1,234.5")))
    assert (a.company_id, a.year, a.value) == (100, 2023, "1,234.5")
    assert a.url == "https://example.com/apple-inc.-2023.pdf"
    assert a.license == "CC BY 4.0"
    assert a.cc_by
    assert wr.parse_number("1,234.5") == 1234.5
    assert wr.parse_number("Unknown") is None
    assert wr.parse_number("Yes") is None
    assert wr.parse_number("nan") is None
    with pytest.raises(DataProviderError, match="format"):
        wr.parse_answers(b'{"message": "error"}')
    with pytest.raises(DataProviderError, match="format"):
        wr.check_json(b"<html>")


@pytest.mark.parametrize(
    ("stated", "cc_by"),
    [
        (CC_BY, True),
        ({"abbreviation": "CC-BY-4.0"}, True),
        ({"name": "Creative Commons Attribution 4.0 International"}, True),
        ({"reference_url": "https://creativecommons.org/licenses/by/4.0/"}, True),
        (None, True),  # none stated
        ({"abbreviation": "CC BY-NC 4.0", "name": "Attribution-NonCommercial 4.0"}, False),
        ({"abbreviation": "CC BY-SA 4.0"}, False),
        ("All rights reserved", False),
    ],
)
def test_only_cc_by_answers_count_as_open(stated: object, cc_by: bool) -> None:
    [a] = wr.parse_answers(payload(answer_row(1, "A", 2023, "1", license=stated)))
    assert a.cc_by is cc_by


def test_only_web_links_are_kept() -> None:
    bad = answer_row(1, "A", 2023, "1", sources=[{"original_url": "javascript:alert(1)"}])
    odd = answer_row(1, "A", 2022, "1", sources=[{"original_url": " DATA:text/html,x"}])
    none = answer_row(1, "A", 2021, "1", sources=None)
    assert [a.url for a in wr.parse_answers(payload(bad, odd, none))] == ["", "", ""]


def test_queries() -> None:
    path, params = wr.answers_query(826615, [1, 2], 1000)
    assert path == "/v1_answers"
    assert ("metric_id", "eq.826615") in params
    assert ("company_id", "in.(1,2)") in params
    assert ("offset", "1000") in params
    assert ("order", "id") in params  # a stable order, so pages do not shift
    # A search text cannot add wildcards of its own.
    assert dict(wr.metrics_query("scope * 1", 5)[1])["metric_name"] == "ilike.*scope 1*"
    one = dict(wr.companies_by_isin_query(["US0378331005"])[1])
    assert one["company_identifiers->>isin"] == "like.*US0378331005*"
    # Only ISINs become part of a combined filter; anything else could change its meaning.
    two = dict(wr.companies_by_isin_query(["US0378331005", "x),id.gt.0", "DE000A1EWWW0"])[1])
    assert two["or"] == (
        "(company_identifiers->>isin.like.*US0378331005*,"
        "company_identifiers->>isin.like.*DE000A1EWWW0*)"
    )
    with pytest.raises(ValueError, match="ISIN"):
        wr.companies_by_isin_query(["not an isin"])


@respx.mock
def test_client_sends_keys_and_reports_errors() -> None:
    fake = FakeWikiRate(metrics=[metric_row()])
    route = fake.install()
    client = wr.WikiRateClient(HEADERS["apikey"], HEADERS["x-api-token"])
    assert len(wr.parse_metrics(client.get(*wr.metrics_query("emissions", 5)))) == 1
    sent = route.calls.last.request
    assert sent.headers["apikey"] == "pk-test"
    assert sent.headers["x-api-token"] == "wr_test"
    assert sent.headers["Accept-Profile"] == "api"
    assert sent.url.path == "/rest/v1/v1_metrics"

    with pytest.raises(DataProviderError, match="ARDENTUM_WIKIRATE_API_TOKEN"):
        wr.WikiRateClient("pk-test", "revoked").get(*wr.metrics_query("x", 1))
    # Without keys nothing is sent: the message says how to switch the feature on.
    calls = route.call_count
    with pytest.raises(DataProviderError, match="switched off"):
        wr.WikiRateClient().get(*wr.metrics_query("x", 1))
    assert route.call_count == calls


@respx.mock
def test_client_status_codes() -> None:
    client = wr.WikiRateClient("k", "t")
    url = f"{wr.BASE_URL}/v1_answers"
    respx.get(url).mock(return_value=httpx.Response(416))
    assert client.get("/v1_answers", []) == b"[]"  # an offset past the last row
    respx.get(url).mock(return_value=httpx.Response(400))
    with pytest.raises(wr.BadRequestError):
        client.get("/v1_answers", [])
    respx.get(url).mock(return_value=httpx.Response(503))
    with pytest.raises(DataProviderError, match="HTTP 503"):
        client.get("/v1_answers", [])
    respx.get(url).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(DataProviderError, match="unreachable"):
        client.get("/v1_answers", [])


def test_the_stand_in_pages_and_filters() -> None:
    fake = FakeWikiRate(answers=[answer_row(1, "A", 2000 + i, str(i)) for i in range(5)])
    path, params = wr.answers_query(826615, [1], 0)
    query = {**dict(params), "limit": "2"}
    status, body = fake.respond(path, query, {**HEADERS, "accept-profile": "api"})
    assert status == 200
    assert [a.year for a in wr.parse_answers(body)] == [2000, 2001]
    assert (
        fake.respond(path, {**query, "offset": "9"}, {**HEADERS, "accept-profile": "api"})[0] == 416
    )
