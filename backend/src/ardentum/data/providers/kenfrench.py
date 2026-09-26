"""Kenneth R. French Data Library: real US industry-portfolio returns (free, no key).

Source: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
Files are zipped CSVs at ``ftp/<name>_CSV.zip``. Each file contains one or more
tables separated by blank lines; a table starts at a line beginning with a comma
(the column header) and its title is the text just above it. Values are percent
returns; ``-99.99`` and ``-999`` mark missing data. (Format as documented by the
library and implemented by pandas-datareader's FamaFrenchReader.)

Construction (from the library): every NYSE, AMEX and NASDAQ stock is assigned to
an industry at the end of June each year by its four-digit SIC code; portfolios
are value-weighted (we use the value-weighted tables). Returns include dividends.

Terms: the library is freely published by Prof. French and widely reused with
citation; it carries no explicit licence, so commercial redistribution should be
confirmed with the author (see DECISIONS D-018).
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from dataclasses import dataclass

import httpx
import numpy as np
import pandas as pd

from ardentum.data.errors import DataProviderError
from ardentum.data.models import AssetClass, AssetInfo, DataProvenance

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
MISSING = (-99.99, -999.0)
SOURCE = "Kenneth R. French Data Library (Dartmouth)"
LICENSE_NOTE = (
    "Freely published by Prof. Kenneth R. French; cite the Data Library. "
    "Confirm terms with the author before commercial redistribution."
)

IND12 = {
    "NoDur": "Consumer Non-Durables",
    "Durbl": "Consumer Durables",
    "Manuf": "Manufacturing",
    "Enrgy": "Oil, Gas & Coal",
    "Chems": "Chemicals",
    "BusEq": "Business Equipment",
    "Telcm": "Telecommunications",
    "Utils": "Utilities",
    "Shops": "Wholesale & Retail",
    "Hlth": "Healthcare",
    "Money": "Finance",
    "Other": "Other",
}

IND49 = {
    "Agric": "Agriculture",
    "Food": "Food Products",
    "Soda": "Candy & Soda",
    "Beer": "Beer & Liquor",
    "Smoke": "Tobacco",
    "Toys": "Recreation",
    "Fun": "Entertainment",
    "Books": "Printing & Publishing",
    "Hshld": "Consumer Goods",
    "Clths": "Apparel",
    "Hlth": "Healthcare",
    "MedEq": "Medical Equipment",
    "Drugs": "Pharmaceuticals",
    "Chems": "Chemicals",
    "Rubbr": "Rubber & Plastics",
    "Txtls": "Textiles",
    "BldMt": "Construction Materials",
    "Cnstr": "Construction",
    "Steel": "Steel Works",
    "FabPr": "Fabricated Products",
    "Mach": "Machinery",
    "ElcEq": "Electrical Equipment",
    "Autos": "Automobiles & Trucks",
    "Aero": "Aircraft",
    "Ships": "Shipbuilding & Railroad",
    "Guns": "Defense",
    "Gold": "Precious Metals",
    "Mines": "Industrial Metal Mining",
    "Coal": "Coal",
    "Oil": "Petroleum & Natural Gas",
    "Util": "Utilities",
    "Telcm": "Communication",
    "PerSv": "Personal Services",
    "BusSv": "Business Services",
    "Hardw": "Computers",
    "Softw": "Computer Software",
    "Chips": "Electronic Equipment",
    "LabEq": "Measuring & Control Equipment",
    "Paper": "Business Supplies",
    "Boxes": "Shipping Containers",
    "Trans": "Transportation",
    "Whlsl": "Wholesale",
    "Rtail": "Retail",
    "Meals": "Restaurants & Hotels",
    "Banks": "Banking",
    "Insur": "Insurance",
    "RlEst": "Real Estate",
    "Fin": "Trading",
    "Other": "Other",
}


@dataclass(frozen=True)
class KFDatasetSpec:
    id: str
    name: str
    daily_file: str
    monthly_file: str
    industries: dict[str, str]


DATASETS: dict[str, KFDatasetSpec] = {
    "kf12": KFDatasetSpec(
        "kf12",
        "US industries — 12 portfolios (Kenneth French)",
        "12_Industry_Portfolios_daily",
        "12_Industry_Portfolios",
        IND12,
    ),
    "kf49": KFDatasetSpec(
        "kf49",
        "US industries — 49 portfolios (Kenneth French)",
        "49_Industry_Portfolios_daily",
        "49_Industry_Portfolios",
        IND49,
    ),
}
FACTORS_DAILY = "F-F_Research_Data_Factors_daily"
MARKET_TICKER = "MKT"


@dataclass(frozen=True)
class Table:
    title: str
    frame: pd.DataFrame  # index: raw integer date codes; values: floats (percent)


def ticker_for(code: str) -> str:
    return code.strip().upper()


def parse_tables(text: str) -> list[Table]:
    """Split a French-library CSV into titled tables (values as floats, NaN for missing)."""
    text = re.sub(r"\r(?!\n)", "\r\n", text).replace("\r\n", "\n")
    tables: list[Table] = []
    for chunk in re.split(r"\n\s*\n", text):
        m = re.search(r"^\s*,", chunk, re.M)
        if not m:
            continue
        title = " ".join(chunk[: m.start()].split())
        body = chunk[m.start() :]
        lines = [ln for ln in body.split("\n") if ln.strip()]
        header = [c.strip() for c in lines[0].split(",")[1:]]
        rows: list[list[float]] = []
        index: list[int] = []
        for ln in lines[1:]:
            parts = [p.strip() for p in ln.split(",")]
            if not parts[0].isdigit():
                break  # footer such as a copyright line
            index.append(int(parts[0]))
            vals = []
            for p in parts[1 : len(header) + 1]:
                try:
                    v = float(p)
                except ValueError:
                    v = np.nan
                vals.append(np.nan if any(abs(v - mv) < 1e-9 for mv in MISSING) else v)
            rows.append(vals)
        if rows:
            tables.append(Table(title, pd.DataFrame(rows, index=index, columns=header)))
    if not tables:
        raise DataProviderError("Unexpected format in Kenneth French data file (no tables found).")
    return tables


def find_table(tables: list[Table], *keywords: str) -> Table:
    for t in tables:
        low = t.title.lower()
        if all(k.lower() in low for k in keywords):
            return t
    raise DataProviderError(f"Kenneth French file has no table matching {' '.join(keywords)!r}.")


def daily_index(codes: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(codes.astype(str), format="%Y%m%d"))


def unzip_text(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            raw = zf.read(zf.namelist()[0])
    except (zipfile.BadZipFile, IndexError) as exc:
        raise DataProviderError("Kenneth French download was not a valid zip file.") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def download(name: str, client: httpx.Client | None = None, timeout: float = 60.0) -> bytes:
    url = f"{BASE_URL}{name}_CSV.zip"
    c = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        resp = c.get(url)
    except httpx.HTTPError as exc:
        raise DataProviderError(f"The Kenneth French Data Library is unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise DataProviderError(f"Kenneth French download failed (HTTP {resp.status_code}).")
    return resp.content


def industry_returns(daily_text: str) -> pd.DataFrame:
    """Value-weighted daily industry returns (decimal) indexed by date."""
    t = find_table(parse_tables(daily_text), "value weighted")
    df = t.frame / 100.0
    df.index = daily_index(df.index)
    df.columns = [ticker_for(c) for c in df.columns]
    return df


def factor_returns(factors_text: str) -> pd.DataFrame:
    """Daily market (Mkt-RF + RF) and risk-free (RF) returns (decimal)."""
    t = parse_tables(factors_text)[0]
    cols = {c.upper(): c for c in t.frame.columns}
    if "MKT-RF" not in cols or "RF" not in cols:
        raise DataProviderError("Kenneth French factors file lacks Mkt-RF/RF columns.")
    df = pd.DataFrame(
        {
            MARKET_TICKER: (t.frame[cols["MKT-RF"]] + t.frame[cols["RF"]]) / 100.0,
            "RF": t.frame[cols["RF"]] / 100.0,
        }
    )
    df.index = daily_index(t.frame.index)
    return df


def market_caps(monthly_text: str) -> dict[str, float]:
    """Latest industry market capitalisation ($m): number of firms x average firm size."""
    tables = parse_tables(monthly_text)
    n = find_table(tables, "number of firms").frame
    size = find_table(tables, "average firm size").frame
    last = n.index.max()
    caps = n.loc[last] * size.loc[last]
    return {ticker_for(k): float(v) for k, v in caps.items() if np.isfinite(v) and v > 0}


def returns_to_prices(returns: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Total-return index levels; each series starts where its data starts."""
    growth = (1.0 + returns).cumprod()
    return base * growth


def assets(spec: KFDatasetSpec) -> tuple[AssetInfo, ...]:
    out = [
        AssetInfo(
            ticker=ticker_for(code),
            name=f"{name} (US industry portfolio)",
            asset_class=AssetClass.EQUITY,
            sector=name,
            description=f"Value-weighted portfolio of NYSE/AMEX/NASDAQ stocks in industry '{code}'.",
        )
        for code, name in spec.industries.items()
    ]
    out.append(
        AssetInfo(
            ticker=MARKET_TICKER,
            name="US equity market (Fama-French Mkt)",
            asset_class=AssetClass.INDEX,
            sector="Index",
            is_benchmark=True,
            description="Value-weighted return of all CRSP firms (Mkt-RF + RF).",
        )
    )
    return tuple(out)


def provenance(retrieved_at: dt.datetime | None) -> DataProvenance:
    return DataProvenance(
        source=SOURCE,
        is_synthetic=False,
        adjustment="Value-weighted total returns (dividends included), converted to index levels.",
        retrieved_at=retrieved_at,
        license_note=LICENSE_NOTE,
        notes=(
            "Industry portfolios, not individual securities: company-level ESG data does not apply.",
            "Source: Kenneth R. French Data Library, "
            "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
        ),
    )
