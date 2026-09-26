"""Performance attribution.

Contribution to return
    Over one period, asset ``i`` contributes ``c_{t,i} = w_{t-1,i} r_{t,i}`` where
    ``w_{t-1}`` are the weights held at the *start* of the period; contributions
    sum to the portfolio's gross return for that period.

Multi-period linking (Carino 1999, "Combining Attribution Effects Over Time",
Journal of Performance Measurement 3(4))
    Arithmetic contributions do not add up to a compounded return. Carino scales
    each period's effects by ``k_t / K`` with ``k_t = ln(1 + R_t) / R_t`` and
    ``K = ln(1 + R) / R`` (``R`` = total compounded return). For active returns
    ``k_t = [ln(1 + R_t) - ln(1 + B_t)] / (R_t - B_t)``. Linked effects then sum
    exactly to the total (active) compounded return.

Brinson-Fachler (1985) sector attribution
    ``allocation_j  = (wp_j - wb_j)(rb_j - Rb)``
    ``selection_j   = wb_j (rp_j - rb_j)``
    ``interaction_j = (wp_j - wb_j)(rp_j - rb_j)``
    which sum over sectors to ``Rp - Rb``. When a sector is absent from the
    portfolio (benchmark) its portfolio (benchmark) sector return is set equal to
    the other side's, the standard convention that keeps the identity exact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ardentum.quant.errors import InvalidInputError


def _log_ratio(r: np.ndarray | float) -> np.ndarray:
    """``ln(1 + r) / r`` with the limit 1 at ``r = 0``."""
    r = np.asarray(r, dtype=float)
    out = np.ones_like(r)
    nz = np.abs(r) > 1e-12
    out[nz] = np.log1p(r[nz]) / r[nz]
    return out


def _active_log_ratio(r: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``[ln(1+r) - ln(1+b)] / (r - b)`` with the limit ``1 / (1 + r)`` when equal."""
    r = np.asarray(r, dtype=float)
    b = np.asarray(b, dtype=float)
    diff = r - b
    out = 1.0 / (1.0 + r)
    nz = np.abs(diff) > 1e-12
    out[nz] = (np.log1p(r[nz]) - np.log1p(b[nz])) / diff[nz]
    return out


def carino_link(
    period_effects: np.ndarray,
    portfolio_returns: np.ndarray,
    benchmark_returns: np.ndarray | None = None,
) -> np.ndarray:
    """Link per-period effects (T x K) into K total effects.

    Without a benchmark, effects must sum per period to ``portfolio_returns`` and
    the linked effects sum to the compounded portfolio return. With a benchmark,
    effects must sum to the active return ``R_t - B_t`` and the linked effects
    sum to ``prod(1 + R) - prod(1 + B)``.
    """
    e = np.atleast_2d(np.asarray(period_effects, dtype=float))
    r = np.asarray(portfolio_returns, dtype=float)
    if e.shape[0] != r.shape[0]:
        raise InvalidInputError("Effects and returns must have the same number of periods.")
    total_r = float(np.prod(1.0 + r) - 1.0)
    if benchmark_returns is None:
        target = r
        k_t = _log_ratio(r)
        k = float(_log_ratio(np.array([total_r]))[0])
    else:
        b = np.asarray(benchmark_returns, dtype=float)
        if b.shape != r.shape:
            raise InvalidInputError("Benchmark returns must align with portfolio returns.")
        target = r - b
        total_b = float(np.prod(1.0 + b) - 1.0)
        k_t = _active_log_ratio(r, b)
        k = float(_active_log_ratio(np.array([total_r]), np.array([total_b]))[0])
    if not np.allclose(e.sum(axis=1), target, atol=1e-10):
        raise InvalidInputError("Per-period effects must sum to the period (active) return.")
    return np.asarray((k_t / k) @ e, dtype=float)


