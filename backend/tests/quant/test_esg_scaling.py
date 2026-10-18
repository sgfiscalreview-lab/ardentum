"""Transforms from raw open-data ESG metrics to 0-100 scores."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import rankdata

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.esg import percentile_scores, scale_linear, yearly_scores


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


def test_yearly_scores_score_each_year_on_its_own() -> None:
    values = {2022: {"A": 1000.0}, 2023: {"A": 800.0, "B": 400.0}}
    # A fixed scale scores value by value, whatever else was reported that year.
    linear = yearly_scores(values, "linear", higher_is_better=False, lower=0.0, upper=2000.0)
    assert linear == {2022: {"A": 50.0}, 2023: {"A": 60.0, "B": 80.0}}
    # Percentile ranks compare a year's values only; one value alone has no rank.
    ranks = yearly_scores(values, "percentile", higher_is_better=False)
    assert ranks == {2023: {"A": 0.0, "B": 100.0}}
    with pytest.raises(InvalidInputError, match="lower and an upper"):
        yearly_scores(values, "linear")
