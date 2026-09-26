import itertools

import numpy as np
import pytest

from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.montecarlo import (
    MonteCarloConfig,
    SimulationMethod,
    lognormal_parameters,
    simulate_bootstrap,
    simulate_parametric,
)


def test_lognormal_moment_matching() -> None:
    a, s = lognormal_parameters(0.01, 0.0025)
    mean = np.exp(a + s * s / 2) - 1
    var = (np.exp(s * s) - 1) * np.exp(2 * a + s * s)
    assert mean == pytest.approx(0.01)
    assert var == pytest.approx(0.0025)


def test_parametric_reproducible_with_seed() -> None:
    cfg = MonteCarloConfig(seed=42, n_paths=500, horizon_years=2)
    a = simulate_parametric(cfg, 0.08, 0.15)
    b = simulate_parametric(cfg, 0.08, 0.15)
    np.testing.assert_array_equal(a.terminal_values, b.terminal_values)
    np.testing.assert_array_equal(a.percentile_paths[50], b.percentile_paths[50])
    c = simulate_parametric(MonteCarloConfig(seed=43, n_paths=500, horizon_years=2), 0.08, 0.15)
    assert not np.array_equal(a.terminal_values, c.terminal_values)


def test_parametric_matches_analytic_moments() -> None:
    """E[W_T] = W0 (1 + m)^n and median = W0 exp(n a) for i.i.d. lognormal returns."""
    mu, vol, years, p = 0.08, 0.20, 5, 12
    cfg = MonteCarloConfig(
        seed=1,
        n_paths=40_000,
        horizon_years=years,
        periods_per_year=p,
        periods_per_step=1,
        initial_value=1.0,
    )
    res = simulate_parametric(cfg, mu, vol)
    n = years * p
    m, v = mu / p, vol**2 / p
    a, s = lognormal_parameters(m, v)
    expected_mean = (1 + m) ** n
    log_t = np.log(res.terminal_values)
    se_log = s * np.sqrt(n) / np.sqrt(cfg.n_paths)
    assert log_t.mean() == pytest.approx(n * a, abs=4 * se_log)
    assert log_t.std() == pytest.approx(s * np.sqrt(n), rel=0.02)
    se_mean = res.terminal_values.std() / np.sqrt(cfg.n_paths)
    assert res.terminal_values.mean() == pytest.approx(expected_mean, abs=4 * se_mean)
    assert res.terminal_percentiles[50] == pytest.approx(np.exp(n * a), rel=0.02)


def test_zero_volatility_is_deterministic() -> None:
    cfg = MonteCarloConfig(
        seed=3, n_paths=10, horizon_years=1, periods_per_year=12, periods_per_step=1
    )
    res = simulate_parametric(cfg, 0.12, 0.0)
    np.testing.assert_allclose(res.terminal_values, 10_000 * 1.01**12)
    assert res.probability_of_loss == 0.0
    np.testing.assert_allclose(res.max_drawdown_percentiles[5], 0.0)


def test_percentile_paths_are_ordered_and_start_at_initial() -> None:
    res = simulate_parametric(MonteCarloConfig(seed=5, n_paths=2000, horizon_years=3), 0.07, 0.18)
    keys = sorted(res.percentile_paths)
    for lo, hi in itertools.pairwise(keys):
        assert (res.percentile_paths[lo] <= res.percentile_paths[hi] + 1e-9).all()
    for k in keys:
        assert res.percentile_paths[k][0] == 10_000
    assert res.times_years[0] == 0
    assert res.times_years[-1] == pytest.approx(3.0)
    assert res.sample_paths.shape == (20, len(res.times_years))


def test_drawdowns_are_non_positive_and_var_consistent() -> None:
    res = simulate_parametric(MonteCarloConfig(seed=6, n_paths=3000, horizon_years=5), 0.06, 0.25)
    assert all(v <= 0 for v in res.max_drawdown_percentiles.values())
    assert res.terminal_return_cvar_95 >= res.terminal_return_var_95
    assert 0 < res.probability_of_loss < 1


def test_probability_of_target() -> None:
    cfg = MonteCarloConfig(seed=7, n_paths=5000, horizon_years=10, target_value=20_000)
    res = simulate_parametric(cfg, 0.07, 0.15)
    assert res.probability_of_target == pytest.approx(np.mean(res.terminal_values >= 20_000))


def test_iid_bootstrap_expected_terminal_value() -> None:
    """For i.i.d. resampling, E[prod(1 + r)] = (1 + mean(r))^n exactly."""
    rng = np.random.default_rng(0)
    hist = rng.normal(0.0004, 0.01, 1000)
    cfg = MonteCarloConfig(
        seed=11,
        method=SimulationMethod.BOOTSTRAP,
        n_paths=20_000,
        horizon_years=1,
        initial_value=1.0,
    )
    res = simulate_bootstrap(cfg, hist)
    expected = (1 + hist.mean()) ** 252
    se = res.terminal_values.std() / np.sqrt(cfg.n_paths)
    assert res.terminal_values.mean() == pytest.approx(expected, abs=4 * se)


