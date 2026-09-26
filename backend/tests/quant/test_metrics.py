import numpy as np
import pandas as pd
import pytest
from scipy import stats

from ardentum.quant.errors import InvalidInputError, UndefinedMetricError
from ardentum.quant.estimation import historical_mean, risk_free_arithmetic, sample_covariance
from ardentum.quant.metrics import (
    annualised_volatility,
    beta,
    calmar_ratio,
    conditional_value_at_risk,
    correlation_matrix,
    covariance_matrix,
    downside_deviation,
    drawdown_series,
    information_ratio,
    max_drawdown,
    performance_summary,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
    value_at_risk,
)
from ardentum.quant.portfolio import constant_mix_returns, portfolio_sharpe


def test_volatility_known_value() -> None:
    r = np.array([0.01, -0.01, 0.01, -0.01])
    assert annualised_volatility(r, 252) == pytest.approx(0.01 * np.sqrt(4 / 3) * np.sqrt(252))


def test_sharpe_known_value() -> None:
    # mean 4%, sd 2% monthly -> 2 * sqrt(12)
    assert sharpe_ratio(np.array([0.02, 0.04, 0.06]), 12) == pytest.approx(2 * np.sqrt(12))


def test_sharpe_with_risk_free_rate() -> None:
    r = np.array([0.02, 0.04, 0.06])
    rf_m = 1.06 ** (1 / 12) - 1
    expected = (0.04 - rf_m) / 0.02 * np.sqrt(12)
    assert sharpe_ratio(r, 12, risk_free_rate=0.06) == pytest.approx(expected)


def test_sharpe_undefined_for_constant_returns() -> None:
    with pytest.raises(UndefinedMetricError):
        sharpe_ratio(np.full(10, 0.01), 12)


def test_sortino_known_value() -> None:
    r = np.array([0.02, -0.01, 0.03, -0.02])
    dd = np.sqrt((0.01**2 + 0.02**2) / 4)  # all observations in the denominator
    assert sortino_ratio(r, 12) == pytest.approx(0.005 / dd * np.sqrt(12))
    assert downside_deviation(r, 12) == pytest.approx(dd * np.sqrt(12))


def test_sortino_undefined_without_downside() -> None:
    with pytest.raises(UndefinedMetricError):
        sortino_ratio(np.array([0.01, 0.02, 0.03]), 12)


def test_max_drawdown_known_path() -> None:
    # 100 -> 120 -> 90 -> 130
    r = np.array([0.2, -0.25, 130 / 90 - 1])
    dd = max_drawdown(r)
    assert dd.max_drawdown == pytest.approx(-0.25)
    assert (dd.peak_position, dd.trough_position, dd.recovery_position) == (1, 2, 3)


def test_max_drawdown_counts_first_period_loss() -> None:
    dd = max_drawdown(np.array([-0.1, 0.05]))
    assert dd.max_drawdown == pytest.approx(-0.1)
    assert dd.peak_position == 0
    assert dd.recovery_position is None


def test_max_drawdown_no_loss() -> None:
    assert max_drawdown(np.array([0.01, 0.02])).max_drawdown == 0.0


def test_drawdown_series_brute_force() -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.0, 0.02, 300)
    w = np.concatenate(([1.0], np.cumprod(1 + r)))
    brute = np.array([w[i] / w[: i + 1].max() - 1 for i in range(len(w))])
    np.testing.assert_allclose(drawdown_series(r), brute)
    assert max_drawdown(r).max_drawdown == pytest.approx(brute.min())


def test_calmar() -> None:
    r = np.array([0.2, -0.25, 130 / 90 - 1])
    cagr = 1.3 ** (12 / 3) - 1
    assert calmar_ratio(r, 12) == pytest.approx(cagr / 0.25)


def test_beta_exact_linear_relationship() -> None:
    rng = np.random.default_rng(2)
    m = rng.normal(0.0, 0.01, 500)
    assert beta(2.0 * m + 0.001, m) == pytest.approx(2.0)


