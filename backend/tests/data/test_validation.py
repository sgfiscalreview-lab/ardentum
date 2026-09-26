import numpy as np
import pandas as pd
import pytest

from ardentum.data.validation import MAX_FILL, align_prices
from ardentum.quant.errors import InsufficientDataError, InvalidInputError


def _frame(data: dict[str, list[float]]) -> pd.DataFrame:
    n = len(next(iter(data.values())))
    return pd.DataFrame(data, index=pd.bdate_range("2024-01-01", periods=n))


def test_clean_data_passes_unchanged() -> None:
    df = _frame({"A": [1.0, 1.1, 1.2, 1.3], "B": [2.0, 2.1, 2.0, 2.2]})
    out, rep = align_prices(df)
    pd.testing.assert_frame_equal(out, df)
    assert rep.ok
    assert not rep.notes


def test_late_listing_trims_common_start() -> None:
    df = _frame({"A": [1.0, 1.1, 1.2, 1.3, 1.4], "B": [np.nan, np.nan, 2.0, 2.1, 2.2]})
    out, rep = align_prices(df)
    assert out.index[0] == df.index[2]
    assert "because B has no earlier prices" in rep.notes[0]


def test_short_gap_is_filled_and_reported() -> None:
    df = _frame({"A": [1.0, np.nan, 1.2, 1.3], "B": [2.0, 2.1, 2.0, 2.2]})
    out, rep = align_prices(df)
    assert out.loc[df.index[1], "A"] == 1.0
    assert any("carried forward" in n for n in rep.notes)


def test_long_gap_is_rejected() -> None:
    vals = [1.0] + [np.nan] * (MAX_FILL + 1) + [1.2]
    df = _frame({"A": vals, "B": list(np.linspace(1, 2, len(vals)))})
    with pytest.raises(InvalidInputError, match="gap"):
        align_prices(df)


def test_non_positive_and_duplicates_rejected() -> None:
    with pytest.raises(InvalidInputError, match="Non-positive"):
        align_prices(_frame({"A": [1.0, 0.0, 1.0]}))
    df = _frame({"A": [1.0, 1.1, 1.2]})
    df.index = pd.DatetimeIndex([df.index[0], df.index[0], df.index[2]])
    with pytest.raises(InvalidInputError, match="Duplicate dates"):
        align_prices(df)


def test_no_overlap() -> None:
    df = _frame({"A": [1.0, 1.1, np.nan, np.nan], "B": [np.nan, np.nan, 2.0, 2.1]})
    with pytest.raises(InsufficientDataError):
        align_prices(df)


def test_extreme_move_and_stale_warnings() -> None:
    a = [1.0] * 12 + [3.0, 3.1]
    b = list(np.linspace(1, 2, 14))
    _, rep = align_prices(_frame({"A": a, "B": b}))
    assert any("above 50%" in w for w in rep.warnings)
    assert any("unchanged" in w for w in rep.warnings)
