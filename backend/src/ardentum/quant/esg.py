"""ESG scoring utilities used by portfolio construction.

ESG scores are *third-party opinions*, not observed quantities. Providers
disagree substantially (Berg, Koelbel & Rigobon 2022, "Aggregate Confusion: The
Divergence of ESG Ratings", Review of Finance, report correlations of ~0.38-0.71
between major raters). Ardentum therefore treats a score as an input with
explicit provenance and never fabricates one: assets without a score must be
excluded or scored by the user before any ESG constraint or tilt is applied.

Scale: scores are on a 0-100 scale where higher is better. Providers using other
scales (e.g. Sustainalytics risk scores, where lower is better) must be converted
by the data layer before reaching this module.

Portfolio score: the value-weighted average ``s' w`` of constituent scores. With
long-only weights summing to one this is a convex combination, so a minimum
portfolio score is a single linear constraint ``s' w >= s_min``.

ESG preference ("tilt"): an ESG-adjusted expected return
``mu_i + tau * z_i`` where ``z_i`` is the cross-sectionally standardised score
and ``tau`` is the annual return the investor is willing to trade for a
one-standard-deviation better score. This follows the ESG-adjusted-return
formulation of Pedersen, Fitzgibbons & Pomorski (2021), "Responsible investing:
The ESG-efficient frontier", JFE 142(2). The adjustment only affects the
*optimisation objective*; all reported expected returns remain unadjusted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from ardentum.quant.errors import InvalidInputError

ESG_SCORE_MIN = 0.0
ESG_SCORE_MAX = 100.0


def score_vector(
    tickers: Sequence[str], scores: Mapping[str, float | None], *, purpose: str
) -> np.ndarray:
    """Return scores aligned to ``tickers``; raise listing any missing/invalid ones."""
    missing = [t for t in tickers if scores.get(t) is None]
    if missing:
        raise InvalidInputError(
            f"{purpose} requires an ESG score for every investable asset. Missing: "
            f"{', '.join(missing)}. Exclude these assets or supply scores."
        )
    s = np.array([float(scores[t]) for t in tickers])  # type: ignore[arg-type]
    if not np.isfinite(s).all() or (s < ESG_SCORE_MIN).any() or (s > ESG_SCORE_MAX).any():
        raise InvalidInputError("ESG scores must be finite numbers between 0 and 100.")
    return s


def standardise_scores(scores: np.ndarray) -> np.ndarray:
    """Cross-sectional z-scores (population standard deviation); zeros if all equal."""
    s = np.asarray(scores, dtype=float)
    sd = s.std(ddof=0)
    if sd == 0.0:
        return np.zeros_like(s)
    return (s - s.mean()) / sd


def esg_adjusted_returns(
    expected_returns: np.ndarray, scores: np.ndarray, tilt: float
) -> np.ndarray:
    """``mu + tilt * z(scores)``; ``tilt`` is an annual return per 1 SD of score."""
    if tilt < 0.0:
        raise InvalidInputError("ESG tilt must be non-negative.")
    return np.asarray(expected_returns, dtype=float) + tilt * standardise_scores(scores)


def portfolio_esg_score(weights: np.ndarray, scores: np.ndarray) -> float:
    """Value-weighted average ESG score of a fully invested portfolio."""
    w = np.asarray(weights, dtype=float)
    s = np.asarray(scores, dtype=float)
    if w.shape != s.shape:
        raise InvalidInputError("Weights and ESG scores must have the same length.")
    if (w < -1e-9).any():
        # With short positions s'w is not a convex combination of scores and has
        # no accepted interpretation, so it is not reported.
        raise InvalidInputError("A portfolio ESG score is only defined for long-only portfolios.")
    return float(w @ s)


# --------------------------------------------------------------------------- raw metrics -> 0-100


def scale_linear(
    values: np.ndarray, lower: float, upper: float, higher_is_better: bool = True
) -> np.ndarray:
    """Map raw metric values onto 0-100: ``100 (x - lower) / (upper - lower)``, clipped.

    With ``higher_is_better=False`` (e.g. emissions) the scale is reversed. Values
    outside ``[lower, upper]`` are clipped to the end points.
    """
    x = np.asarray(values, dtype=float)
    if not np.isfinite(x).all():
        raise InvalidInputError("Metric values must be finite numbers.")
    if not (np.isfinite(lower) and np.isfinite(upper)) or upper <= lower:
        raise InvalidInputError("The scale needs a lower bound strictly below the upper bound.")
    s = np.clip((x - lower) / (upper - lower), 0.0, 1.0) * 100.0
    return s if higher_is_better else 100.0 - s


def percentile_scores(values: np.ndarray, higher_is_better: bool = True) -> np.ndarray:
    """Percentile rank within the group on 0-100: ``100 (rank - 1) / (n - 1)``.

    Ranks start at 1; ties receive their average rank. The best value scores 100 and the
    worst 0. Relative scores say nothing about absolute performance and change when
    the group changes. At least two values are required.
    """
    x = np.asarray(values, dtype=float)
    if x.size < 2:
        raise InvalidInputError(
            "Percentile scores need at least two companies with values; use a fixed scale."
        )
    if not np.isfinite(x).all():
        raise InvalidInputError("Metric values must be finite numbers.")
    key = x if higher_is_better else -x
    order = np.argsort(key, kind="mergesort")
    ranks = np.empty(x.size)
    ranks[order] = np.arange(1, x.size + 1, dtype=float)
    for v in np.unique(key):  # average ranks of ties
        tie = key == v
        if tie.sum() > 1:
            ranks[tie] = ranks[tie].mean()
    return 100.0 * (ranks - 1.0) / (x.size - 1.0)
