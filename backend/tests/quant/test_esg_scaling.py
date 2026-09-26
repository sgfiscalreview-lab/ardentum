"""Transforms from raw open-data ESG metrics to 0-100 scores."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import rankdata

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.esg import percentile_scores, scale_linear


def test_scale_linear_known_values_and_direction() -> None:
    x = np.array([0.0, 2.5, 5.0, 10.0, 12.0, -1.0])
    np.testing.assert_allclose(scale_linear(x, 0, 10), [0, 25, 50, 100, 100, 0])
    np.testing.assert_allclose(
        scale_linear(x, 0, 10, higher_is_better=False), [100, 75, 50, 0, 0, 100]
    )
    with pytest.raises(InvalidInputError, match="lower bound"):
        scale_linear(x, 5, 5)
    with pytest.raises(InvalidInputError, match="finite"):
        scale_linear(np.array([np.nan]), 0, 1)


def test_percentile_scores_match_scipy_average_ranks() -> None:
    rng = np.random.default_rng(1)
    x = np.round(rng.normal(size=25), 1)  # rounding creates ties
    expected = 100 * (rankdata(x, method="average") - 1) / (x.size - 1)
    np.testing.assert_allclose(percentile_scores(x), expected)
    np.testing.assert_allclose(percentile_scores(x, higher_is_better=False), 100 - expected)
    np.testing.assert_allclose(percentile_scores(np.array([3.0, 1.0, 2.0])), [100, 0, 50])
    with pytest.raises(InvalidInputError, match="at least two"):
        percentile_scores(np.array([1.0]))
