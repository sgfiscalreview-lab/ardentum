"""Return calculations.

Conventions
-----------
* Prices are indexed by a strictly increasing ``DatetimeIndex``; columns are asset
  identifiers. Prices should be total-return adjusted closes (splits and dividends
  reinvested) so that price returns equal total returns.
* Simple (arithmetic) return: ``r_t = P_t / P_{t-1} - 1``.
* Log (continuously compounded) return: ``x_t = ln(P_t / P_{t-1}) = ln(1 + r_t)``.
* The first observation has no return and is dropped; it is never filled with zero,
  because a fabricated zero return would bias means and volatilities downwards.
* Missing prices are not interpolated here. Alignment and gap handling are the
  responsibility of the data layer (``ardentum.data.validation``); this module
  rejects NaNs explicitly instead of guessing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError


def validate_prices(prices: pd.DataFrame | pd.Series) -> None:
    """Raise ``InvalidInputError`` unless prices are finite, positive and time-ordered."""
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise InvalidInputError("Prices must be indexed by dates (DatetimeIndex).")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise InvalidInputError("Price dates must be strictly increasing with no duplicates.")
    values = prices.to_numpy(dtype=float)
    if np.isnan(values).any():
        raise InvalidInputError(
            "Prices contain missing values. Align or clean the data before computing returns."
        )
    if not np.isfinite(values).all():
        raise InvalidInputError("Prices contain infinite values.")
    if (values <= 0).any():
        raise InvalidInputError("Prices must be strictly positive.")
    if len(prices) < 2:
        raise InsufficientDataError("At least two prices are required to compute a return.")


def simple_returns[T: (pd.DataFrame, pd.Series)](prices: T) -> T:
    """Arithmetic returns ``P_t / P_{t-1} - 1``; the first date is dropped."""
    validate_prices(prices)
    return (prices / prices.shift(1) - 1.0).iloc[1:]


def log_returns[T: (pd.DataFrame, pd.Series)](prices: T) -> T:
    """Continuously compounded returns ``ln(P_t / P_{t-1})``; the first date is dropped."""
    validate_prices(prices)
    ratio = prices / prices.shift(1)
    return ratio.iloc[1:].apply(np.log)


def simple_to_log[T: (pd.DataFrame, pd.Series, np.ndarray)](returns: T) -> T:
    """Convert simple returns to log returns: ``ln(1 + r)``. Requires ``r > -1``."""
    arr = np.asarray(returns, dtype=float)
    if (arr <= -1.0).any():
        raise InvalidInputError("Simple returns must exceed -100% to convert to log returns.")
    return np.log1p(returns)  # type: ignore[return-value,no-any-return]


def log_to_simple[T: (pd.DataFrame, pd.Series, np.ndarray)](returns: T) -> T:
    """Convert log returns to simple returns: ``exp(x) - 1``."""
    return np.expm1(returns)  # type: ignore[return-value,no-any-return]


def validate_returns(returns: np.ndarray, *, min_obs: int = 2, name: str = "returns") -> None:
    """Raise unless ``returns`` is finite, > -100% and has at least ``min_obs`` rows."""
    if returns.shape[0] < min_obs:
        raise InsufficientDataError(
            f"{name} has {returns.shape[0]} observations; at least {min_obs} are required."
        )
    if not np.isfinite(returns).all():
        raise InvalidInputError(f"{name} contains missing or infinite values.")
    if (returns < -1.0).any():
        raise InvalidInputError(f"{name} contains a return below -100%, which is impossible.")


def wealth_index(returns: pd.Series | np.ndarray, initial: float = 1.0) -> np.ndarray:
    """Cumulative wealth ``W_t = W_0 * prod_{s<=t}(1 + r_s)``, with ``W_0`` prepended.

    The returned array has ``len(returns) + 1`` elements; element 0 is ``initial``.
    Prepending the starting value is essential for drawdowns: a loss in the first
    period is a drawdown from the initial investment.
    """
    r = np.asarray(returns, dtype=float)
    validate_returns(r, min_obs=1)
    return initial * np.concatenate(([1.0], np.cumprod(1.0 + r)))


def total_return(returns: pd.Series | np.ndarray) -> float:
    """Compounded total return over the whole sample: ``prod(1 + r) - 1``."""
    r = np.asarray(returns, dtype=float)
    validate_returns(r, min_obs=1)
    return float(np.prod(1.0 + r) - 1.0)


def annualised_return(
    returns: pd.Series | np.ndarray,
    periods_per_year: int,
    *,
    method: str = "geometric",
) -> float:
    """Annualised return.

    ``method="geometric"`` (default) is the compound annual growth rate implied by
    the realised path: ``(prod(1 + r))^(P / n) - 1`` where ``P`` is periods per year
    and ``n`` the number of return observations. This is the CAGR.

    ``method="arithmetic"`` is ``P * mean(r)``: the annualised expected one-period
    return used by mean-variance optimisation. It exceeds the geometric rate by
    roughly ``sigma^2 / 2`` (volatility drag).
    """
    r = np.asarray(returns, dtype=float)
    validate_returns(r, min_obs=1)
    if method == "arithmetic":
        return float(periods_per_year * r.mean())
    if method == "geometric":
        growth = float(np.prod(1.0 + r))
        if growth <= 0.0:
            return -1.0  # total loss: CAGR is -100%
        return float(growth ** (periods_per_year / r.shape[0]) - 1.0)
    raise InvalidInputError(f"Unknown annualisation method {method!r}.")


def cagr(returns: pd.Series | np.ndarray, periods_per_year: int) -> float:
    """Compound annual growth rate. Alias for geometric ``annualised_return``."""
    return annualised_return(returns, periods_per_year, method="geometric")


def annual_rate_to_periodic(annual_rate: float, periods_per_year: int) -> float:
    """Convert an effective annual rate to the equivalent per-period compounded rate.

    ``(1 + R)^(1/P) - 1``; e.g. a 5% annual risk-free rate is ~0.01936% per trading day.
    """
    if annual_rate <= -1.0:
        raise InvalidInputError("Annual rate must exceed -100%.")
    return float((1.0 + annual_rate) ** (1.0 / periods_per_year) - 1.0)
