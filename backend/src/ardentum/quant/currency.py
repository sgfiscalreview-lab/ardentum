"""Currency conversion of price histories, unhedged or currency-hedged.

An asset priced in local currency L is expressed in base currency B by
``P_B(t) = P_L(t) * X(t)``, where ``X(t)`` is the number of units of B per unit of
L. Returns then satisfy ``1 + r_B = (1 + r_L)(1 + r_X)``: the base-currency
investor bears the asset's return and the currency's return (no hedging).

Rates are aligned to the price dates by carrying the last published rate
forward for at most ``max_fill`` observations (central banks do not publish on
their holidays); longer gaps, or prices before the first available rate, are
errors rather than guesses.

Hedged: each period the investor sells forward the position's start-of-period value
(a hedge re-set on every price date). With the forward priced by covered interest
parity, ``F = X(t-1) (1 + i_B d) / (1 + i_L d)`` for a period of ``d`` years and
short rates ``i_B`` (base) and ``i_L`` (local) known at ``t-1``, the base-currency
return is

    r_H = r_L (1 + r_X) + (1 + i_B d) / (1 + i_L d) - 1 .

The asset's local return is kept; only the period's gain stays exposed to the
exchange rate (the ``r_L r_X`` term), and the interest-rate differential is the cost
(or income) of hedging. Nothing from after ``t-1`` enters the hedge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError

MAX_FX_FILL = 5
MAX_RATE_FILL = 10  # policy-rate series skip weekends and holidays; rates change rarely
DAYS_PER_YEAR = 365.0


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


def align_interest_rates(
    rates: pd.Series, dates: pd.DatetimeIndex, max_fill: int = MAX_RATE_FILL
) -> pd.Series:
    """Annual short rates (decimals, may be zero or negative) on ``dates``, using the latest
    published on or before each date."""
    if rates.empty:
        raise InsufficientDataError("No interest rates are available for this period.")
    if not np.isfinite(rates.to_numpy(dtype=float)).all() or (rates <= -1.0).any():
        raise InvalidInputError("Interest rates must be finite decimals above -100%.")
    rates = rates.sort_index()
    union = rates.index.union(dates)
    out = rates.reindex(union).ffill(limit=max_fill).reindex(dates)
    if out.isna().any():
        first_bad = out.index[out.isna()][0].date()
        raise InsufficientDataError(
            f"No interest rate within {max_fill} days of {first_bad}; the rate source does not "
            "cover the whole price history. Shorten the window or use unhedged returns."
        )
    return out


def hedged_returns(
    local_returns: pd.Series,
    fx_returns: pd.Series,
    base_rate: pd.Series,
    local_rate: pd.Series,
) -> pd.Series:
    """Per-period base-currency returns of a position hedged by a one-period forward.

    ``base_rate`` and ``local_rate`` are the annual rates at the *start* of each period
    (index aligned with the returns); the period length is taken from the dates.
    """
    idx = local_returns.index
    for other in (fx_returns, base_rate, local_rate):
        if not other.index.equals(idx):
            raise InvalidInputError("Returns and rates must share the same dates.")
    if not isinstance(idx, pd.DatetimeIndex):
        raise InvalidInputError("Hedged returns need dated observations.")
    years = pd.Series(idx, index=idx).diff().dt.days.to_numpy(dtype=float) / DAYS_PER_YEAR
    grow_b = 1.0 + base_rate.to_numpy(dtype=float) * years
    grow_l = 1.0 + local_rate.to_numpy(dtype=float) * years
    if (grow_l[1:] <= 0).any():
        raise InvalidInputError("The local interest rate implies a non-positive forward.")
    carry = grow_b / grow_l - 1.0
    r_l = local_returns.to_numpy(dtype=float)
    r_x = fx_returns.to_numpy(dtype=float)
    return pd.Series(r_l * (1.0 + r_x) + carry, index=idx)


def convert_prices_hedged(
    prices: pd.Series,
    fx_rates: pd.Series,
    base_rates: pd.Series,
    local_rates: pd.Series,
    max_fx_fill: int = MAX_FX_FILL,
    max_rate_fill: int = MAX_RATE_FILL,
) -> pd.Series:
    """Local-currency prices as a base-currency, currency-hedged value index.

    ``fx_rates`` are units of base per unit of local; ``base_rates``/``local_rates`` annual
    short rates as decimals. The index starts at the unhedged converted first price, so
    hedged and unhedged series are directly comparable.
    """
    valid = prices.dropna()
    dates = pd.DatetimeIndex(valid.index)
    x = align_rates(fx_rates, dates, max_fx_fill)
    i_b = align_interest_rates(base_rates, dates, max_rate_fill)
    i_l = align_interest_rates(local_rates, dates, max_rate_fill)
    # The hedge for (t-1, t] is priced with the rates known at t-1.
    r_h = hedged_returns(valid.pct_change(), x.pct_change(), i_b.shift(1), i_l.shift(1)).iloc[1:]
    start = float(valid.iloc[0]) * float(x.iloc[0])
    path = start * np.concatenate([[1.0], np.cumprod(1.0 + r_h.to_numpy())])
    return pd.Series(path, index=valid.index).reindex(prices.index)
