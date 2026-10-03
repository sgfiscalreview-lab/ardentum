"""Trade list: the trades that turn current holdings into target weights.

With holdings ``h_i`` (money values), new money ``c`` (negative to withdraw), target
weights ``w_i`` and a trading cost of ``k`` per unit traded, paid out of the portfolio, the
value left invested after trading, ``V``, solves

    V = sum_i h_i + c - k sum_i |w_i V - h_i|

and the trades are ``t_i = w_i V - h_i`` (positive to buy). The right-hand side minus
``V`` falls strictly as ``V`` rises when ``k sum_i |w_i| < 1``, so the solution is unique;
it is found by bracketing root search and checked against the identity afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError, SolverError

MAX_COST_RATE = 0.05  # 500 basis points


@dataclass(frozen=True)
class TradeList:
    current: np.ndarray  # h_i
    target_weights: np.ndarray  # w_i
    target_values: np.ndarray  # w_i V
    trades: np.ndarray  # t_i = w_i V - h_i (positive: buy)
    costs: np.ndarray  # k |t_i|
    value_before: float  # sum h_i
    new_money: float  # c
    value_after: float  # V
    total_costs: float

    @property
    def current_weights(self) -> np.ndarray | None:
        """Each holding's share of the current value (None when nothing is held)."""
        if self.value_before <= 0.0:
            return None
        return self.current / self.value_before

    @property
    def bought(self) -> float:
        return float(self.trades[self.trades > 0].sum())

    @property
    def sold(self) -> float:
        return float(-self.trades[self.trades < 0].sum())


def trade_list(
    current: np.ndarray, target_weights: np.ndarray, new_money: float = 0.0, cost_rate: float = 0.0
) -> TradeList:
    h = np.asarray(current, dtype=float)
    w = np.asarray(target_weights, dtype=float)
    if h.shape != w.shape or h.ndim != 1 or h.size == 0:
        raise InvalidInputError("Holdings and target weights must list the same assets.")
    if not (np.isfinite(h).all() and np.isfinite(w).all() and np.isfinite(new_money)):
        raise InvalidInputError("Holdings, weights and new money must be finite numbers.")
    if (h < 0).any():
        raise InvalidInputError("Current holdings must be zero or positive amounts.")
    if abs(w.sum() - 1.0) > 1e-6:
        raise InvalidInputError(f"Target weights must sum to 1 (got {w.sum():.6f}).")
    if not 0.0 <= cost_rate <= MAX_COST_RATE:
        raise InvalidInputError("Trading costs must be between 0 and 500 basis points.")
    if cost_rate * np.abs(w).sum() >= 1.0:
        raise InvalidInputError("Trading costs are too high for this much leverage.")
    total = float(h.sum() + new_money)

    def gap(v: float) -> float:
        return total - cost_rate * float(np.abs(w * v - h).sum()) - v

    if gap(0.0) < 0.0:
        # Selling everything costs k * sum h; nothing is left to invest.
        most = float(h.sum() - cost_rate * h.sum())
        raise InfeasibleProblemError(
            f"Withdrawing {-new_money:,.2f} leaves nothing after trading costs; "
            f"withdraw at most {most:,.2f}."
        )
    if total <= 0.0:
        v = 0.0
    else:
        v = float(brentq(gap, 0.0, total, xtol=1e-12 * max(total, 1.0), rtol=1e-15, maxiter=200))
    target = w * v
    trades = target - h
    costs = cost_rate * np.abs(trades)
    if abs(v + costs.sum() - total) > 1e-9 * max(total, 1.0):
        raise SolverError("The trade list does not balance; please report this.")
    return TradeList(
        current=h,
        target_weights=w,
        target_values=target,
        trades=trades,
        costs=costs,
        value_before=float(h.sum()),
        new_money=float(new_money),
        value_after=v,
        total_costs=float(costs.sum()),
    )
