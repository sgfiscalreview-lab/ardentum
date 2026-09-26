import numpy as np
import pandas as pd
import pytest

from ardentum.quant.errors import InsufficientDataError, InvalidInputError
from ardentum.quant.frequency import Frequency, infer_frequency
from ardentum.quant.returns import (
    annual_rate_to_periodic,
    annualised_return,
    cagr,
    log_returns,
    log_to_simple,
    simple_returns,
    simple_to_log,
    total_return,
    wealth_index,
)


def _prices(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.bdate_range("2024-01-01", periods=len(values)), name="X")


def test_simple_returns_known_values() -> None:
    r = simple_returns(_prices([100.0, 110.0, 99.0]))
    np.testing.assert_allclose(r.to_numpy(), [0.10, -0.10])
    assert len(r) == 2  # first observation dropped, never zero-filled


def test_log_returns_known_values() -> None:
    r = log_returns(_prices([100.0, 110.0, 99.0]))
    np.testing.assert_allclose(r.to_numpy(), [np.log(1.1), np.log(0.9)])


def test_log_simple_round_trip() -> None:
    r = np.array([0.1, -0.5, 0.0, 2.0])
    np.testing.assert_allclose(log_to_simple(simple_to_log(r)), r)


def test_log_returns_sum_to_total_log_return() -> None:
    p = _prices([50.0, 55.0, 40.0, 80.0])
    assert log_returns(p).sum() == pytest.approx(np.log(80.0 / 50.0))


def test_simple_to_log_rejects_total_loss() -> None:
    with pytest.raises(InvalidInputError):
        simple_to_log(np.array([-1.0]))


@pytest.mark.parametrize(
    "values",
    [[100.0, np.nan, 101.0], [100.0, 0.0, 101.0], [100.0, -5.0], [100.0, np.inf]],
)
def test_invalid_prices_raise(values: list[float]) -> None:
    with pytest.raises(InvalidInputError):
        simple_returns(_prices(values))


def test_unsorted_dates_raise() -> None:
    p = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-02", "2024-01-01"]))
    with pytest.raises(InvalidInputError):
        simple_returns(p)


def test_single_price_raises() -> None:
    with pytest.raises(InsufficientDataError):
        simple_returns(_prices([100.0]))


def test_dataframe_returns_preserve_columns() -> None:
    idx = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"A": [1.0, 2.0, 4.0], "B": [10.0, 5.0, 5.0]}, index=idx)
    r = simple_returns(prices)
    assert list(r.columns) == ["A", "B"]
    np.testing.assert_allclose(r.to_numpy(), [[1.0, -0.5], [1.0, 0.0]])


def test_wealth_index_prepends_initial_value() -> None:
    np.testing.assert_allclose(wealth_index(np.array([0.1, -0.1]), 100.0), [100.0, 110.0, 99.0])


def test_total_return() -> None:
    assert total_return(np.array([0.1, -0.1])) == pytest.approx(-0.01)


def test_cagr_monthly_one_percent() -> None:
    r = np.full(12, 0.01)
    assert cagr(r, 12) == pytest.approx(1.01**12 - 1)


def test_cagr_two_years_doubling() -> None:
    # 24 monthly returns compounding to exactly 2x: CAGR = sqrt(2) - 1.
    r = np.full(24, 2.0 ** (1 / 24) - 1)
    assert cagr(r, 12) == pytest.approx(np.sqrt(2.0) - 1.0)


def test_cagr_total_loss() -> None:
    assert cagr(np.array([0.5, -1.0]), 12) == -1.0


def test_arithmetic_annualisation() -> None:
    r = np.array([0.01, 0.03])
    assert annualised_return(r, 12, method="arithmetic") == pytest.approx(0.24)


def test_arithmetic_exceeds_geometric_for_volatile_series() -> None:
    r = np.array([0.2, -0.15, 0.1, -0.05] * 10)
    assert annualised_return(r, 12, method="arithmetic") > annualised_return(r, 12)


def test_unknown_method_raises() -> None:
    with pytest.raises(InvalidInputError):
        annualised_return(np.array([0.1]), 12, method="harmonic")


def test_annual_rate_to_periodic_compounds_back() -> None:
    per = annual_rate_to_periodic(0.05, 252)
    assert (1 + per) ** 252 == pytest.approx(1.05)


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (pd.bdate_range("2024-01-01", periods=30), Frequency.DAILY),
        (pd.date_range("2024-01-05", periods=30, freq="W-FRI"), Frequency.WEEKLY),
        (pd.date_range("2020-01-31", periods=30, freq="ME"), Frequency.MONTHLY),
        (pd.date_range("2000-03-31", periods=30, freq="QE"), Frequency.QUARTERLY),
        (pd.date_range("1990-12-31", periods=30, freq="YE"), Frequency.ANNUAL),
    ],
)
def test_infer_frequency(index: pd.DatetimeIndex, expected: Frequency) -> None:
    assert infer_frequency(index) is expected


def test_periods_per_year() -> None:
    assert Frequency.DAILY.periods_per_year == 252
    assert Frequency.MONTHLY.periods_per_year == 12
