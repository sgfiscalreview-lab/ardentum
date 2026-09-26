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

Cash flows
----------
Optional regular contributions (positive) or withdrawals (negative) of
``annual_cash_flow / cash_flows_per_year`` are made at the end of every
``round(periods_per_year / cash_flows_per_year)`` periods, growing at
``cash_flow_growth`` per year (e.g. inflation indexation): the flow at time ``t``
years is ``(A / f)(1 + g)^(t - 1/f)``. Wealth evolves as
``W <- W (1 + r)`` each period and ``W <- W + CF`` on flow dates. A path whose
wealth cannot cover a withdrawal is **depleted**: its wealth becomes zero and
stays zero. With deterministic returns this reproduces the annuity closed form
``W_n = W_0 G^n + C (G^n - 1) / (G - 1)`` (tested).

Growth rates, drawdowns and terminal VaR/CVaR describe the portfolio's
time-weighted return (they are unaffected by cash flows); wealth percentiles,
target and depletion probabilities include the cash flows. With cash flows,
"loss" means ending with less than the initial value plus net contributions.

Limitations: no parameter uncertainty (estimates are treated as true), no taxes
or transaction costs, and history-based methods cannot generate scenarios worse
than the historical sample's worst periods.
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
    annual_cash_flow: float = 0.0  # + contributions / - withdrawals, per year
    cash_flows_per_year: int = 12
    cash_flow_growth: float = 0.0  # annual growth of the flows

    @property
    def has_cash_flows(self) -> bool:
        return self.annual_cash_flow != 0.0

    @property
    def cash_flow_interval(self) -> int:
        """Data periods between cash flows."""
        return max(1, round(self.periods_per_year / max(1, self.cash_flows_per_year)))

    def cash_flow_at(self, t_years: float) -> float:
        f = self.periods_per_year / self.cash_flow_interval
        return float(
            (self.annual_cash_flow / f) * (1.0 + self.cash_flow_growth) ** (t_years - 1.0 / f)
        )


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
    net_cash_flow: float = 0.0  # sum of all scheduled flows (before any depletion)
    probability_of_depletion: float | None = None  # None unless there are withdrawals
    depletion_years_percentiles: dict[int, float] | None = None  # among depleted paths

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
    if not 1 <= config.cash_flows_per_year <= config.periods_per_year:
        raise InvalidInputError(
            "Cash flows per year must be between 1 and the number of data periods per year."
        )
    if not np.isfinite(config.annual_cash_flow):
        raise InvalidInputError("Cash flow must be a finite number.")
    if not -0.5 < config.cash_flow_growth <= 0.5:
        raise InvalidInputError("Cash-flow growth must be between -50% and 50% per year.")
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
        *_flow_assumptions(config),
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
        *_flow_assumptions(config),
    )
    return _run(config, draw, float(hist.mean()), float(hist.std(ddof=1)), assumptions)


def _flow_assumptions(config: MonteCarloConfig) -> tuple[str, ...]:
    if not config.has_cash_flows:
        return ("No contributions, withdrawals, fees, taxes or transaction costs.",)
    kind = "Contributions" if config.annual_cash_flow > 0 else "Withdrawals"
    f = config.periods_per_year / config.cash_flow_interval
    growth = (
        f", growing {config.cash_flow_growth:.2%} per year"
        if config.cash_flow_growth
        else ", not indexed"
    )
    out = [
        f"{kind} of {abs(config.annual_cash_flow):,.2f} per year in {f:g} equal instalments "
        f"at the end of each interval{growth}.",
        "No fees, taxes or transaction costs.",
    ]
    if config.annual_cash_flow < 0:
        out.append("A path is depleted when its wealth cannot cover a withdrawal; it stays at 0.")
    return tuple(out)


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
    ppy = config.periods_per_year
    flows = config.has_cash_flows
    interval = config.cash_flow_interval

    log_w = np.zeros(n)  # log of the time-weighted return index
    wealth = np.full(n, config.initial_value)
    depleted_at = np.full(n, np.nan)
    net_flow = 0.0
    peak = np.zeros(n)
    mdd = np.zeros(n)
    times = [0.0]
    pct_rows = [np.full(len(pct), config.initial_value)]
    mean_row = [config.initial_value]
    samples = [np.full(n_keep, config.initial_value)]

    done = 0
    next_report = step
    next_flow = interval if flows else n_periods + 1
    while done < n_periods:
        k = min(next_report, next_flow, n_periods) - done
        inc = draw(rng, k, n)  # type: ignore[operator]
        cum = np.cumsum(inc, axis=0)
        path = log_w + cum
        run_peak = np.maximum(peak, np.maximum.accumulate(path, axis=0))
        mdd = np.minimum(mdd, np.min(np.expm1(path - run_peak), axis=0))
        peak = run_peak[-1]
        log_w = path[-1]
        done += k
        if flows:
            wealth = wealth * np.exp(cum[-1])
            if done == next_flow:
                cf = config.cash_flow_at(done / ppy)
                net_flow += cf
                alive = np.isnan(depleted_at)
                wealth = np.where(alive, wealth + cf, 0.0)
                newly = alive & (wealth <= 0.0)
                depleted_at[newly] = done / ppy
                wealth[newly] = 0.0
                next_flow += interval
        else:
            wealth = config.initial_value * np.exp(log_w)
        if done in (next_report, n_periods):
            times.append(done / ppy)
            pct_rows.append(np.percentile(wealth, pct))
            mean_row.append(float(wealth.mean()))
            samples.append(wealth[:n_keep].copy())
            next_report = done + step

    terminal = wealth
    pct_arr = np.vstack(pct_rows)
    term_ret = np.expm1(log_w)  # time-weighted
    var_q = float(np.quantile(term_ret, 0.05))
    years = n_periods / ppy
    cagr = np.exp(log_w / years) - 1.0
    withdrawals = flows and config.annual_cash_flow < 0
    dep = depleted_at[~np.isnan(depleted_at)]
    return MonteCarloResult(
        config=config,
        times_years=np.array(times),
        percentile_paths={p: pct_arr[:, i] for i, p in enumerate(pct)},
        mean_path=np.array(mean_row),
        sample_paths=np.vstack(samples).T,
        terminal_values=terminal,
        terminal_percentiles={p: float(np.percentile(terminal, p)) for p in pct},
        probability_of_loss=float(np.mean(terminal < config.initial_value + net_flow)),
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
        net_cash_flow=net_flow,
        probability_of_depletion=float(dep.size / n) if withdrawals else None,
        depletion_years_percentiles=(
            {p: float(np.percentile(dep, p)) for p in (10, 50, 90)} if dep.size else None
        ),
    )
