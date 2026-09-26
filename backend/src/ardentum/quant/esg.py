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
