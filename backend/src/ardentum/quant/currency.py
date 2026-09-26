"""Currency conversion of price histories (unhedged).

An asset priced in local currency L is expressed in base currency B by
``P_B(t) = P_L(t) * X(t)``, where ``X(t)`` is the number of units of B per unit of
L. Returns then satisfy ``1 + r_B = (1 + r_L)(1 + r_X)``: the base-currency
investor bears the asset's return and the currency's return (no hedging).

Rates are aligned to the price dates by carrying the last published rate
forward for at most ``max_fill`` observations (central banks do not publish on
their holidays); longer gaps, or prices before the first available rate, are
errors rather than guesses.
"""

from __future__ import annotations

import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError

MAX_FX_FILL = 5


def align_rates(
    rates: pd.Series, dates: pd.DatetimeIndex, max_fill: int = MAX_FX_FILL
) -> pd.Series:
    """Rates on ``dates`` using the latest rate published on or before each date."""
    if rates.empty:
        raise InsufficientDataError("No exchange rates are available for this period.")
    if (rates <= 0).any():
        raise InvalidInputError("Exchange rates must be positive.")
    rates = rates.sort_index()
    union = rates.index.union(dates)
    filled = rates.reindex(union).ffill(limit=max_fill)
    out = filled.reindex(dates)
    if out.isna().any():
        first_bad = out.index[out.isna()][0].date()
        raise InsufficientDataError(
            f"No exchange rate within {max_fill} days of {first_bad}; the FX source does not "
            "cover the whole price history. Shorten the window or use the local currency."
        )
    return out


def convert_prices(prices: pd.Series, rates: pd.Series, max_fill: int = MAX_FX_FILL) -> pd.Series:
    """Local-currency prices converted to the base currency (``rates`` = base per local)."""
    valid = prices.dropna()
    x = align_rates(rates, pd.DatetimeIndex(valid.index), max_fill)
    return (valid * x).reindex(prices.index)
