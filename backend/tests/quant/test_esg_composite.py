"""Composite ESG scores: closed forms, missing components and input checks."""

from __future__ import annotations

import numpy as np
import pytest

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.esg import composite_scores


def test_weighted_average_with_normalised_weights() -> None:
    s = np.array([[80.0, 20.0, 50.0], [0.0, 100.0, 100.0]])
    out = composite_scores(s, np.array([2.0, 1.0, 1.0]))
    assert out == pytest.approx([(2 * 80 + 20 + 50) / 4, (0 + 100 + 100) / 4])
    # Scaling all weights does not change the result.
    assert composite_scores(s, np.array([20.0, 10.0, 10.0])) == pytest.approx(out)
    # Equal weights give the plain mean.
    assert composite_scores(s, np.ones(3)) == pytest.approx(s.mean(axis=1))


def test_missing_component_is_never_filled_in() -> None:
    s = np.array([[80.0, np.nan], [60.0, 40.0], [np.nan, np.nan]])
    out = composite_scores(s, np.array([1.0, 1.0]))
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(50.0)
    assert np.isnan(out[2])


def test_bounds_and_monotonicity() -> None:
    rng = np.random.default_rng(3)
    s = rng.uniform(0, 100, size=(200, 4))
    w = rng.uniform(0.1, 5, size=4)
    out = composite_scores(s, w)
    assert (out >= s.min(axis=1) - 1e-12).all()
    assert (out <= s.max(axis=1) + 1e-12).all()
    better = s.copy()
    better[:, 2] = np.minimum(100.0, better[:, 2] + 10)
    assert (composite_scores(better, w) >= out - 1e-12).all()


@pytest.mark.parametrize(
    ("scores", "weights"),
    [
        (np.array([[50.0, 50.0]]), np.array([1.0, 0.0])),
        (np.array([[50.0, 50.0]]), np.array([1.0, -1.0])),
        (np.array([[50.0, 150.0]]), np.array([1.0, 1.0])),
        (np.array([[50.0, 50.0]]), np.array([1.0])),
    ],
)
def test_input_checks(scores: np.ndarray, weights: np.ndarray) -> None:
    with pytest.raises(InvalidInputError):
        composite_scores(scores, weights)
