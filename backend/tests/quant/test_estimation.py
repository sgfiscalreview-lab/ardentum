import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import LedoitWolf

from ardentum.quant.errors import InsufficientDataError
from ardentum.quant.estimation import (
    CovarianceEstimator,
    MeanEstimator,
    bayes_stein_mean,
    estimate,
    historical_mean,
    ledoit_wolf_constant_correlation,
    ledoit_wolf_covariance,
    risk_free_arithmetic,
    sample_covariance,
)
from tests.conftest import make_returns


def test_historical_mean(returns_df: pd.DataFrame) -> None:
    np.testing.assert_allclose(
        historical_mean(returns_df, 252), returns_df.mean().to_numpy() * 252
    )


def test_sample_covariance(returns_df: pd.DataFrame) -> None:
    np.testing.assert_allclose(
        sample_covariance(returns_df, 252), returns_df.cov().to_numpy() * 252
    )


def test_ledoit_wolf_identity_matches_scikit_learn(returns_df: pd.DataFrame) -> None:
    ours, delta = ledoit_wolf_covariance(returns_df, 1)
    ref = LedoitWolf(assume_centered=False).fit(returns_df.to_numpy())
    np.testing.assert_allclose(ours, ref.covariance_, rtol=1e-10, atol=1e-16)
    assert delta == pytest.approx(ref.shrinkage_)


def test_ledoit_wolf_identity_high_dimension() -> None:
    df = make_returns(n_obs=40, n_assets=30, seed=11)
    ours, delta = ledoit_wolf_covariance(df, 1)
    ref = LedoitWolf().fit(df.to_numpy())
    np.testing.assert_allclose(ours, ref.covariance_, rtol=1e-10, atol=1e-16)
    assert 0.0 < delta <= 1.0
    assert np.linalg.eigvalsh(ours).min() > 0  # well-conditioned even when T < 2N


