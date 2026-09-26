import numpy as np
import pytest

from ardentum.quant.attribution import (
    brinson_fachler,
    brinson_fachler_period,
    carino_link,
    contributions,
)
from ardentum.quant.errors import InvalidInputError


def test_carino_linked_contributions_sum_to_compounded_return() -> None:
    rng = np.random.default_rng(0)
    w = rng.dirichlet(np.ones(4), size=60)
    r = rng.normal(0.005, 0.04, size=(60, 4))
    c = contributions(w, r)
    port = c.sum(axis=1)
    linked = carino_link(c, port)
    assert linked.sum() == pytest.approx(np.prod(1 + port) - 1, abs=1e-12)


def test_carino_handles_zero_return_periods() -> None:
    c = np.array([[0.0, 0.0], [0.05, 0.05]])
    port = c.sum(axis=1)
    linked = carino_link(c, port)
    assert linked.sum() == pytest.approx(0.1)
    np.testing.assert_allclose(linked, [0.05, 0.05])


def test_carino_single_period_is_identity() -> None:
    c = np.array([[0.02, -0.01, 0.03]])
    np.testing.assert_allclose(carino_link(c, c.sum(axis=1)), c[0])


def test_carino_rejects_inconsistent_effects() -> None:
    with pytest.raises(InvalidInputError):
        carino_link(np.array([[0.01, 0.01]]), np.array([0.05]))


def test_brinson_fachler_single_period_textbook_example() -> None:
    # Two sectors. Portfolio overweights sector 0, which outperforms.
    wp, wb = np.array([0.7, 0.3]), np.array([0.5, 0.5])
    rp, rb = np.array([0.10, 0.02]), np.array([0.08, 0.03])
    alloc, sel, inter = brinson_fachler_period(wp, wb, rp, rb)
    total_b = 0.5 * 0.08 + 0.5 * 0.03  # 5.5%
    np.testing.assert_allclose(alloc, [0.2 * (0.08 - total_b), -0.2 * (0.03 - total_b)])
    np.testing.assert_allclose(sel, [0.5 * 0.02, 0.5 * -0.01])
    np.testing.assert_allclose(inter, [0.2 * 0.02, -0.2 * -0.01])
    rp_total = 0.7 * 0.10 + 0.3 * 0.02
    assert alloc.sum() + sel.sum() + inter.sum() == pytest.approx(rp_total - total_b)


def test_brinson_fachler_missing_sector_convention() -> None:
    wp, wb = np.array([1.0, 0.0]), np.array([0.5, 0.5])
    rp, rb = np.array([0.05, 0.0]), np.array([0.04, 0.10])
    a, s, i = brinson_fachler_period(wp, wb, rp, rb)
    assert a.sum() + s.sum() + i.sum() == pytest.approx(0.05 - 0.07)


def test_multi_period_brinson_links_to_active_return() -> None:
    rng = np.random.default_rng(3)
    tickers = ["A", "B", "C", "D", "E"]
    sectors = {"A": "Tech", "B": "Tech", "C": "Energy", "D": "Health", "E": "Health"}
    t = 36
    wp = rng.dirichlet(np.ones(5), size=t)
    wp[:, 2] = 0.0  # portfolio avoids Energy entirely
    wp /= wp.sum(axis=1, keepdims=True)
    wb = np.full((t, 5), 0.2)
    r = rng.normal(0.01, 0.05, size=(t, 5))
    res = brinson_fachler(tickers, sectors, wp, wb, r)
    port = (wp * r).sum(axis=1)
    bench = (wb * r).sum(axis=1)
    active = np.prod(1 + port) - np.prod(1 + bench)
    assert res.total == pytest.approx(active, abs=1e-12)
    assert res.sectors == ("Energy", "Health", "Tech")
    assert res.portfolio_weights[0] == 0.0
