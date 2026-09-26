"""Monte Carlo simulation of portfolio wealth.

The portfolio is assumed to be rebalanced to its target weights every data period
(constant mix), so its per-period return is ``r_p,t = w' r_t``. Simulation runs at
the data frequency (e.g. daily) and results are recorded at reporting steps.

Methods
-------
``parametric``
    I.i.d. lognormal gross returns whose per-period mean and variance equal the
    portfolio's arithmetic moments implied by the *same* annualised estimates the
    optimiser used: ``m = w' mu / P`` and ``v = w' S w / P``. Moment matching gives
    ``log(1 + r) ~ N(a, s^2)`` with ``s^2 = ln(1 + v / (1 + m)^2)`` and
    ``a = ln(1 + m) - s^2 / 2``. Thin-tailed; ignores volatility clustering.
``bootstrap``
    I.i.d. resampling (with replacement) of historical portfolio returns
    ``w' r_t``. Preserves the empirical marginal distribution (fat tails, skew)
    and cross-asset dependence at each date, but not serial dependence.
``block_bootstrap``
    Stationary bootstrap of Politis & Romano (1994), JASA 89(428): blocks of
    consecutive historical returns with geometric lengths (mean ``L``), wrapping
    circularly. Also preserves short-range serial dependence such as volatility
    clustering.

Reproducibility: all randomness comes from one ``numpy.random.Generator``
(PCG64) seeded with the explicit ``seed``; identical inputs and seed give
bit-identical outputs.

Limitations: no parameter uncertainty (estimates are treated as true), no cash
flows, taxes or transaction costs, and history-based methods cannot generate
scenarios worse than the historical sample's worst periods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from ardentum.quant.errors import InsufficientDataError, InvalidInputError

MAX_PATHS = 50_000
MAX_WORK = 100_000_000  # paths x periods (~5 s worst case; keeps requests interactive)
DEFAULT_PERCENTILES = (5, 10, 25, 50, 75, 90, 95)


class SimulationMethod(StrEnum):
    PARAMETRIC = "parametric"
    BOOTSTRAP = "bootstrap"
    BLOCK_BOOTSTRAP = "block_bootstrap"


@dataclass(frozen=True)
class MonteCarloConfig:
    seed: int
    method: SimulationMethod = SimulationMethod.PARAMETRIC
    n_paths: int = 5_000
    horizon_years: float = 10.0
    initial_value: float = 10_000.0
    periods_per_year: int = 252
    periods_per_step: int = 21  # reporting granularity (21 trading days ~ 1 month)
    mean_block_length: float = 21.0
    target_value: float | None = None
    percentiles: tuple[int, ...] = DEFAULT_PERCENTILES
    n_sample_paths: int = 20


@dataclass(frozen=True)
class MonteCarloResult:
    config: MonteCarloConfig
    times_years: np.ndarray  # reporting times, starting at 0
    percentile_paths: dict[int, np.ndarray]
    mean_path: np.ndarray
    sample_paths: np.ndarray  # (n_sample_paths, n_steps + 1)
    terminal_values: np.ndarray
    terminal_percentiles: dict[int, float]
    probability_of_loss: float
    probability_of_target: float | None
    terminal_return_var_95: float  # loss fraction of initial value, positive = loss
    terminal_return_cvar_95: float
    cagr_percentiles: dict[int, float]
    max_drawdown_percentiles: dict[int, float]
    per_period_mean: float
    per_period_volatility: float
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    def histogram(self, bins: int = 50) -> tuple[np.ndarray, np.ndarray]:
        counts, edges = np.histogram(self.terminal_values, bins=bins)
        return counts, edges


def lognormal_parameters(mean: float, variance: float) -> tuple[float, float]:
    """(mu, sigma) of ``log(1 + r)`` matching ``E[r] = mean`` and ``Var[r] = variance``."""
    if mean <= -1.0:
        raise InvalidInputError("Expected per-period return must exceed -100%.")
    if variance < 0:
        raise InvalidInputError("Variance must be non-negative.")
    s2 = float(np.log1p(variance / (1.0 + mean) ** 2))
    return float(np.log1p(mean) - 0.5 * s2), float(np.sqrt(s2))


def _validate(config: MonteCarloConfig) -> int:
    if not 1 <= config.n_paths <= MAX_PATHS:
        raise InvalidInputError(f"Number of paths must be between 1 and {MAX_PATHS:,}.")
    if not 0 < config.horizon_years <= 50:
        raise InvalidInputError("Horizon must be between 0 and 50 years.")
    if config.initial_value <= 0:
        raise InvalidInputError("Initial value must be positive.")
    if config.periods_per_step < 1:
        raise InvalidInputError("Periods per reporting step must be at least 1.")
    if config.mean_block_length < 1:
        raise InvalidInputError("Mean block length must be at least 1.")
    if any(not 0 < p < 100 for p in config.percentiles):
        raise InvalidInputError("Percentiles must lie strictly between 0 and 100.")
    n_periods = round(config.horizon_years * config.periods_per_year)
    if n_periods < 1:
        raise InvalidInputError("Horizon is shorter than one data period.")
    if n_periods * config.n_paths > MAX_WORK:
        raise InvalidInputError(
            "Simulation too large: reduce the number of paths or the horizon "
            f"(paths x periods must not exceed {MAX_WORK:,})."
        )
    return n_periods


def simulate_parametric(
    config: MonteCarloConfig, annual_expected_return: float, annual_volatility: float
) -> MonteCarloResult:
    """Lognormal simulation from annualised arithmetic moments of the portfolio."""
    if annual_volatility < 0 or not np.isfinite(annual_volatility):
        raise InvalidInputError("Volatility must be a non-negative finite number.")
    p = config.periods_per_year
    m, v = annual_expected_return / p, annual_volatility**2 / p
    a, s = lognormal_parameters(m, v)

    def draw(rng: np.random.Generator, k: int, n: int) -> np.ndarray:
        return rng.normal(a, s, size=(k, n))

    assumptions = (
        "Portfolio rebalanced to target weights every period (constant mix).",
        "Per-period returns are independent and identically lognormally distributed.",
        f"Moments from estimates: expected return {annual_expected_return:.2%} p.a. "
        f"(arithmetic), volatility {annual_volatility:.2%} p.a.",
        "Estimated parameters are treated as known (no parameter uncertainty).",
        "No contributions, withdrawals, fees, taxes or transaction costs.",
    )
    return _run(config, draw, m, np.sqrt(v), assumptions)


def simulate_bootstrap(
    config: MonteCarloConfig, historical_portfolio_returns: np.ndarray
) -> MonteCarloResult:
    """I.i.d. or stationary block bootstrap of historical portfolio returns."""
    hist = np.asarray(historical_portfolio_returns, dtype=float)
    if hist.ndim != 1 or hist.shape[0] < 60:
        raise InsufficientDataError("Bootstrap simulation needs at least 60 historical returns.")
    if not np.isfinite(hist).all() or (hist <= -1).any():
        raise InvalidInputError("Historical returns must be finite and greater than -100%.")
    log_hist = np.log1p(hist)
    t_len = hist.shape[0]
    block = config.method is SimulationMethod.BLOCK_BOOTSTRAP
    p_new = 1.0 / config.mean_block_length
    state: dict[str, np.ndarray] = {}

    def draw(rng: np.random.Generator, k: int, n: int) -> np.ndarray:
        if not block:
            return log_hist[rng.integers(0, t_len, size=(k, n), dtype=np.int32)]
        # Stationary bootstrap, vectorised over the k periods of this step: a new
        # block starts with probability p_new (always at the very first period);
        # otherwise the path continues with the next historical observation.
        starts = rng.integers(0, t_len, size=(k, n), dtype=np.int32)
        new_block = rng.random((k, n)) < p_new
        current = state.get("idx")
        if current is None:
            new_block[0] = True
        rows = np.arange(k)[:, None]
        last = np.maximum.accumulate(np.where(new_block, rows, -1), axis=0)
        from_start = np.take_along_axis(starts, np.maximum(last, 0), axis=0) + (rows - last)
        if current is None:
            idx = from_start % t_len
        else:
            idx = np.where(last >= 0, from_start, current[None, :] + 1 + rows) % t_len
        current = idx[-1]
        state["idx"] = current
        return np.asarray(log_hist[idx])

    label = (
        f"stationary block bootstrap (mean block length {config.mean_block_length:g} periods)"
        if block
        else "i.i.d. bootstrap"
    )
    assumptions = (
        "Portfolio rebalanced to target weights every period (constant mix).",
        f"Returns resampled from {t_len} historical portfolio returns by {label}.",
        "Future return distribution assumed to resemble the historical sample; "
        "scenarios worse than the sample's worst periods cannot occur.",
        "No contributions, withdrawals, fees, taxes or transaction costs.",
    )
    return _run(config, draw, float(hist.mean()), float(hist.std(ddof=1)), assumptions)


def _run(
    config: MonteCarloConfig,
    draw: object,
    per_period_mean: float,
    per_period_vol: float,
    assumptions: tuple[str, ...],
) -> MonteCarloResult:
    n_periods = _validate(config)
    rng = np.random.default_rng(config.seed)
    n = config.n_paths
    step = config.periods_per_step
    pct = tuple(sorted(set(config.percentiles) | {5, 50, 95}))
    n_keep = min(config.n_sample_paths, n)

    log_w = np.zeros(n)
    peak = np.zeros(n)
    mdd = np.zeros(n)
    times = [0.0]
    pct_rows = [np.full(len(pct), config.initial_value)]
    mean_row = [config.initial_value]
    samples = [np.full(n_keep, config.initial_value)]

    done = 0
    while done < n_periods:
        k = min(step, n_periods - done)
        inc = draw(rng, k, n)  # type: ignore[operator]
        path = log_w + np.cumsum(inc, axis=0)
        run_peak = np.maximum(peak, np.maximum.accumulate(path, axis=0))
        mdd = np.minimum(mdd, np.min(np.expm1(path - run_peak), axis=0))
        peak = run_peak[-1]
        log_w = path[-1]
        done += k
        wealth = config.initial_value * np.exp(log_w)
        times.append(done / config.periods_per_year)
        pct_rows.append(np.percentile(wealth, pct))
        mean_row.append(float(wealth.mean()))
        samples.append(wealth[:n_keep].copy())

    terminal = config.initial_value * np.exp(log_w)
    pct_arr = np.vstack(pct_rows)
    term_ret = terminal / config.initial_value - 1.0
    var_q = float(np.quantile(term_ret, 0.05))
    years = n_periods / config.periods_per_year
    cagr = np.exp(log_w / years) - 1.0
    return MonteCarloResult(
        config=config,
        times_years=np.array(times),
        percentile_paths={p: pct_arr[:, i] for i, p in enumerate(pct)},
        mean_path=np.array(mean_row),
        sample_paths=np.vstack(samples).T,
        terminal_values=terminal,
        terminal_percentiles={p: float(np.percentile(terminal, p)) for p in pct},
        probability_of_loss=float(np.mean(terminal < config.initial_value)),
        probability_of_target=(
            None if config.target_value is None else float(np.mean(terminal >= config.target_value))
        ),
        terminal_return_var_95=-var_q,
        terminal_return_cvar_95=float(-term_ret[term_ret <= var_q].mean()),
        cagr_percentiles={p: float(np.percentile(cagr, p)) for p in pct},
        max_drawdown_percentiles={p: float(np.percentile(mdd, p)) for p in pct},
        per_period_mean=per_period_mean,
        per_period_volatility=per_period_vol,
        assumptions=assumptions,
    )
