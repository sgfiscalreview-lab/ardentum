"""WikiRate parsing and client behaviour against the documented formats."""

from __future__ import annotations

import httpx
import pytest
import respx

from ardentum.data.errors import DataProviderError
from ardentum.data.providers import wikirate as wr
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


def test_parse_metric_list_and_single_card() -> None:
    [m] = wr.parse_metrics(metrics_payload(metric_item()))
    assert m.id == 826615
    assert m.designer == "Global Reporting Initiative"
    assert m.unit == "tonnes CO2 equivalent"
    assert m.topics == ("Environment", "Climate Change")
    assert m.numeric
    assert m.url.endswith("Direct_GHG_Scope_1")

    card = wr.parse_metric(metric_card(rng="0-10"))
    assert card.value_type == "Number"
    assert card.metric_type == "Researched"
    assert card.unit == "tonnes CO2 equivalent"
    assert card.range == "0-10"
    assert card.topics == ()  # an empty nested list card
    empty = wr.parse_metric(metric_card(value_type=None))
    assert empty.value_type is None  # never the nested card's own name
    assert empty.range is None
    assert not wr.parse_metrics(metrics_payload(metric_item(value_type="Category")))[0].numeric


def test_parse_companies_both_shapes() -> None:
    [c] = wr.parse_companies(companies_payload(company_item(7, "Adidas AG", ["de000a1ewww0"])))
    assert c.isins == ("DE000A1EWWW0",)
    assert c.headquarters == "United States"
    single = wr.parse_companies(b'{"items": [' + company_card(9, "Puma") + b"]}")[0]
    assert single.isins == ("DE0006969603",)
    assert single.headquarters == "Germany"


def test_parse_answers_and_numbers() -> None:
    answers, nxt = wr.parse_answers(
        answers_payload(answer_item("Apple Inc.", 2023, "1,234.5"), nxt="https://wikirate.org/next")
    )
    assert answers[0].year == 2023
    assert answers[0].url.endswith("Apple_Inc.+2023")
    assert nxt == "https://wikirate.org/next"
    assert wr.parse_number("1,234.5") == 1234.5
    assert wr.parse_number("Unknown") is None
    assert wr.parse_number("Yes") is None
    assert wr.parse_number("nan") is None
    with pytest.raises(DataProviderError, match="format"):
        wr.parse_answers(b"[]")


@respx.mock
def test_client_sends_key_and_reports_errors() -> None:
    route = respx.get(f"{wr.BASE_URL}/Metrics.json").mock(
        return_value=httpx.Response(200, content=metrics_payload())
    )
    path, params = wr.metrics_query("emissions", 5)
    wr.WikiRateClient("secret").get(path, params)
    req = route.calls.last.request
    assert req.headers["X-API-Key"] == "secret"
    assert req.url.params["filter[name]"] == "emissions"
    respx.get(f"{wr.BASE_URL}/Companies.json").mock(return_value=httpx.Response(401))
    with pytest.raises(DataProviderError, match="ARDENTUM_WIKIRATE_API_KEY"):
        wr.WikiRateClient().get(*wr.companies_by_name_query("x", 1))
    respx.get(f"{wr.BASE_URL}/~1.json").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(DataProviderError, match="unreachable"):
        wr.WikiRateClient().get(wr.metric_path(1), [])


def test_answers_query_uses_company_ids() -> None:
    path, params = wr.answers_query(826615, [1, 2], 100)
    assert path == "/~826615+Answers.json"
    assert ("filter[company][]", "~1") in params
    assert ("filter[company][]", "~2") in params
    assert ("offset", "100") in params
