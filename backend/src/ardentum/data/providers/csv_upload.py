"""Parsing of user-uploaded CSV price and metadata files.

Accepted price layouts
----------------------
* **Wide**: a date column followed by one column of prices per ticker::

      date,AAA,BBB
      2024-01-02,101.2,55.1

* **Long**: columns ``date``, ``ticker`` and one of ``adj_close``, ``adjclose``,
  ``close`` or ``price``::

      date,ticker,adj_close
      2024-01-02,AAA,101.2

Dates must be ISO-8601 (``YYYY-MM-DD``) to avoid day/month ambiguity. Prices
should be total-return adjusted closes; the uploader asserts this and the
provenance records it. Nothing is inferred silently: malformed input is rejected
with the offending rows/columns named.

Metadata CSV (optional): ``ticker,name,sector,asset_class,currency,isin,market_cap,
esg_score,esg_source,esg_as_of``. ``currency`` (ISO 4217, default USD) is the currency
the prices are quoted in; ``isin`` lets open ESG data be matched to the asset;
``market_cap`` (in ``currency``) feeds Black-Litterman equilibrium priors.
"""

from __future__ import annotations

import datetime as dt
import io
import re

import numpy as np
import pandas as pd

from ardentum.data.models import AssetClass, AssetInfo, EsgRecord
from ardentum.quant.errors import InvalidInputError