def test_block_bootstrap_preserves_autocorrelation() -> None:
    rng = np.random.default_rng(1)
    t = 5000
    e = rng.normal(0, 0.01, t)
    hist = np.empty(t)
    hist[0] = e[0]
    for i in range(1, t):
        hist[i] = 0.6 * hist[i - 1] + e[i]  # strongly autocorrelated returns

    def lag1_of_sim(method: SimulationMethod) -> float:
        cfg = MonteCarloConfig(
            seed=2,
            method=method,
            n_paths=1,
            horizon_years=40,
            periods_per_step=10_080,
            n_sample_paths=1,
            mean_block_length=50,
        )
        from ardentum.quant import montecarlo

        captured: list[np.ndarray] = []
        original = montecarlo._run

        def spy(config, draw, *args):  # type: ignore[no-untyped-def]
            def wrapped(rng, k, n):  # type: ignore[no-untyped-def]
                inc = draw(rng, k, n)
                captured.append(inc[:, 0])
                return inc

            return original(config, wrapped, *args)

        montecarlo._run = spy  # type: ignore[assignment]
        try:
            simulate_bootstrap(cfg, hist)
        finally:
            montecarlo._run = original  # type: ignore[assignment]
        series = np.concatenate(captured)
        return float(np.corrcoef(series[:-1], series[1:])[0, 1])

    assert lag1_of_sim(SimulationMethod.BOOTSTRAP) == pytest.approx(0.0, abs=0.05)
    assert lag1_of_sim(SimulationMethod.BLOCK_BOOTSTRAP) == pytest.approx(0.6, abs=0.06)


def test_bootstrap_reproducible() -> None:
    hist = np.random.default_rng(4).normal(0.0003, 0.012, 500)
    cfg = MonteCarloConfig(
        seed=9, method=SimulationMethod.BLOCK_BOOTSTRAP, n_paths=300, horizon_years=2
    )
    a = simulate_bootstrap(cfg, hist)
    b = simulate_bootstrap(cfg, hist)
    np.testing.assert_array_equal(a.terminal_values, b.terminal_values)


def test_bootstrap_requires_history() -> None:
    cfg = MonteCarloConfig(seed=1, method=SimulationMethod.BOOTSTRAP)
    with pytest.raises(InsufficientDataError):
        simulate_bootstrap(cfg, np.zeros(10))


@pytest.mark.parametrize(
    "cfg",
    [
        MonteCarloConfig(seed=1, n_paths=0),
        MonteCarloConfig(seed=1, horizon_years=0),
        MonteCarloConfig(seed=1, initial_value=-5),
        MonteCarloConfig(seed=1, n_paths=20_000, horizon_years=25),
        MonteCarloConfig(seed=1, percentiles=(0, 50)),
    ],
)
def test_invalid_configs(cfg: MonteCarloConfig) -> None:
    with pytest.raises(InvalidInputError):
        simulate_parametric(cfg, 0.05, 0.1)


def test_stationary_bootstrap_block_structure() -> None:
    """Consecutive draws continue the history (i -> i+1 mod T) with probability 1 - 1/L."""
    from ardentum.quant import montecarlo

    t = 997
    hist = np.linspace(-0.02, 0.02, t)  # distinct values let us recover the indices
    log_hist = np.log1p(hist)
    captured: list[np.ndarray] = []
    original = montecarlo._run

    def spy(config, draw, *args):  # type: ignore[no-untyped-def]
        def wrapped(rng, k, n):  # type: ignore[no-untyped-def]
            inc = draw(rng, k, n)
            captured.append(inc)
            return inc

        return original(config, wrapped, *args)

    montecarlo._run = spy  # type: ignore[assignment]
    try:
        cfg = MonteCarloConfig(
            seed=3,
            method=SimulationMethod.BLOCK_BOOTSTRAP,
            n_paths=400,
            horizon_years=4,
            mean_block_length=10,
            periods_per_step=21,
        )
        simulate_bootstrap(cfg, hist)
    finally:
        montecarlo._run = original  # type: ignore[assignment]
    inc = np.concatenate(captured, axis=0)
    idx = np.searchsorted(log_hist, inc)
    np.testing.assert_allclose(log_hist[idx], inc)
    cont = (idx[1:] == (idx[:-1] + 1) % t).mean()
    # P(continue) = (1 - 1/L) + (1/L)(1/T) for a uniformly drawn new start.
    assert cont == pytest.approx(0.9 + 0.1 / t, abs=0.01)