def contributions(weights_start: np.ndarray, asset_returns: np.ndarray) -> np.ndarray:
    """Per-period contributions ``w_{t-1,i} r_{t,i}`` (T x N)."""
    w = np.asarray(weights_start, dtype=float)
    r = np.asarray(asset_returns, dtype=float)
    if w.shape != r.shape:
        raise InvalidInputError("Weights and returns must have the same shape.")
    return np.asarray(w * r, dtype=float)


@dataclass(frozen=True)
class BrinsonResult:
    sectors: tuple[str, ...]
    allocation: np.ndarray
    selection: np.ndarray
    interaction: np.ndarray
    portfolio_weights: np.ndarray  # average start-of-period sector weights
    benchmark_weights: np.ndarray

    @property
    def total(self) -> float:
        return float(self.allocation.sum() + self.selection.sum() + self.interaction.sum())


def _sector_matrix(
    tickers: Sequence[str], sectors: Mapping[str, str]
) -> tuple[tuple[str, ...], np.ndarray]:
    missing = [t for t in tickers if not sectors.get(t)]
    if missing:
        raise InvalidInputError(
            "Sector attribution needs a sector for every asset: " + ", ".join(missing)
        )
    names = tuple(sorted({sectors[t] for t in tickers}))
    m = np.array([[1.0 if sectors[t] == s else 0.0 for s in names] for t in tickers])
    return names, m


def brinson_fachler_period(
    wp: np.ndarray, wb: np.ndarray, rp: np.ndarray, rb: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Single-period Brinson-Fachler effects by sector given sector weights/returns."""
    wp, wb, rp, rb = (np.asarray(x, dtype=float) for x in (wp, wb, rp, rb))
    rp = np.where(wp > 1e-12, rp, rb)
    rb = np.where(wb > 1e-12, rb, rp)
    total_b = float(wb @ rb)
    alloc = (wp - wb) * (rb - total_b)
    select = wb * (rp - rb)
    inter = (wp - wb) * (rp - rb)
    return alloc, select, inter


def brinson_fachler(
    tickers: Sequence[str],
    sectors: Mapping[str, str],
    portfolio_weights: np.ndarray,
    benchmark_weights: np.ndarray,
    asset_returns: np.ndarray,
) -> BrinsonResult:
    """Multi-period Brinson-Fachler attribution, Carino-linked.

    ``portfolio_weights`` and ``benchmark_weights`` are start-of-period asset
    weights (T x N); ``asset_returns`` are the period returns (T x N). Linked
    effects sum to the compounded gross active return.
    """
    names, m = _sector_matrix(tickers, sectors)
    wp_a = np.asarray(portfolio_weights, dtype=float)
    wb_a = np.asarray(benchmark_weights, dtype=float)
    r_a = np.asarray(asset_returns, dtype=float)
    if not (wp_a.shape == wb_a.shape == r_a.shape):
        raise InvalidInputError("Weights and returns must have identical shapes.")
    t_len, k = r_a.shape[0], len(names)
    alloc = np.zeros((t_len, k))
    select = np.zeros((t_len, k))
    inter = np.zeros((t_len, k))
    wp_s = wp_a @ m
    wb_s = wb_a @ m
    with np.errstate(divide="ignore", invalid="ignore"):
        rp_s = np.where(wp_s > 1e-12, ((wp_a * r_a) @ m) / wp_s, 0.0)
        rb_s = np.where(wb_s > 1e-12, ((wb_a * r_a) @ m) / wb_s, 0.0)
    for t in range(t_len):
        alloc[t], select[t], inter[t] = brinson_fachler_period(wp_s[t], wb_s[t], rp_s[t], rb_s[t])
    port = (wp_a * r_a).sum(axis=1)
    bench = (wb_a * r_a).sum(axis=1)
    effects = np.hstack([alloc, select, inter])
    linked = carino_link(effects, port, bench)
    return BrinsonResult(
        sectors=names,
        allocation=linked[:k],
        selection=linked[k : 2 * k],
        interaction=linked[2 * k :],
        portfolio_weights=wp_s.mean(axis=0),
        benchmark_weights=wb_s.mean(axis=0),
    )
