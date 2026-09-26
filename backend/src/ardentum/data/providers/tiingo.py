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
from typing import Any

import httpx
import pandas as pd

from ardentum.data.errors import DataNotConfiguredError, DataProviderError
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
        self._client = client or httpx.Client(timeout=timeout)

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self._base}{path}"
        headers = {"Authorization": f"Token {self._key}", "Content-Type": "application/json"}
        last: Exception | None = None
        for _ in range(2):
            try:
                resp = self._client.get(url, params=params, headers=headers)
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

    def fetch_prices(self, tickers: list[str], start: dt.date, end: dt.date) -> PriceData:
        series: dict[str, pd.Series] = {}
        for t in tickers:
            rows = self._get(
                f"/tiingo/daily/{t.lower()}/prices",
                {"startDate": start.isoformat(), "endDate": end.isoformat(), "format": "json"},
            )
            if not isinstance(rows, list) or not rows:
                raise DataProviderError(
                    f"Tiingo returned no prices for {t} in the requested range."
                )
            try:
                idx = pd.DatetimeIndex(
                    [pd.Timestamp(r["date"]).tz_localize(None).normalize() for r in rows]
                )
                vals = [float(r["adjClose"]) for r in rows]
            except (KeyError, TypeError, ValueError) as exc:
                raise DataProviderError(f"Unexpected Tiingo response format for {t}.") from exc
            series[t.upper()] = pd.Series(vals, index=idx, name=t.upper())
        prices = pd.DataFrame(series).sort_index()
        prices.index.name = "date"
        return PriceData(
            prices=prices,
            provenance=DataProvenance(
                source=SOURCE,
                is_synthetic=False,
                adjustment="Split- and dividend-adjusted close (total return).",
                retrieved_at=dt.datetime.now(dt.UTC),
                license_note="Subject to the Tiingo terms of service for the configured plan.",
            ),
        )

    def fetch_metadata(self, ticker: str) -> AssetInfo:
        meta = self._get(f"/tiingo/daily/{ticker.lower()}")
        if not isinstance(meta, dict):
            raise DataProviderError(f"Unexpected Tiingo metadata format for {ticker}.")
        return AssetInfo(
            ticker=ticker.upper(),
            name=str(meta.get("name") or ticker.upper()).strip(),
            description=(str(meta["description"])[:500] if meta.get("description") else None),
        )
