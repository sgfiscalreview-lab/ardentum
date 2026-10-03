"""Trade list against closed forms and the cash identity it must satisfy."""

from __future__ import annotations

import numpy as np
import pytest

from ardentum.quant.errors import InfeasibleProblemError, InvalidInputError
from ardentum.quant.trades import trade_list


def test_without_costs_trades_are_target_minus_current() -> None:
    h = np.array([5000.0, 3000.0, 2000.0, 0.0])
    w = np.array([0.25, 0.25, 0.25, 0.25])
    tl = trade_list(h, w, new_money=2000.0)
    assert tl.value_after == pytest.approx(12000.0, rel=1e-14)
    assert tl.trades == pytest.approx([-2000.0, 0.0, 1000.0, 3000.0], abs=1e-9)
    assert tl.total_costs == 0.0
    assert tl.bought - tl.sold == pytest.approx(2000.0, rel=1e-12)


def test_costs_closed_form_when_every_trade_is_a_buy() -> None:
    # All new money, starting from nothing: V = c - k V, so V = c / (1 + k).
    w = np.array([0.6, 0.4])
    tl = trade_list(np.zeros(2), w, new_money=10_000.0, cost_rate=0.001)
    assert tl.value_after == pytest.approx(10_000.0 / 1.001, rel=1e-13)
    assert tl.total_costs == pytest.approx(10_000.0 - 10_000.0 / 1.001, rel=1e-10)


def test_costs_closed_form_for_a_switch() -> None:
    # Hold 100% A, move to 100% B with no new money: V = H - k (H + V), V = H (1-k)/(1+k).
    tl = trade_list(np.array([1000.0, 0.0]), np.array([0.0, 1.0]), cost_rate=0.01)
    assert tl.value_after == pytest.approx(1000.0 * 0.99 / 1.01, rel=1e-13)
    assert tl.trades[0] == pytest.approx(-1000.0, rel=1e-13)


@pytest.mark.parametrize("seed", range(5))
def test_cash_balances_and_weights_hit_the_target(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n = 8
    h = rng.uniform(0, 5000, n)
    w = rng.dirichlet(np.ones(n))
    c = float(rng.uniform(-2000, 2000))
    k = float(rng.uniform(0, 0.01))
    tl = trade_list(h, w, new_money=c, cost_rate=k)
    # What is sold plus new money pays for what is bought plus every cost.
    assert tl.sold + c == pytest.approx(tl.bought + tl.total_costs, rel=1e-10, abs=1e-8)
    after = h + tl.trades
    assert after / after.sum() == pytest.approx(w, rel=1e-10, abs=1e-14)
    assert tl.costs == pytest.approx(k * np.abs(tl.trades), rel=1e-14)


def test_withdrawing_too_much_says_how_much_is_possible() -> None:
    with pytest.raises(InfeasibleProblemError, match=r"withdraw at most 9,950.00"):
        trade_list(
            np.array([6000.0, 4000.0]), np.array([0.5, 0.5]), new_money=-10_000.0, cost_rate=0.005
        )
    # Withdrawing everything with no costs leaves an empty portfolio.
    tl = trade_list(np.array([6000.0, 4000.0]), np.array([0.5, 0.5]), new_money=-10_000.0)
    assert tl.value_after == 0.0
    assert tl.trades == pytest.approx([-6000.0, -4000.0])


def test_bad_inputs_are_refused() -> None:
    with pytest.raises(InvalidInputError, match="sum to 1"):
        trade_list(np.array([1.0, 1.0]), np.array([0.5, 0.4]))
    with pytest.raises(InvalidInputError, match="zero or positive"):
        trade_list(np.array([-1.0, 1.0]), np.array([0.5, 0.5]))
    with pytest.raises(InvalidInputError, match="500 basis points"):
        trade_list(np.array([1.0, 1.0]), np.array([0.5, 0.5]), cost_rate=0.06)
    with pytest.raises(InvalidInputError, match="same assets"):
        trade_list(np.array([1.0]), np.array([0.5, 0.5]))