def test_beta_matches_ols_slope() -> None:
    rng = np.random.default_rng(3)
    m = rng.normal(0.0, 0.01, 500)
    a = 0.7 * m + rng.normal(0.0, 0.01, 500)
    assert beta(a, m) == pytest.approx(stats.linregress(m, a).slope)


def test_beta_undefined_for_constant_market() -> None:
    with pytest.raises(UndefinedMetricError):
        beta(np.array([0.1, 0.2, 0.3]), np.array([0.01, 0.01, 0.01]))


def test_covariance_and_correlation(returns_df: pd.DataFrame) -> None:
    cov = covariance_matrix(returns_df, 252)
    np.testing.assert_allclose(cov.to_numpy(), returns_df.cov().to_numpy() * 252)
    corr = correlation_matrix(returns_df)
    np.testing.assert_allclose(corr.to_numpy(), returns_df.corr().to_numpy(), atol=1e-12)
    np.testing.assert_allclose(np.diag(corr.to_numpy()), 1.0)


def test_correlation_undefined_for_constant_asset() -> None:
    df = pd.DataFrame({"A": [0.01, 0.02, 0.03], "B": [0.01, 0.01, 0.01]})
    with pytest.raises(UndefinedMetricError):
        correlation_matrix(df)


def test_historical_var_and_cvar() -> None:
    r = np.linspace(-0.05, 0.05, 101)
    assert value_at_risk(r, 0.95) == pytest.approx(0.045)
    assert conditional_value_at_risk(r, 0.95) == pytest.approx(0.0475)
    assert conditional_value_at_risk(r, 0.95) >= value_at_risk(r, 0.95)


def test_gaussian_var() -> None:
    rng = np.random.default_rng(4)
    r = rng.normal(0.001, 0.02, 1000)
    expected = -(r.mean() + stats.norm.ppf(0.05) * r.std(ddof=1))
    assert value_at_risk(r, 0.95, method="gaussian") == pytest.approx(expected)


def test_var_rejects_bad_confidence() -> None:
    with pytest.raises(InvalidInputError):
        value_at_risk(np.array([0.1, 0.2]), 1.2)


def test_tracking_error_and_information_ratio() -> None:
    b = np.array([0.01, -0.02, 0.03, 0.0])
    p = b + np.array([0.001, 0.002, 0.0, 0.001])
    active = p - b
    assert tracking_error(p, b, 12) == pytest.approx(active.std(ddof=1) * np.sqrt(12))
    assert information_ratio(p, b, 12) == pytest.approx(
        active.mean() / active.std(ddof=1) * np.sqrt(12)
    )
    with pytest.raises(UndefinedMetricError):
        information_ratio(b, b, 12)


def test_nan_returns_rejected() -> None:
    with pytest.raises(InvalidInputError):
        annualised_volatility(np.array([0.01, np.nan, 0.02]), 252)


def test_ex_ante_sharpe_equals_ex_post_on_same_sample(returns_df: pd.DataFrame) -> None:
    """Consistency of the annualisation conventions across modules."""
    w = np.array([0.1, 0.2, 0.3, 0.25, 0.15])
    rf = 0.03
    mu = historical_mean(returns_df, 252)
    cov = sample_covariance(returns_df, 252)
    ex_ante = portfolio_sharpe(w, mu, cov, risk_free_arithmetic(rf, 252))
    ex_post = sharpe_ratio(constant_mix_returns(returns_df, w), 252, risk_free_rate=rf)
    assert ex_ante == pytest.approx(ex_post, rel=1e-10)


def test_performance_summary_undefined_metrics_carry_reasons() -> None:
    s = performance_summary(np.full(12, 0.01), 12)
    assert s.sharpe_ratio.value is None
    assert s.sharpe_ratio.reason is not None
    assert s.cagr == pytest.approx(1.01**12 - 1)


def test_performance_summary_with_benchmark(returns_df: pd.DataFrame) -> None:
    p = returns_df["A1"].to_numpy()
    b = returns_df["A0"].to_numpy()
    s = performance_summary(p, 252, 0.02, b)
    assert s.beta is not None
    assert s.beta.value == pytest.approx(beta(p, b))
    assert s.tracking_error == pytest.approx(tracking_error(p, b, 252))
