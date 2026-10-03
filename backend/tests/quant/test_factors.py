"""Fama-French three-factor regression against statsmodels (OLS with Newey-West standard
errors), exact identities of least squares and hand-compounded factor returns."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.factors import (
    FACTORS,
    factor_regression,
    newey_west_lags,
    period_factors,
)


def _factors(n: int, seed: int = 0, start: str = "2015-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame(
        {
            "MKT_RF": rng.normal(0.0004, 0.011, n),
            "SMB": rng.normal(0.0001, 0.005, n),
            "HML": rng.normal(0.0000, 0.006, n),
            "RF": np.full(n, 0.00008),
        },
        index=idx,
    )


def _series(
    f: pd.DataFrame, betas: tuple[float, float, float], alpha: float, noise: float, seed: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    e = rng.normal(0, noise, len(f))
    # Autocorrelated errors make the Newey-West correction matter.
    e = e + 0.4 * np.concatenate(([0.0], e[:-1]))
    return alpha + f[list(FACTORS)].to_numpy() @ np.array(betas) + e


@pytest.mark.parametrize("lags", [None, 0, 3])
def test_matches_statsmodels_ols_with_newey_west_errors(lags: int | None) -> None:
    f = _factors(750, seed=1)
    y = _series(f, (1.1, 0.4, -0.3), 0.0001, 0.004, seed=2)
    res = factor_regression(y, f[list(FACTORS)].to_numpy(), 252, lags=lags)
    nlags = newey_west_lags(750) if lags is None else lags
    ref = sm.OLS(y, sm.add_constant(f[list(FACTORS)].to_numpy())).fit(
        cov_type="HAC", cov_kwds={"maxlags": nlags, "use_correction": True}, use_t=True
    )
    assert res.lags == nlags
    assert res.coefficients == pytest.approx(ref.params, rel=1e-10, abs=1e-14)
    assert res.std_errors == pytest.approx(ref.bse, rel=1e-9)
    assert res.t_stats == pytest.approx(ref.tvalues, rel=1e-9)
    assert res.p_values == pytest.approx(ref.pvalues, rel=1e-7, abs=1e-14)
    assert res.r_squared == pytest.approx(ref.rsquared, rel=1e-12)
    assert res.adj_r_squared == pytest.approx(ref.rsquared_adj, rel=1e-12)
    assert res.residual_volatility == pytest.approx(np.sqrt(ref.mse_resid * 252), rel=1e-12)
    # And the coefficients from a plain least-squares solve.
    x = np.column_stack([np.ones(750), f[list(FACTORS)].to_numpy()])
    assert res.coefficients == pytest.approx(
        np.linalg.lstsq(x, y, rcond=None)[0], rel=1e-10, abs=1e-14
    )


def test_recovers_known_loadings() -> None:
    f = _factors(5000, seed=4)
    y = _series(f, (0.8, -0.2, 0.6), 0.0002, 0.0005, seed=5)
    res = factor_regression(y, f[list(FACTORS)].to_numpy(), 252)
    assert res.loadings == pytest.approx([0.8, -0.2, 0.6], abs=0.01)
    # Within four standard errors of the true alpha.
    assert abs(res.alpha - 0.0002 * 252) < 4 * res.std_errors[0] * 252
    assert res.r_squared > 0.99


def test_mean_excess_return_splits_exactly() -> None:
    f = _factors(400, seed=6)
    y = _series(f, (1.3, 0.2, 0.1), -0.0001, 0.006, seed=7)
    res = factor_regression(y, f[list(FACTORS)].to_numpy(), 252)
    assert res.alpha + res.contributions.sum() == pytest.approx(res.mean_excess_return, abs=1e-12)
    assert res.factor_means == pytest.approx(f[list(FACTORS)].mean().to_numpy() * 252, rel=1e-12)


def test_portfolio_loadings_are_the_weighted_asset_loadings() -> None:
    f = _factors(500, seed=8)
    x = f[list(FACTORS)].to_numpy()
    assets = np.column_stack(
        [
            _series(f, b, 0.0, 0.007, seed=10 + i)
            for i, b in enumerate([(1.2, 0.5, 0.3), (0.6, -0.3, 0.8), (1.0, 0.0, -0.5)])
        ]
    )
    w = np.array([0.5, 0.3, 0.2])
    port = factor_regression(assets @ w, x, 252)
    each = np.array([factor_regression(assets[:, i], x, 252).coefficients for i in range(3)])
    assert port.coefficients == pytest.approx(w @ each, rel=1e-10, abs=1e-14)


def test_daily_periods_reproduce_the_daily_factors() -> None:
    f = _factors(60, seed=9)
    pf = period_factors(f, pd.DatetimeIndex(f.index))
    assert pf.frame.index.equals(f.index[1:])
    assert pf.frame.to_numpy() == pytest.approx(
        f.iloc[1:][[*FACTORS, "RF"]].to_numpy(), rel=1e-12, abs=1e-16
    )
    assert (pf.dropped_before, pf.dropped_after, pf.dropped_empty) == (0, 0, 0)


def test_weekly_periods_compound_the_days_inside() -> None:
    f = _factors(80, seed=11)
    ends = pd.DatetimeIndex([d for d in f.index if d.dayofweek == 4])  # Fridays
    pf = period_factors(f, ends)
    second = f.loc[(f.index > ends[0]) & (f.index <= ends[1])]
    assert len(second) == 5
    rf = np.prod(1 + second["RF"]) - 1
    mkt = np.prod(1 + second["MKT_RF"] + second["RF"]) - 1
    row = pf.frame.iloc[0]
    assert row["RF"] == pytest.approx(rf, rel=1e-12)
    assert row["MKT_RF"] == pytest.approx(mkt - rf, rel=1e-12)
    assert row["SMB"] == pytest.approx(np.prod(1 + second["SMB"]) - 1, rel=1e-12)
    assert row["HML"] == pytest.approx(np.prod(1 + second["HML"]) - 1, rel=1e-12)


def test_periods_outside_the_factor_data_are_dropped_and_counted() -> None:
    f = _factors(50, seed=12, start="2020-01-06")
    ends = pd.DatetimeIndex(
        [
            pd.Timestamp("2019-12-20"),
            pd.Timestamp("2019-12-31"),
            *f.index[5:45:5],
            pd.Timestamp("2020-12-31"),
        ]
    )
    pf = period_factors(f, ends)
    # (2019-12-20, 2019-12-31] and (2019-12-31, first Friday] start before the data.
    assert pf.dropped_before == 2
    assert pf.dropped_after == 1
    assert len(pf.frame) == len(ends) - 1 - 3


def test_undefined_regressions_are_refused() -> None:
    f = _factors(200, seed=13)
    x = f[list(FACTORS)].to_numpy()
    with pytest.raises(InsufficientDataError, match="at least 30"):
        factor_regression(np.zeros(20) + 0.001, x[:20], 252)
    with pytest.raises(InvalidInputError, match="do not vary"):
        factor_regression(np.full(200, 0.001), x, 252)
    collinear = np.column_stack([x[:, 0], x[:, 0] * 2.0, x[:, 2]])
    with pytest.raises(InvalidInputError, match="collinear"):
        factor_regression(x[:, 0] + 0.001, collinear, 252)


def test_lag_rule() -> None:
    assert newey_west_lags(100) == 4
    assert newey_west_lags(1000) == 6
    assert newey_west_lags(2520) == 8