MAX_BYTES = 5 * 1024 * 1024
MAX_TICKERS = 200
MAX_ROWS = 60_000
TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-_^=]{0,19}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def isin_is_valid(isin: str) -> bool:
    """ISO 6166 check: letters become 10..35, then the Luhn check over the digit string."""
    if not ISIN_RE.match(isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return total % 10 == 0


_PRICE_COLUMNS = ("adj_close", "adjclose", "adjusted_close", "close", "price")


def _read(content: bytes) -> pd.DataFrame:
    if len(content) > MAX_BYTES:
        raise InvalidInputError(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidInputError("File must be UTF-8 encoded CSV.") from exc
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InvalidInputError(f"Could not parse CSV: {exc}") from exc
    if df.empty:
        raise InvalidInputError("The CSV contains no data rows.")
    if len(df) > MAX_ROWS:
        raise InvalidInputError(f"The CSV has more than {MAX_ROWS:,} rows.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_dates(values: pd.Series) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(values.str.strip(), format="%Y-%m-%d", errors="coerce")
    bad = values[parsed.isna()]
    if not bad.empty:
        sample = ", ".join(repr(v) for v in bad.head(3))
        raise InvalidInputError(
            f"{len(bad)} date value(s) are not ISO-8601 YYYY-MM-DD (e.g. {sample})."
        )
    return pd.DatetimeIndex(parsed)


def _to_float(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.apply(lambda s: pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce"))
    # Cells that were non-empty but failed to parse are errors, not missing data.
    bad_mask = out.isna() & frame.notna() & (frame.apply(lambda s: s.str.strip()) != "")
    if bad_mask.to_numpy().any():
        col = str(bad_mask.any()[bad_mask.any()].index[0])
        raise InvalidInputError(f"Column {col!r} contains non-numeric price values.")
    return pd.DataFrame(out.astype(float))


def _check_tickers(tickers: list[str]) -> None:
    if len(tickers) > MAX_TICKERS:
        raise InvalidInputError(f"At most {MAX_TICKERS} tickers are supported per upload.")
    bad = [t for t in tickers if not TICKER_RE.match(t)]
    if bad:
        raise InvalidInputError(f"Invalid ticker symbol(s): {', '.join(bad[:5])}.")
    if len(set(tickers)) != len(tickers):
        raise InvalidInputError("Duplicate ticker columns.")


def parse_price_csv(content: bytes) -> pd.DataFrame:
    """Return a wide DataFrame of prices (dates x tickers) from an uploaded CSV."""
    df = _read(content)
    lower = {c.lower(): c for c in df.columns}
    date_col = lower.get("date") or df.columns[0]

    if "ticker" in lower:
        price_col = next((lower[c] for c in _PRICE_COLUMNS if c in lower), None)
        if price_col is None:
            raise InvalidInputError(
                "Long-format CSV needs a price column named one of: " + ", ".join(_PRICE_COLUMNS)
            )
        tick_col = lower["ticker"]
        long = pd.DataFrame(
            {
                "date": _parse_dates(df[date_col]),
                "ticker": df[tick_col].str.strip().str.upper(),
                "price": _to_float(df[[price_col]]).iloc[:, 0].to_numpy(),
            }
        )
        if long.duplicated(["date", "ticker"]).any():
            raise InvalidInputError("Duplicate (date, ticker) rows in the CSV.")
        wide = long.pivot(index="date", columns="ticker", values="price")  # noqa: PD010
    else:
        price_cols = [c for c in df.columns if c != date_col]
        if not price_cols:
            raise InvalidInputError(
                "Wide-format CSV needs at least one ticker column after the date."
            )
        wide = _to_float(df[price_cols])
        wide.index = _parse_dates(df[date_col])
        wide.columns = [c.strip().upper() for c in price_cols]
        if wide.index.has_duplicates:
            raise InvalidInputError("Duplicate dates in the CSV.")

    wide = wide.sort_index()
    wide.index.name = "date"
    wide.columns.name = None
    _check_tickers([str(c) for c in wide.columns])
    if (wide.to_numpy()[~np.isnan(wide.to_numpy())] <= 0).any():
        raise InvalidInputError("Prices must be strictly positive.")
    if len(wide) < 3:
        raise InvalidInputError("At least three dates of prices are required.")
    return wide


def parse_metadata_csv(content: bytes) -> list[AssetInfo]:
    """Parse optional asset metadata including user-supplied ESG scores."""
    df = _read(content)
    cols = {c.lower(): c for c in df.columns}
    if "ticker" not in cols:
        raise InvalidInputError("Metadata CSV needs a 'ticker' column.")
    out: list[AssetInfo] = []
    for i, row in df.iterrows():
        line = int(str(i)) + 2  # header is line 1
        ticker = str(row[cols["ticker"]]).strip().upper()
        _check_tickers([ticker])

        def get(name: str, row: pd.Series = row) -> str | None:
            c = cols.get(name)
            v = row[c] if c else None
            return None if v is None or pd.isna(v) or str(v).strip() == "" else str(v).strip()

        esg: EsgRecord | None = None
        score_s = get("esg_score")
        if score_s is not None:
            try:
                score = float(score_s)
            except ValueError as exc:
                raise InvalidInputError(
                    f"Line {line}: ESG score {score_s!r} is not a number."
                ) from exc
            if not 0.0 <= score <= 100.0:
                raise InvalidInputError(f"Line {line}: ESG score must be between 0 and 100.")
            source = get("esg_source")
            if source is None:
                raise InvalidInputError(
                    f"Line {line}: an ESG score needs an 'esg_source' naming its provider."
                )
            as_of_s = get("esg_as_of")
            try:
                as_of = dt.date.fromisoformat(as_of_s) if as_of_s else None
            except ValueError as exc:
                raise InvalidInputError(f"Line {line}: esg_as_of must be YYYY-MM-DD.") from exc
            esg = EsgRecord(score=score, source=source, as_of=as_of)
        ac_s = (get("asset_class") or "equity").lower()
        try:
            asset_class = AssetClass(ac_s)
        except ValueError as exc:
            raise InvalidInputError(
                f"Line {line}: asset_class must be one of {', '.join(a.value for a in AssetClass)}."
            ) from exc
        currency = (get("currency") or "USD").upper()
        if not CURRENCY_RE.match(currency):
            raise InvalidInputError(
                f"Line {line}: currency must be a three-letter ISO 4217 code such as USD or EUR."
            )
        isin = get("isin")
        if isin is not None:
            isin = isin.upper()
            if not isin_is_valid(isin):
                raise InvalidInputError(
                    f"Line {line}: {isin!r} is not a valid ISIN (12 characters with a check digit)."
                )
        cap_s = get("market_cap")
        market_cap: float | None = None
        if cap_s is not None:
            try:
                market_cap = float(cap_s)
            except ValueError as exc:
                raise InvalidInputError(
                    f"Line {line}: market_cap {cap_s!r} is not a number."
                ) from exc
            if not np.isfinite(market_cap) or market_cap <= 0:
                raise InvalidInputError(f"Line {line}: market_cap must be positive.")
        out.append(
            AssetInfo(
                ticker=ticker,
                name=get("name") or ticker,
                asset_class=asset_class,
                sector=get("sector"),
                currency=currency,
                esg=esg,
                isin=isin,
                market_cap=market_cap,
            )
        )
    tickers = [a.ticker for a in out]
    if len(set(tickers)) != len(tickers):
        raise InvalidInputError("Duplicate tickers in metadata CSV.")
    return out
