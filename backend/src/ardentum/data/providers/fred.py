"""FRED adapter for the risk-free rate.

Default series ``DGS3MO``: Market Yield on U.S. Treasury Securities at 3-Month
Constant Maturity, Quoted on an Investment Basis (percent, daily), published by
the Board of Governors of the Federal Reserve System via FRED (Federal Reserve
Bank of St. Louis). U.S. government data in the public domain; FRED asks users
to cite the source. Endpoint: ``/fred/series/observations`` (JSON). Missing
observations are reported as ``"."`` and dropped.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pandas as pd

from ardentum.data.errors import DataNotConfiguredError, DataProviderError
from ardentum.data.http import shared_client

BASE_URL = "https://api.stlouisfed.org"
DEFAULT_SERIES = "DGS3MO"


class FredClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        client: httpx.Client | None = None,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
    ) -> None:
        if not api_key:
            raise DataNotConfiguredError("FRED is not configured: set FRED_API_KEY.")
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._client = client or shared_client()
        self._timeout = timeout

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._client.get(url, timeout=self._timeout, **kwargs)

    def series_payload(self, series_id: str, start: dt.date = dt.date(1980, 1, 1)) -> bytes:
        """Raw JSON observations from ``start`` to today (for caching)."""
        try:
            resp = self._get(
                f"{self._base}/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self._key,
                    "file_type": "json",
                    "observation_start": start.isoformat(),
                },
            )
        except httpx.HTTPError as exc:
            raise DataProviderError(f"FRED is unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise DataProviderError(f"FRED request failed (HTTP {resp.status_code}).")
        return resp.content

    def series(self, series_id: str, start: dt.date, end: dt.date) -> pd.Series:
        """Observations as decimal fractions (percent / 100)."""
        try:
            resp = self._get(
                f"{self._base}/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self._key,
                    "file_type": "json",
                    "observation_start": start.isoformat(),
                    "observation_end": end.isoformat(),
                },
            )
        except httpx.HTTPError as exc:
            raise DataProviderError(f"FRED is unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise DataProviderError(f"FRED request failed (HTTP {resp.status_code}).")
        try:
            obs = resp.json()["observations"]
            pairs = [(o["date"], o["value"]) for o in obs if o["value"] not in (".", "")]
        except (KeyError, TypeError, ValueError) as exc:
            raise DataProviderError("Unexpected FRED response format.") from exc
        if not pairs:
            raise DataProviderError(f"FRED returned no observations for {series_id}.")
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in pairs])
        return pd.Series([float(v) / 100.0 for _, v in pairs], index=idx, name=series_id)

    def average_rate(self, start: dt.date, end: dt.date, series_id: str = DEFAULT_SERIES) -> float:
        """Mean annual yield over a window (decimal), e.g. for Sharpe ratios."""
        return float(self.series(series_id, start, end).mean())


def parse_observations(payload: bytes, series_id: str) -> pd.Series:
    """Observations as decimal fractions (percent / 100); '.' marks missing values."""
    try:
        obs = json.loads(payload)["observations"]
        pairs = [(o["date"], o["value"]) for o in obs if o["value"] not in (".", "")]
    except (KeyError, TypeError, ValueError) as exc:
        raise DataProviderError("Unexpected FRED response format.") from exc
    if not pairs:
        raise DataProviderError(f"FRED returned no observations for {series_id}.")
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in pairs])
    return pd.Series([float(v) / 100.0 for _, v in pairs], index=idx, name=series_id)
