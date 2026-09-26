"""Data-quality checks and alignment of price histories.

Rules (see DECISIONS.md D-011):
* Duplicate dates, non-positive or non-numeric prices are errors.
* Each asset's history starts at its first valid price. The aligned panel starts
  at the latest first-valid date across the selected assets, so no asset's
  pre-listing period is fabricated. The report states how much history was lost.
* Inside the common window, gaps of up to ``MAX_FILL`` consecutive missing prices
  (typically holiday-calendar mismatches) are forward-filled, which yields zero
  returns on those days; the number of filled points is reported. Longer gaps are
  errors because filling them would understate volatility.
* Daily absolute returns above 50% and runs of 10+ identical prices are flagged
  as warnings (possible bad ticks, stale quotes or unadjusted corporate actions).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ardentum.quant.errors import InsufficientDataError, InvalidInputError

MAX_FILL = 3
EXTREME_RETURN = 0.5
STALE_RUN = 10


@dataclass
class QualityReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _longest_nan_run(s: pd.Series) -> int:
    isna = s.isna().to_numpy()
    best = run = 0
    for v in isna:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def _longest_constant_run(s: pd.Series) -> int:
    v = s.dropna().to_numpy()
    if v.size == 0:
        return 0
    best = run = 1
    for a, b in itertools.pairwise(v):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


def align_prices(
    prices: pd.DataFrame, *, min_observations: int = 2
) -> tuple[pd.DataFrame, QualityReport]:
    """Validate and align a wide price panel; raise on errors, report the rest."""
    report = QualityReport()
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise InvalidInputError("Prices must be indexed by dates.")
    if prices.index.has_duplicates:
        dups = prices.index[prices.index.duplicated()].unique()
        raise InvalidInputError(
            f"Duplicate dates in price data: {', '.join(d.date().isoformat() for d in dups[:5])}."
        )
    if prices.columns.has_duplicates:
        raise InvalidInputError("Duplicate tickers in price data.")
    if prices.shape[1] == 0:
        raise InvalidInputError("No assets selected.")
    df = prices.sort_index().apply(pd.to_numeric, errors="coerce").astype(float)
    values = df.to_numpy()
    if np.isinf(values).any():
        raise InvalidInputError("Price data contains infinite values.")
    bad = [str(c) for c in df.columns if (df[c].dropna() <= 0).any()]
    if bad:
        raise InvalidInputError(f"Non-positive prices for: {', '.join(bad)}.")
    empty = [str(c) for c in df.columns if df[c].notna().sum() == 0]
    if empty:
        raise InvalidInputError(f"No price data for: {', '.join(empty)}.")

    first_valid = {str(c): df[c].first_valid_index() for c in df.columns}
    last_valid = {str(c): df[c].last_valid_index() for c in df.columns}
    start = max(first_valid.values())
    end = min(last_valid.values())
    if start >= end:
        raise InsufficientDataError("The selected assets have no overlapping price history.")
    latest = max(first_valid, key=lambda t: first_valid[t])
    if start > df.index[0]:
        report.notes.append(
            f"Common history starts {start.date()} because {latest} has no earlier prices; "
            f"{int((df.index < start).sum())} earlier dates are not used."
        )
    earliest_end = min(last_valid, key=lambda t: last_valid[t])
    if end < df.index[-1]:
        report.notes.append(
            f"Common history ends {end.date()} because {earliest_end} has no later prices."
        )
    window = df.loc[start:end]

    for c in window.columns:
        run = _longest_nan_run(window[c])
        if run > MAX_FILL:
            report.errors.append(
                f"{c} has a gap of {run} consecutive missing prices inside the common window "
                f"(maximum fillable gap is {MAX_FILL})."
            )
    if report.errors:
        raise InvalidInputError(" ".join(report.errors))

    n_missing = int(window.isna().sum().sum())
    filled = window.ffill(limit=MAX_FILL)
    if n_missing:
        report.notes.append(
            f"{n_missing} missing prices (holiday-calendar gaps of at most {MAX_FILL} days) were "
            "carried forward, producing zero returns on those dates."
        )

    rets = filled / filled.shift(1) - 1.0
    for c in filled.columns:
        extreme = rets[c].abs() > EXTREME_RETURN
        if extreme.any():
            dates = ", ".join(d.date().isoformat() for d in rets.index[extreme][:3])
            report.warnings.append(
                f"{c}: {int(extreme.sum())} daily move(s) above {EXTREME_RETURN:.0%} ({dates}); "
                "check for bad ticks or unadjusted splits."
            )
        stale = _longest_constant_run(filled[c])
        if stale >= STALE_RUN:
            report.warnings.append(
                f"{c}: price unchanged for {stale} consecutive observations (stale data?)."
            )

    if len(filled) < min_observations:
        raise InsufficientDataError(
            f"Only {len(filled)} aligned observations; at least {min_observations} are required."
        )
    return filled, report
