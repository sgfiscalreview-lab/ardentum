"""Crisis replay (buy and hold through a period) against closed forms, a brute-force
share-count calculation and the existing drawdown and buy-and-hold functions."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from ardentum.data.crises import EPISODES
from ardentum.quant.errors import InvalidInputError
from ardentum.quant.metrics import max_drawdown
from ardentum.quant.portfolio import buy_and_hold_returns
from ardentum.quant.stress import PeriodNotCoveredError, period_return, replay, require_daily


def _returns(
    values: np.ndarray, start: str = "2020-01-01", cols: list[str] | None = None
) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(values))
    v = np.asarray(values, dtype=float)
    if v.ndim == 1:
        v = v[:, None]
    return pd.DataFrame(v, index=idx, columns=cols or [f"A{i}" for i in range(v.shape[1])])


def test_constant_returns_have_closed_forms() -> None:
    # Two assets with constant daily returns a and b: V_t = w (1+a)^t + (1-w)(1+b)^t.
    n = 40
    a, b, w = 0.01, -0.02, 0.3
    rets = _returns(np.column_stack([np.full(n, a), np.full(n, b)]))
    start, end = rets.index[4].date(), rets.index[24].date()
    res = replay(rets, np.array([w, 1 - w]), start, end)
    t = np.arange(21)
    expected = w * (1 + a) ** t + (1 - w) * (1 + b) ** t
    assert res.value == pytest.approx(expected, rel=1e-12)
    assert res.total_return == pytest.approx(expected[-1] - 1, rel=1e-12)
    assert res.asset_returns == pytest.approx([(1 + a) ** 20 - 1, (1 + b) ** 20 - 1], rel=1e-12)
    assert res.dates[0].date() == start
    assert res.dates[-1].date() == end
    # Falls every day: the low is the last day and the drawdown is the total return.
    assert res.max_drawdown == pytest.approx(res.total_return, rel=1e-12)
    assert res.trough_date == end
    assert res.recovery_date is None  # keeps falling to the end of the data


def test_contributions_add_up_and_match_a_share_count_calculation() -> None:
    rng = np.random.default_rng(3)
    rets = _returns(rng.normal(0.0003, 0.015, size=(300, 4)))
    w = np.array([0.4, 0.3, 0.2, 0.1])
    start, end = rets.index[50].date(), rets.index[180].date()
    res = replay(rets, w, start, end)
    assert res.contributions.sum() == pytest.approx(res.total_return, abs=1e-14)

    # Brute force: buy shares at the start price, value them each day.
    prices = (1 + rets).cumprod() * 100
    base = prices.loc[pd.Timestamp(start)]
    shares = w / base.to_numpy()
    window = prices.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    brute = window.to_numpy() @ shares
    assert res.value == pytest.approx(brute, rel=1e-12)

    # The same path from the existing buy-and-hold function.
    inside = rets.loc[(rets.index > pd.Timestamp(start)) & (rets.index <= pd.Timestamp(end))]
    bh = buy_and_hold_returns(inside, w).to_numpy()
    assert res.period_returns == pytest.approx(bh, rel=1e-12, abs=1e-15)
    assert res.worst_period_return == pytest.approx(bh.min(), rel=1e-12)
    assert res.worst_period_date == inside.index[int(np.argmin(bh))].date()
    assert res.max_drawdown == pytest.approx(max_drawdown(bh).max_drawdown, rel=1e-12)


def test_recovery_uses_later_data_without_trading() -> None:
    # Falls 10% a day for 3 days, then rises 5% a day.
    r = np.concatenate([np.full(3, -0.10), np.full(20, 0.05)])
    rets = _returns(r, start="2021-03-01")
    start = (rets.index[0] - pd.offsets.BDay(1)).date()  # bought the business day before
    with pytest.raises(PeriodNotCoveredError, match="begins after this period started"):
        replay(rets, np.array([1.0]), start, rets.index[5].date())
    res = replay(rets, np.array([1.0]), rets.index[0].date(), rets.index[4].date())
    # Bought at the close of day 0 (already down 10%): falls on days 1-2, rises 3-4.
    assert res.trough_date == rets.index[2].date()
    assert res.max_drawdown == pytest.approx(0.81 - 1, rel=1e-12)
    # Back at 1.0: 0.81 * 1.05^k >= 1 for k >= 5 (1.05^5 = 1.276), i.e. index 2 + 5 = 7.
    assert res.recovery_date == rets.index[7].date()
    md = max_drawdown(rets.iloc[1:, 0].to_numpy())
    assert md.recovery_position is not None
    assert rets.index[md.recovery_position].date() == res.recovery_date


def test_a_rising_period_has_no_low_and_no_recovery() -> None:
    rets = _returns(np.full(30, 0.001))
    res = replay(rets, np.array([1.0]), rets.index[3].date(), rets.index[20].date())
    assert res.max_drawdown == 0.0
    assert res.trough_date is None
    assert res.recovery_date is None
    assert period_return(rets.iloc[:, 0], rets.index[3].date(), rets.index[20].date()) == (
        pytest.approx(1.001**17 - 1, rel=1e-12)
    )


def test_uses_nothing_before_the_purchase() -> None:
    rng = np.random.default_rng(5)
    rets = _returns(rng.normal(0, 0.01, size=(120, 2)))
    start, end = rets.index[60].date(), rets.index[100].date()
    a = replay(rets, np.array([0.5, 0.5]), start, end)
    changed = rets.copy()
    changed.iloc[:61] = rng.normal(0, 0.05, size=(61, 2))  # everything up to the purchase
    b = replay(changed, np.array([0.5, 0.5]), start, end)
    assert a.value == pytest.approx(b.value, rel=1e-14)


def test_start_on_a_holiday_buys_at_the_previous_close() -> None:
    rets = _returns(np.full(30, 0.002))
    friday = next(i for i, d in enumerate(rets.index) if d.dayofweek == 4)
    saturday = (rets.index[friday] + pd.Timedelta(days=1)).date()
    res = replay(rets, np.array([1.0]), saturday, rets.index[15].date())
    assert res.dates[0] == rets.index[friday]


def test_periods_the_data_does_not_cover_say_why() -> None:
    rets = _returns(np.full(30, 0.001), start="2020-06-01")
    w = np.array([1.0])
    with pytest.raises(PeriodNotCoveredError, match="can be bought is 2020-06-01"):
        replay(rets, w, dt.date(2020, 2, 19), dt.date(2020, 7, 1))
    with pytest.raises(PeriodNotCoveredError, match="data ends"):
        replay(rets, w, dt.date(2020, 6, 10), dt.date(2021, 1, 1))
    gappy = rets.drop(rets.index[5:20])
    with pytest.raises(PeriodNotCoveredError, match="week before"):
        replay(gappy, w, rets.index[17].date(), rets.index[25].date())
    with pytest.raises(InvalidInputError, match="start before it ends"):
        replay(rets, w, dt.date(2020, 6, 10), dt.date(2020, 6, 10))


def test_insolvent_short_portfolios_are_refused() -> None:
    rets = _returns(np.column_stack([np.full(10, 0.2), np.full(10, 0.0)]))
    with pytest.raises(InvalidInputError, match="stays solvent"):
        replay(rets, np.array([-1.0, 2.0]), rets.index[0].date(), rets.index[9].date())


def test_daily_prices_are_required() -> None:
    monthly = pd.DataFrame(
        {"A": np.full(24, 0.01)}, index=pd.date_range("2020-01-31", periods=24, freq="ME")
    )
    with pytest.raises(InvalidInputError, match="monthly prices"):
        require_daily(monthly)
    require_daily(_returns(np.full(10, 0.0)))


def test_episode_catalogue_is_consistent() -> None:
    keys = [e.key for e in EPISODES]
    assert len(set(keys)) == len(keys)
    starts = [e.start for e in EPISODES]
    assert starts == sorted(starts)
    for e in EPISODES:
        assert e.start < e.end
        assert e.start >= dt.date(1926, 7, 1)  # first day of the Kenneth French daily data
        assert "\u2014" not in e.summary
        assert "\u2014" not in e.name
