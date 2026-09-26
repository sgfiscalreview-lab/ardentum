import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ardentum.quant.errors import InvalidInputError
from ardentum.quant.portfolio import (
    buy_and_hold_returns,
    constant_mix_returns,
    diversification_ratio,
    effective_number_of_assets,
    portfolio_expected_return,
    portfolio_volatility,
    risk_decomposition,
    validate_covariance,
    validate_weights,
)


def _two_asset_cov() -> np.ndarray:
    vol = np.array([0.2, 0.1])
    corr = np.array([[1.0, 0.5], [0.5, 1.0]])
    return np.outer(vol, vol) * corr


def test_two_asset_volatility_known_value() -> None:
    # 0.25*0.04 + 0.25*0.01 + 2*0.25*0.5*0.2*0.1 = 0.0175
    assert portfolio_volatility(np.array([0.5, 0.5]), _two_asset_cov()) == pytest.approx(
        np.sqrt(0.0175)
    )


def test_expected_return() -> None:
    assert portfolio_expected_return(np.array([0.25, 0.75]), np.array([0.08, 0.04])) == (
        pytest.approx(0.05)
    )


def test_risk_contributions_sum_to_volatility() -> None:
    d = risk_decomposition(np.array([0.5, 0.5]), _two_asset_cov())
    assert d.risk_contribution.sum() == pytest.approx(d.volatility)
    assert d.percent_contribution.sum() == pytest.approx(1.0)
    # Asset 1: w (S w)_1 / vol = 0.5 * (0.02 + 0.005) / vol
    assert d.risk_contribution[0] == pytest.approx(0.5 * 0.025 / np.sqrt(0.0175))


@st.composite
def _psd_and_weights(draw: st.DrawFn) -> tuple[np.ndarray, np.ndarray]:
    n = draw(st.integers(min_value=2, max_value=8))
    seed = draw(st.integers(min_value=0, max_value=10_000))
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(n, n))
    cov = a @ a.T / n + 1e-4 * np.eye(n)
    w = rng.dirichlet(np.ones(n))
    return cov, w


@settings(max_examples=60, deadline=None)
@given(_psd_and_weights())
def test_euler_decomposition_property(data: tuple[np.ndarray, np.ndarray]) -> None:
    cov, w = data
    d = risk_decomposition(w, cov)
    assert d.risk_contribution.sum() == pytest.approx(d.volatility, rel=1e-10)
    # Numerical gradient check of the marginal contribution.
    eps = 1e-7
    for i in range(len(w)):
        bump = np.zeros_like(w)
        bump[i] = eps
        grad = (portfolio_volatility(w + bump, cov) - portfolio_volatility(w - bump, cov)) / (
            2 * eps
        )
        assert d.marginal_contribution[i] == pytest.approx(grad, rel=1e-5, abs=1e-8)
    assert diversification_ratio(w, cov) >= 1.0 - 1e-12


def test_effective_number_of_assets() -> None:
    assert effective_number_of_assets(np.full(4, 0.25)) == pytest.approx(4.0)
    assert effective_number_of_assets(np.array([1.0, 0.0])) == pytest.approx(1.0)


def test_validate_weights() -> None:
    validate_weights(np.array([0.5, 0.5]), 2)
    with pytest.raises(InvalidInputError):
        validate_weights(np.array([0.5, 0.6]), 2)
    with pytest.raises(InvalidInputError):
        validate_weights(np.array([1.5, -0.5]), 2)
    validate_weights(np.array([1.5, -0.5]), 2, allow_short=True)
    with pytest.raises(InvalidInputError):
        validate_weights(np.array([np.nan, 1.0]), 2)


def test_validate_covariance_rejects_non_psd() -> None:
    with pytest.raises(InvalidInputError):
        validate_covariance(np.array([[1.0, 2.0], [2.0, 1.0]]))
    with pytest.raises(InvalidInputError):
        validate_covariance(np.array([[1.0, 0.1], [0.2, 1.0]]))


def test_buy_and_hold_matches_manual_value() -> None:
    idx = pd.bdate_range("2024-01-01", periods=2)
    r = pd.DataFrame({"A": [0.1, 0.1], "B": [0.0, -0.5]}, index=idx)
    p = buy_and_hold_returns(r, np.array([0.5, 0.5]))
    # Values: 0.5*1.1 + 0.5*1.0 = 1.05 ; 0.5*1.21 + 0.5*0.5 = 0.855
    np.testing.assert_allclose(p.to_numpy(), [0.05, 0.855 / 1.05 - 1])


def test_constant_mix() -> None:
    idx = pd.bdate_range("2024-01-01", periods=2)
    r = pd.DataFrame({"A": [0.1, 0.1], "B": [0.0, -0.5]}, index=idx)
    np.testing.assert_allclose(
        constant_mix_returns(r, np.array([0.5, 0.5])).to_numpy(), [0.05, -0.2]
    )
