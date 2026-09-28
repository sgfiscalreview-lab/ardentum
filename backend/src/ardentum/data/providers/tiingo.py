"""Tiingo end-of-day price adapter.

Endpoint: ``GET https://api.tiingo.com/tiingo/daily/{ticker}/prices`` with
``startDate``/``endDate`` (YYYY-MM-DD); authentication via the
``Authorization: Token <key>`` header. Uses ``adjClose`` (split- and
dividend-adjusted close), so returns are total returns.

Licensing: Tiingo's free plan is licensed for personal use; commercial use or
redistribution to end users requires a commercial plan. See DECISIONS.md D-004
and TODO.md (founder decision required before production use).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pandas as pd

from ardentum.data.errors import DataNotConfiguredError, DataProviderError
from ardentum.data.http import shared_client
from ardentum.data.models import AssetInfo, DataProvenance, PriceData

BASE_URL = "https://api.tiingo.com"
SOURCE = "Tiingo End-of-Day API (adjClose)"


class TiingoProvider:
    name = "tiingo"

    def __init__(
        self,
        api_key: str | None,
        *,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
    ) -> None:
        if not api_key:
            raise DataNotConfiguredError(
                "Tiingo is not configured: set TIINGO_API_KEY to enable live market data."
            )
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._client = client or shared_client()
        self._timeout = timeout

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self._base}{path}"
        headers = {"Authorization": f"Token {self._key}", "Content-Type": "application/json"}
        last: Exception | None = None
        for _ in range(2):
            try:
                resp = self._client.get(url, params=params, headers=headers, timeout=self._timeout)
            except httpx.HTTPError as exc:
                last = exc
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                raise DataProviderError(f"Tiingo rejected the API key (HTTP {resp.status_code}).")
            if resp.status_code == 404:
                raise DataProviderError(
                    f"Tiingo does not recognise {path.split('/')[3].upper()!r}."
                )
            if resp.status_code == 429:
                raise DataProviderError("Tiingo rate limit reached; try again later.")
            if resp.status_code >= 500:
                last = DataProviderError(f"Tiingo server error (HTTP {resp.status_code}).")
                continue
            raise DataProviderError(f"Tiingo request failed (HTTP {resp.status_code}).")
        raise DataProviderError(f"Tiingo is unreachable: {last}")

    def history_payload(self, ticker: str) -> bytes:
        """Full daily history for one ticker as the raw JSON payload (for caching)."""
        rows = self._get(
            f"/tiingo/daily/{ticker.lower()}/prices",
            {"startDate": "1970-01-01", "format": "json"},
        )
        if not isinstance(rows, list) or not rows:
            raise DataProviderError(f"Tiingo returned no prices for {ticker}.")
        return json.dumps(rows).encode("utf-8")

    def fetch_prices(self, tickers: list[str], start: dt.date, end: dt.date) -> PriceData:
        series = {t.upper(): parse_history(self.history_payload(t), t) for t in tickers}
        prices = pd.DataFrame(series).sort_index().loc[pd.Timestamp(start) : pd.Timestamp(end)]
        prices.index.name = "date"
        return PriceData(prices=prices, provenance=provenance(dt.datetime.now(dt.UTC)))

    def fetch_metadata(self, ticker: str) -> AssetInfo:
        meta = self._get(f"/tiingo/daily/{ticker.lower()}")
        if not isinstance(meta, dict):
            raise DataProviderError(f"Unexpected Tiingo metadata format for {ticker}.")
        return AssetInfo(
            ticker=ticker.upper(),
            name=str(meta.get("name") or ticker.upper()).strip(),
            description=(str(meta["description"])[:500] if meta.get("description") else None),
        )


def parse_history(payload: bytes, ticker: str) -> pd.Series:
    """Adjusted closes from a Tiingo daily-prices payload."""
    try:
        rows = json.loads(payload)
        idx = pd.DatetimeIndex(
            [pd.Timestamp(r["date"]).tz_localize(None).normalize() for r in rows]
        )
        vals = [float(r["adjClose"]) for r in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise DataProviderError(f"Unexpected Tiingo response format for {ticker}.") from exc
    return pd.Series(vals, index=idx, name=ticker.upper()).sort_index()


def provenance(retrieved_at: dt.datetime | None) -> DataProvenance:
    return DataProvenance(
        source=SOURCE,
        is_synthetic=False,
        adjustment="Split- and dividend-adjusted close (total return).",
        retrieved_at=retrieved_at,
        license_note="Subject to the Tiingo terms of service for the configured plan.",
    )
