"""Test fixtures that reproduce the Kenneth French Data Library file format.

Values are generated for tests (not real data); the layout — descriptive header,
CRLF line endings, blank-line separated tables starting with a comma-led header
row, -99.99 missing codes and a copyright footer — mirrors the published files.
"""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd

from ardentum.data.providers.kenfrench import IND12


def _table(title: str, codes: list[str], index: list[str], values: np.ndarray) -> str:
    lines = [f"  {title}", "," + ",".join(f"{c:>6}" for c in codes)]
    for d, row in zip(index, values, strict=True):
        lines.append(d + "," + ",".join(f"{v:7.2f}" for v in row))
    return "\r\n".join(lines)


def industries_daily_text(n_days: int = 400, seed: int = 0, missing_first: int = 0) -> str:
    rng = np.random.default_rng(seed)
    codes = list(IND12)
    dates = [d.strftime("%Y%m%d") for d in pd.bdate_range("2020-01-02", periods=n_days)]
    vw = rng.normal(0.04, 1.2, size=(n_days, len(codes)))
    if missing_first:
        vw[:missing_first, 0] = -99.99
    ew = rng.normal(0.05, 1.4, size=(n_days, len(codes)))
    header = (
        "This file was created by CMPT_IND_RETS_DAILY using the 202512 CRSP database.\r\n"
        "It contains value- and equal-weighted returns for 12 industry portfolios.\r\n"
        "Missing data are indicated by -99.99 or -999.\r\n"
    )
    return (
        header
        + "\r\n"
        + _table("Average Value Weighted Returns -- Daily", [c.ljust(5) for c in codes], dates, vw)
        + "\r\n\r\n"
        + _table("Average Equal Weighted Returns -- Daily", codes, dates, ew)
        + "\r\n\r\n"
    )


def factors_daily_text(n_days: int = 400, seed: int = 1) -> str:
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y%m%d") for d in pd.bdate_range("2020-01-02", periods=n_days)]
    mkt = rng.normal(0.03, 1.0, n_days)
    rows = np.column_stack(
        [mkt, rng.normal(0, 0.5, n_days), rng.normal(0, 0.5, n_days), np.full(n_days, 0.008)]
    )
    lines = [",Mkt-RF,SMB,HML,RF"] + [
        d + "," + ",".join(f"{v:8.3f}" for v in r) for d, r in zip(dates, rows, strict=True)
    ]
    return (
        "This file was created by CMPT_ME_BEME_RETS_DAILY using the 202512 CRSP database.\r\n"
        "The Tbill return is the simple daily rate that, over the number of trading days\r\n"
        "in the month, compounds to 1-month TBill rate from Ibbotson and Associates Inc.\r\n\r\n"
        + "\r\n".join(lines)
        + "\r\n\r\n Copyright 2026 Kenneth R. French\r\n"
    )


def industries_monthly_text() -> str:
    codes = list(IND12)
    months = ["202410", "202411", "202412"]
    firms = np.tile(np.arange(100, 100 + len(codes)), (3, 1)).astype(float)
    size = np.tile(np.linspace(1000, 12000, len(codes)), (3, 1))
    ret = np.zeros((3, len(codes)))
    return (
        "This file was created by CMPT_IND_RETS using the 202512 CRSP database.\r\n\r\n"
        + _table("Average Value Weighted Returns -- Monthly", codes, months, ret)
        + "\r\n\r\n"
        + _table("Number of Firms in Portfolios", codes, months, firms)
        + "\r\n\r\n"
        + _table("Average Firm Size", codes, months, size)
        + "\r\n\r\n"
    )


def zipped(name: str, text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{name}.CSV", text.encode("utf-8"))
    return buf.getvalue()
