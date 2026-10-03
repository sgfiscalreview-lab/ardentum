"""Crisis replay: a fixed portfolio held through a historical period.

The portfolio is bought at the close of the period's first day and then held without
trading (buy and hold), so each holding's weight drifts with its price. With ``w_i`` the
starting weights and ``G_{i,t} = prod_{s<=t} (1 + r_{i,s})`` each asset's growth since the
start, the portfolio's value is ``V_t = sum_i w_i G_{i,t}`` (``V_0 = 1``). Then

* total return ``V_T - 1`` splits exactly into contributions ``w_i (G_{i,T} - 1)``;
* the maximum drawdown is ``min_t (V_t / max_{s<=t} V_s - 1)`` inside the period;
* recovery is the first date after the period's low, using all later data and still
  without trading, on which ``V_t`` is back at the high reached before that low.

Only returns dated after the start are used (the start is the close the portfolio is
bought at), so nothing before the purchase affects the result.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.frequency import Frequency, infer_frequency

MAX_START_GAP_DAYS = 7  # the purchase close may precede the start by a weekend or holiday


class PeriodNotCoveredError(InsufficientDataError):
    """The data does not cover the requested period; the message says why."""


@dataclass(frozen=True)
class ReplayResult:
    dates: pd.DatetimeIndex  # purchase date followed by every date in the period
    value: np.ndarray  # V_t on ``dates`` (starts at 1.0)
    period_returns: np.ndarray  # the portfolio's return on each date after the purchase
    total_return: float
    max_drawdown: float  # negative fraction; 0 when the value never fell
    trough_date: dt.date | None  # the period's low (None when the value never fell)
    worst_period_return: float
    worst_period_date: dt.date
    asset_returns: np.ndarray  # G_{i,T} - 1
    contributions: np.ndarray  # w_i (G_{i,T} - 1); sums to ``total_return``
    recovery_date: dt.date | None  # None: not back at the prior high by ``data_end``
    data_end: dt.date

    @property
    def recovery_days(self) -> int | None:
        """Calendar days from the period's low back to the high before it."""
        if self.recovery_date is None or self.trough_date is None:
            return None
        return (self.recovery_date - self.trough_date).days


def require_daily(returns: pd.DataFrame) -> None:
    """Crisis replay needs daily prices: many crises last only weeks."""
    freq = infer_frequency(pd.DatetimeIndex(returns.index))
    if freq is not Frequency.DAILY:
        raise InvalidInputError(
            f"Crisis replay needs daily prices; this data has {freq.value} prices. "
            "Use a dataset with daily prices."
        )


def replay(
    returns: pd.DataFrame, weights: np.ndarray, start: dt.date, end: dt.date
) -> ReplayResult:
    """Hold ``weights`` (bought at the close on or just before ``start``) through ``end``.

    ``returns`` are simple daily returns, one column per weight, sorted by date, with no
    missing values. Raises :class:`PeriodNotCoveredError` when the data does not span
    the period.
    """
    w = np.asarray(weights, dtype=float)
    if returns.shape[1] != w.shape[0]:
        raise InvalidInputError("Number of weights must match the number of return columns.")
    if start >= end:
        raise InvalidInputError("The period must start before it ends.")
    if returns.empty:
        raise PeriodNotCoveredError("No returns to replay.")
    r = returns.to_numpy(dtype=float)
    if not np.isfinite(r).all():
        raise InvalidInputError("Returns contain missing or non-finite values.")
    idx = pd.DatetimeIndex(returns.index)
    first, last = idx[0].date(), idx[-1].date()

    # Purchase: the last close on or before the start.
    buy = int(idx.searchsorted(pd.Timestamp(start), side="right")) - 1
    if buy < 0:
        raise PeriodNotCoveredError(
            f"The data begins after this period started ({start.isoformat()}); the earliest "
            f"date a portfolio can be bought is {first.isoformat()}."
        )
    if last < end:
        raise PeriodNotCoveredError(
            f"The data ends {last.isoformat()}, before this period ended ({end.isoformat()})."
        )
    if (start - idx[buy].date()).days > MAX_START_GAP_DAYS:
        raise PeriodNotCoveredError(
            f"The data has no prices in the week before {start.isoformat()}."
        )
    stop = int(idx.searchsorted(pd.Timestamp(end), side="right"))  # dates in (buy, end]
    m = stop - (buy + 1)
    if m < 1:
        raise PeriodNotCoveredError("The data has no prices inside this period.")

    growth = np.cumprod(1.0 + r[buy + 1 :], axis=0)  # from the purchase to the data's end
    value_all = np.concatenate(([1.0], growth @ w))
    if (value_all[: m + 1] <= 0).any():
        raise InvalidInputError(
            "The portfolio's value falls to zero or below in this period (short positions "
            "lose more than the capital). Crisis replay needs a portfolio that stays solvent."
        )
    value = value_all[: m + 1]
    period_returns = value[1:] / value[:-1] - 1.0
    dates = idx[buy:stop]

    running_max = np.maximum.accumulate(value)
    dd = value / running_max - 1.0
    trough = int(np.argmin(dd))
    max_dd = float(dd[trough])
    trough_date: dt.date | None = None
    recovery_date: dt.date | None = None
    if max_dd < 0.0:
        trough_date = dates[trough].date()
        prior_high = float(running_max[trough])
        later = np.nonzero(value_all[trough + 1 :] >= prior_high)[0]
        if later.size:
            recovery_date = idx[buy + trough + 1 + int(later[0])].date()

    worst = int(np.argmin(period_returns))
    asset_returns = growth[m - 1] - 1.0
    return ReplayResult(
        dates=dates,
        value=value,
        period_returns=period_returns,
        total_return=float(value[-1] - 1.0),
        max_drawdown=max_dd,
        trough_date=trough_date,
        worst_period_return=float(period_returns[worst]),
        worst_period_date=dates[worst + 1].date(),
        asset_returns=asset_returns,
        contributions=w * asset_returns,
        recovery_date=recovery_date,
        data_end=last,
    )


def period_return(returns: pd.Series, start: dt.date, end: dt.date) -> float:
    """Compounded return of one series from the close on or before ``start`` to ``end``."""
    res = replay(returns.to_frame(), np.array([1.0]), start, end)
    return res.total_return