def _naive_constant_correlation(x: np.ndarray) -> tuple[np.ndarray, float]:
    """Loop implementation of the Ledoit-Wolf (2004, JPM) appendix formulas."""
    t, n = x.shape
    y = x - x.mean(axis=0)
    s = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            s[i, j] = np.sum(y[:, i] * y[:, j]) / t
    r = np.array([[s[i, j] / np.sqrt(s[i, i] * s[j, j]) for j in range(n)] for i in range(n)])
    r_bar = sum(r[i, j] for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    f = np.array(
        [
            [s[i, i] if i == j else r_bar * np.sqrt(s[i, i] * s[j, j]) for j in range(n)]
            for i in range(n)
        ]
    )
    pi_hat = sum(
        np.mean((y[:, i] * y[:, j] - s[i, j]) ** 2) for i in range(n) for j in range(n)
    )

    def theta(i: int, j: int) -> float:
        return float(np.mean((y[:, i] ** 2 - s[i, i]) * (y[:, i] * y[:, j] - s[i, j])))

    rho_hat = sum(np.mean((y[:, i] ** 2 - s[i, i]) ** 2) for i in range(n))
    rho_hat += sum(
        (r_bar / 2)
        * (np.sqrt(s[j, j] / s[i, i]) * theta(i, j) + np.sqrt(s[i, i] / s[j, j]) * theta(j, i))
        for i in range(n)
        for j in range(n)
        if i != j
    )
    gamma_hat = np.sum((f - s) ** 2)
    delta = max(0.0, min(1.0, (pi_hat - rho_hat) / gamma_hat / t))
    return delta * f + (1 - delta) * s, delta


def test_ledoit_wolf_constant_correlation_matches_paper_formulas() -> None:
    df = make_returns(n_obs=120, n_assets=4, seed=5)
    ours, delta = ledoit_wolf_constant_correlation(df, 1)
    ref, ref_delta = _naive_constant_correlation(df.to_numpy())
    assert delta == pytest.approx(ref_delta, rel=1e-10)
    np.testing.assert_allclose(ours, ref, rtol=1e-10)


def test_ledoit_wolf_constant_correlation_close_to_pypfopt() -> None:
    """PyPortfolioOpt mixes a ddof=1 sample covariance into the 1/T formulas, so the
    agreement is only up to O(1/T); this is an independent sanity check."""
    from pypfopt.risk_models import CovarianceShrinkage

    df = make_returns(n_obs=2000, n_assets=6, seed=9)
    ours, _ = ledoit_wolf_constant_correlation(df, 252)
    ref = CovarianceShrinkage(df, returns_data=True, frequency=252).ledoit_wolf(
        "constant_correlation"
    )
    np.testing.assert_allclose(ours, ref.to_numpy(), rtol=2e-3)


def test_constant_correlation_target_properties() -> None:
    df = make_returns(n_obs=60, n_assets=8, seed=12)
    cov, delta = ledoit_wolf_constant_correlation(df, 252)
    assert 0.0 <= delta <= 1.0
    np.testing.assert_allclose(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() > 0
    # Variances are untouched by constant-correlation shrinkage (1/T normalisation).
    x = df.to_numpy()
    np.testing.assert_allclose(np.diag(cov), x.var(axis=0, ddof=0) * 252)


def test_bayes_stein_equal_means_collapse_to_grand_mean() -> None:
    df = make_returns(n_obs=300, n_assets=4, seed=3)
    df = df - df.mean() + 0.0004  # identical sample means
    mu, phi = bayes_stein_mean(df, 252)
    assert phi == pytest.approx(1.0)
    np.testing.assert_allclose(mu, 0.0004 * 252)


def test_bayes_stein_shrinks_between_sample_and_target() -> None:
    df = make_returns(n_obs=500, n_assets=5, seed=4)
    mu_bs, phi = bayes_stein_mean(df, 252)
    mu_hist = historical_mean(df, 252)
    assert 0.0 < phi < 1.0
    # Dispersion of shrunk means is strictly lower than that of sample means.
    assert np.std(mu_bs) < np.std(mu_hist)
    # Manual formula check.
    x = df.to_numpy()
    t, n = x.shape
    s = np.cov(x, rowvar=False) * (t - 1) / (t - n - 2)
    inv = np.linalg.inv(s)
    one = np.ones(n)
    m = x.mean(axis=0)
    mu0 = one @ inv @ m / (one @ inv @ one)
    phi_ref = (n + 2) / ((n + 2) + t * (m - mu0) @ inv @ (m - mu0))
    assert phi == pytest.approx(phi_ref)


def test_bayes_stein_requires_enough_observations() -> None:
    df = make_returns(n_obs=6, n_assets=5, seed=1)
    with pytest.raises(InsufficientDataError):
        bayes_stein_mean(df, 252)


def test_estimate_sample_covariance_rejected_when_singular() -> None:
    df = make_returns(n_obs=30, n_assets=40, seed=1)
    with pytest.raises(InsufficientDataError):
        estimate(df, 252, covariance_estimator=CovarianceEstimator.SAMPLE)
    est = estimate(df, 252, covariance_estimator=CovarianceEstimator.LEDOIT_WOLF)
    assert np.linalg.eigvalsh(est.covariance).min() > 0


def test_estimate_minimum_observations() -> None:
    df = make_returns(n_obs=10, n_assets=2, seed=1)
    with pytest.raises(InsufficientDataError):
        estimate(df, 252)


def test_estimate_records_provenance(returns_df: pd.DataFrame) -> None:
    est = estimate(
        returns_df,
        252,
        mean_estimator=MeanEstimator.BAYES_STEIN,
        covariance_estimator=CovarianceEstimator.LEDOIT_WOLF_CONSTANT_CORRELATION,
    )
    assert est.observations == len(returns_df)
    assert est.start == returns_df.index[0].date()
    assert est.end == returns_df.index[-1].date()
    assert est.mean_shrinkage is not None
    assert est.covariance_shrinkage is not None
    sub = est.subset(["A3", "A1"])
    assert sub.tickers == ("A3", "A1")
    assert sub.covariance[0, 1] == est.covariance[3, 1]


def test_risk_free_arithmetic() -> None:
    assert risk_free_arithmetic(0.05, 252) == pytest.approx(252 * (1.05 ** (1 / 252) - 1))
    assert risk_free_arithmetic(0.0, 12) == 0.0
