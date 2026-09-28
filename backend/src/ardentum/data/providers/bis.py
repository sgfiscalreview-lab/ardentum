"""Central-bank policy rates from the Bank for International Settlements (free, keyless).

Dataset WS_CBPOL, daily series, through the BIS SDMX API:
``GET https://stats.bis.org/api/v1/data/WS_CBPOL/D.{area}/all?startPeriod=...&detail=dataonly&format=csv``
returns ``FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE`` rows with the rate in percent (``NaN`` on
days without a value). BIS statistics may be reused, including commercially, provided the
BIS is cited as the source (https://www.bis.org/terms_statistics.htm).

Policy rates stand in for the short money-market rates that price currency forwards
(covered interest parity); the two differ by small spreads.
"""

from __future__ import annotations

import datetime as dt
import io

import httpx
import pandas as pd

from ardentum.data.errors import DataProviderError
from ardentum.quant.errors import InvalidInputError

BASE_URL = "https://stats.bis.org/api/v1/data/WS_CBPOL"
START = dt.date(1999, 1, 1)
SOURCE = "central bank policy rates from the Bank for International Settlements (BIS, WS_CBPOL)"

# Currency -> BIS reference area of the issuing central bank.
AREA = {
    "AUD": "AU",
    "BRL": "BR",
    "CAD": "CA",
    "CHF": "CH",
    "CNY": "CN",
    "CZK": "CZ",
    "DKK": "DK",
    "EUR": "XM",
    "GBP": "GB",
    "HKD": "HK",
    "HUF": "HU",
    "IDR": "ID",
    "ILS": "IL",
    "INR": "IN",
    "ISK": "IS",
    "JPY": "JP",
    "KRW": "KR",
    "MXN": "MX",
    "MYR": "MY",
    "NOK": "NO",
    "NZD": "NZ",
    "PHP": "PH",
    "PLN": "PL",
    "RON": "RO",
    "SEK": "SE",
    "THB": "TH",
    "TRY": "TR",
    "USD": "US",
    "ZAR": "ZA",
}


def area_for(currency: str) -> str:
    c = currency.strip().upper()
    if c not in AREA:
        raise InvalidInputError(
            f"No central-bank policy rate is available for {c}, so its returns cannot be "
            f"hedged; use unhedged returns. Hedging supports: {', '.join(sorted(AREA))}."
        )
    return AREA[c]


def rates_payload(currency: str, client: httpx.Client | None = None) -> bytes:
    """Daily policy rates of ``currency``'s central bank since 1999, as raw CSV."""
    area = area_for(currency)
    c = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        resp = c.get(
            f"{BASE_URL}/D.{area}/all",
            params={"startPeriod": START.isoformat(), "detail": "dataonly", "format": "csv"},
        )
    except httpx.HTTPError as exc:
        raise DataProviderError(f"The BIS statistics service is unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise DataProviderError(f"BIS has no daily policy-rate series for {currency}.")
    if resp.status_code != 200:
        raise DataProviderError(f"BIS policy-rate request failed (HTTP {resp.status_code}).")
    return resp.content


def parse_rates(payload: bytes, currency: str) -> pd.Series:
    """Annual rates as decimals (4.75% -> 0.0475), indexed by date, missing days dropped."""
    area = area_for(currency)
    try:
        df = pd.read_csv(io.BytesIO(payload), dtype={"REF_AREA": str})
        df = df[(df["REF_AREA"] == area) & (df["FREQ"] == "D")]
        values = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
        out = pd.Series(values.to_numpy() / 100.0, index=pd.to_datetime(df["TIME_PERIOD"]))
    except (KeyError, ValueError) as exc:
        raise DataProviderError("Unexpected BIS policy-rate response format.") from exc
    out = out.dropna().sort_index()
    if out.empty:
        raise DataProviderError(f"BIS returned no policy rates for {currency}.")
    return out
