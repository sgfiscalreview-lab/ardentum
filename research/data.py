"""Download and parse the public data the studies use.

Sources (all free, public):
* Kenneth R. French Data Library (Tuck School of Business, Dartmouth): monthly value-weighted
  returns of 12 US industry portfolios and the Fama-French research factors (market, T-bill).
* European Central Bank reference exchange rates, served by Frankfurter.
* Bank for International Settlements, central-bank policy rates (WS_CBPOL).

Raw downloads are cached in ``research/data/raw`` (not committed) so a rerun is offline.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from ardentum.data.providers import bis, fx, kenfrench

RAW = Path(__file__).parent / "data" / "raw"

KF_INDUSTRIES = "12_Industry_Portfolios"
KF_FACTORS = "F-F_Research_Data_Factors"


def _cached(name: str, fetch) -> bytes:  # type: ignore[no-untyped-def]
    path = RAW / name
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch())
    return path.read_bytes()


def _month_end(codes: pd.Index) -> pd.DatetimeIndex:
    return pd.PeriodIndex(codes.astype(str), freq="M").to_timestamp(how="end").normalize()


def monthly_industries() -> pd.DataFrame:
    """Monthly value-weighted returns (decimal) of the 12 US industries, indexed by month end."""
    text = kenfrench.unzip_text(_cached(f"{KF_INDUSTRIES}.zip", lambda: kenfrench.download(KF_INDUSTRIES)))
    table = kenfrench.find_table(kenfrench.parse_tables(text), "value weighted")
    frame = table.frame[table.frame.index > 100000]  # monthly YYYYMM codes only
    df = frame / 100.0
    df.index = _month_end(df.index)
    df.columns = [kenfrench.ticker_for(c) for c in df.columns]
    return df.dropna()


def monthly_factors() -> pd.DataFrame:
    """Monthly US market (Mkt-RF + RF) and one-month T-bill (RF) returns, decimal."""
    text = kenfrench.unzip_text(_cached(f"{KF_FACTORS}.zip", lambda: kenfrench.download(KF_FACTORS)))
    t = kenfrench.parse_tables(text)[0]
    frame = t.frame[t.frame.index > 100000]
    cols = {c.upper(): c for c in frame.columns}
    df = pd.DataFrame(
        {
            "MKT": (frame[cols["MKT-RF"]] + frame[cols["RF"]]) / 100.0,
            "RF": frame[cols["RF"]] / 100.0,
        }
    )
    df.index = _month_end(frame.index)
    return df.dropna()


def fx_month_end(base: str, local: str) -> pd.Series:
    """Month-end units of ``base`` per 1 ``local`` (ECB reference rates, from 1999)."""
    payload = _cached(f"fx_{local}_{base}.json", lambda: fx.timeseries_payload(local, base))
    daily = fx.parse_timeseries(payload, base)
    return daily.resample("ME").last().dropna()


def policy_rate_month_end(currency: str) -> pd.Series:
    """Month-end central-bank policy rate (annual, decimal) from the BIS."""
    payload = _cached(f"bis_{currency}.csv", lambda: bis.rates_payload(currency))
    daily = bis.parse_rates(payload, currency)
    return daily.resample("ME").last().ffill().dropna()


def load_frame(csv: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(csv), index_col=0, parse_dates=True)
