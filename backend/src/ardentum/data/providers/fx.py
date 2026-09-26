"""Exchange rates from Frankfurter (https://frankfurter.dev): free, keyless, open source.

We use the v1 endpoint, which serves European Central Bank euro foreign-exchange
reference rates (published every ECB business day since 4 January 1999):
``GET /v1/{start}..{end}?base=LOCAL&symbols=BASE`` returns
``{"amount": 1.0, "base": ..., "start_date": ..., "end_date": ..., "rates": {date: {BASE: rate}}}``.
Frankfurter states the API is free for commercial use; the ECB publishes the
reference rates for information purposes.
"""

from __future__ import annotations

import datetime as dt
import json

import httpx
import pandas as pd

from ardentum.data.errors import DataProviderError
from ardentum.quant.errors import InvalidInputError

BASE_URL = "https://api.frankfurter.dev"
ECB_START = dt.date(1999, 1, 4)
# Currencies with ECB reference rates (plus EUR itself).
SUPPORTED = frozenset(
    [
        "AUD",
        "BGN",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "EUR",
        "GBP",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "ISK",
        "JPY",
        "KRW",
        "MXN",
        "MYR",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RON",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "USD",
        "ZAR",
    ]
)
SOURCE = "European Central Bank reference rates via Frankfurter (frankfurter.dev)"


def check_currency(code: str) -> str:
    c = code.strip().upper()
    if c not in SUPPORTED:
        raise InvalidInputError(
            f"Currency {code!r} has no ECB reference rate; supported: {', '.join(sorted(SUPPORTED))}."
        )
    return c


def timeseries_payload(local: str, base: str, client: httpx.Client | None = None) -> bytes:
    """All daily rates (units of ``base`` per 1 ``local``) since 1999, as raw JSON."""
    c = client or httpx.Client(timeout=30.0, follow_redirects=True)
    url = f"{BASE_URL}/v1/{ECB_START.isoformat()}.."
    try:
        resp = c.get(url, params={"base": check_currency(local), "symbols": check_currency(base)})
    except httpx.HTTPError as exc:
        raise DataProviderError(f"The exchange-rate service is unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise DataProviderError(f"Exchange-rate request failed (HTTP {resp.status_code}).")
    return resp.content


def parse_timeseries(payload: bytes, base: str) -> pd.Series:
    try:
        data = json.loads(payload)
        rates = {d: float(v[base]) for d, v in data["rates"].items() if base in v}
    except (KeyError, TypeError, ValueError) as exc:
        raise DataProviderError("Unexpected exchange-rate response format.") from exc
    if not rates:
        raise DataProviderError(f"No exchange rates returned for {base}.")
    s = pd.Series(rates, dtype=float)
    s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
    return s.sort_index()
