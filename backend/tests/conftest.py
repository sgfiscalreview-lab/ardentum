"""Shared fixtures for the Ardentum test-suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_returns(
    n_obs: int = 750,
    n_assets: int = 5,
    seed: int = 7,
    *,
    annual_mu: np.ndarray | None = None,
    annual_vol: np.ndarray | None = None,
    corr: float = 0.3,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Deterministic multivariate-normal daily simple returns for tests."""
    rng = np.random.default_rng(seed)
    mu = np.linspace(0.04, 0.14, n_assets) if annual_mu is None else annual_mu
    vol = np.linspace(0.12, 0.32, n_assets) if annual_vol is None else annual_vol
    c = np.full((n_assets, n_assets), corr)
    np.fill_diagonal(c, 1.0)
    cov = np.outer(vol, vol) * c / periods_per_year
    x = rng.multivariate_normal(mu / periods_per_year, cov, size=n_obs)
    index = pd.bdate_range("2015-01-02", periods=n_obs)
    return pd.DataFrame(x, index=index, columns=[f"A{i}" for i in range(n_assets)])


@pytest.fixture
def returns_df() -> pd.DataFrame:
    return make_returns()
