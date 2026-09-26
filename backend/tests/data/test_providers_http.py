import datetime as dt

import httpx
import pytest
import respx

from ardentum.data.errors import DataNotConfiguredError, DataProviderError
from ardentum.data.providers.fred import FredClient
from ardentum.data.providers.tiingo import TiingoProvider

TIINGO_ROWS = [
    {
        "date": "2024-01-02T00:00:00.000Z",
        "close": 185.64,
        "adjClose": 184.29,
        "divCash": 0.0,
        "splitFactor": 1.0,
    },
    {
        "date": "2024-01-03T00:00:00.000Z",
        "close": 184.25,
        "adjClose": 182.91,
        "divCash": 0.0,
        "splitFactor": 1.0,
    },
]


@respx.mock
def test_tiingo_prices_use_adjclose_and_token_header() -> None:
    route = respx.get("https://api.tiingo.com/tiingo/daily/abc/prices").mock(
        return_value=httpx.Response(200, json=TIINGO_ROWS)
    )
    p = TiingoProvider("secret")
    data = p.fetch_prices(["ABC"], dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    assert list(data.prices["ABC"]) == [184.29, 182.91]
    assert data.prices.index[0] == dt.datetime(2024, 1, 2)
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Token secret"
    assert req.url.params["startDate"] == "2024-01-01"
    assert not data.provenance.is_synthetic


@respx.mock
@pytest.mark.parametrize(
    ("status", "match"), [(401, "API key"), (404, "does not recognise"), (429, "rate limit")]
)
def test_tiingo_errors(status: int, match: str) -> None:
    respx.get("https://api.tiingo.com/tiingo/daily/abc/prices").mock(
        return_value=httpx.Response(status)
    )
    with pytest.raises(DataProviderError, match=match):
        TiingoProvider("k").fetch_prices(["ABC"], dt.date(2024, 1, 1), dt.date(2024, 2, 1))


@respx.mock
def test_tiingo_retries_server_errors_then_fails() -> None:
    route = respx.get("https://api.tiingo.com/tiingo/daily/abc/prices").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(DataProviderError, match="unreachable"):
        TiingoProvider("k").fetch_prices(["ABC"], dt.date(2024, 1, 1), dt.date(2024, 2, 1))
    assert route.call_count == 2


@respx.mock
def test_tiingo_malformed_payload() -> None:
    respx.get("https://api.tiingo.com/tiingo/daily/abc/prices").mock(
        return_value=httpx.Response(200, json=[{"date": "2024-01-02"}])
    )
    with pytest.raises(DataProviderError, match="Unexpected"):
        TiingoProvider("k").fetch_prices(["ABC"], dt.date(2024, 1, 1), dt.date(2024, 2, 1))


@respx.mock
def test_tiingo_metadata() -> None:
    respx.get("https://api.tiingo.com/tiingo/daily/abc").mock(
        return_value=httpx.Response(
            200, json={"ticker": "abc", "name": "ABC Corp", "description": "Makes things."}
        )
    )
    info = TiingoProvider("k").fetch_metadata("abc")
    assert info.ticker == "ABC"
    assert info.name == "ABC Corp"


def test_providers_require_keys() -> None:
    with pytest.raises(DataNotConfiguredError):
        TiingoProvider(None)
    with pytest.raises(DataNotConfiguredError):
        FredClient("")


@respx.mock
def test_fred_series_drops_missing_and_converts_percent() -> None:
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2024-01-02", "value": "5.40"},
                    {"date": "2024-01-03", "value": "."},
                    {"date": "2024-01-04", "value": "5.20"},
                ]
            },
        )
    )
    c = FredClient("k")
    s = c.series("DGS3MO", dt.date(2024, 1, 1), dt.date(2024, 1, 31))
    assert list(s) == pytest.approx([0.054, 0.052])
    assert c.average_rate(dt.date(2024, 1, 1), dt.date(2024, 1, 31)) == pytest.approx(0.053)


@respx.mock
def test_fred_http_error() -> None:
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(DataProviderError):
        FredClient("k").series("DGS3MO", dt.date(2024, 1, 1), dt.date(2024, 1, 31))
