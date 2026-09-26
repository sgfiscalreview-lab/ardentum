"""Frankfurter (ECB) and FRED payload handling against their documented formats."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from ardentum.data.errors import DataProviderError
from ardentum.data.providers import fred, fx
from ardentum.quant.errors import InvalidInputError

PAYLOAD = {
    "amount": 1.0,
    "base": "EUR",
    "start_date": "1999-01-04",
    "end_date": "2024-01-03",
    "rates": {"2024-01-03": {"USD": 1.0919}, "2024-01-02": {"USD": 1.0956}},
}


@respx.mock
def test_timeseries_request_and_parse() -> None:
    route = respx.get(f"{fx.BASE_URL}/v1/1999-01-04..").mock(
        return_value=httpx.Response(200, json=PAYLOAD)
    )
    s = fx.parse_timeseries(fx.timeseries_payload("eur", "usd"), "USD")
    assert route.calls.last.request.url.params["base"] == "EUR"
    assert route.calls.last.request.url.params["symbols"] == "USD"
    assert list(s.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert s.iloc[-1] == 1.0919


@respx.mock
def test_timeseries_errors() -> None:
    respx.get(f"{fx.BASE_URL}/v1/1999-01-04..").mock(return_value=httpx.Response(404))
    with pytest.raises(DataProviderError, match="HTTP 404"):
        fx.timeseries_payload("EUR", "USD")
    with pytest.raises(InvalidInputError, match="no ECB reference rate"):
        fx.check_currency("XYZ")
    with pytest.raises(DataProviderError, match="format"):
        fx.parse_timeseries(b"{}", "USD")
    with pytest.raises(DataProviderError, match="No exchange rates"):
        fx.parse_timeseries(json.dumps({"rates": {"2024-01-02": {"GBP": 0.8}}}).encode(), "USD")


def test_fred_parse_observations() -> None:
    payload = json.dumps(
        {
            "observations": [
                {"date": "2024-01-02", "value": "5.40"},
                {"date": "2024-01-03", "value": "."},
                {"date": "2024-01-04", "value": "5.38"},
            ]
        }
    ).encode()
    s = fred.parse_observations(payload, "DGS3MO")
    assert list(s.round(6)) == [0.054, 0.0538]
    with pytest.raises(DataProviderError, match="no observations"):
        fred.parse_observations(b'{"observations": []}', "DGS3MO")
    with pytest.raises(DataProviderError, match="format"):
        fred.parse_observations(b"[]", "DGS3MO")
