"""BIS policy-rate parsing, using the formats the live API returns."""

from __future__ import annotations

import pandas as pd
import pytest

from ardentum.data.errors import DataProviderError
from ardentum.data.providers import bis
from ardentum.quant.errors import InvalidInputError

# Captured from https://stats.bis.org/api/v1/data/WS_CBPOL/D.JP/all?...&detail=dataonly&format=csv
DATAONLY = b"FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\nD,JP,2026-09-01,1\nD,JP,2026-09-02,1\n"
# The full format (default detail) has more columns and NaN on days without a value.
FULL = (
    b"FREQ,REF_AREA,UNIT_MEASURE,UNIT_MULT,TIME_FORMAT,COMPILATION,DECIMALS,SOURCE_REF,"
    b"SUPP_INFO_BREAKS,TITLE,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK\n"
    b'D,GB,368,0,,"From 3 Aug 2006 onwards: official bank rate; from 6 May 1997: repo rate.",4,'
    b"Bank of England,, Central bank policy rates - United Kingdom - Daily - End of period,"
    b"2026-08-28,3.75,A,F,\n"
    b'D,GB,368,0,,"x",4,Bank of England,, t,2026-08-31,NaN,M,F,\n'
    b'D,GB,368,0,,"x",4,Bank of England,, t,2026-09-01,3.5,A,F,\n'
)


def test_parse_dataonly_and_full_formats() -> None:
    jp = bis.parse_rates(DATAONLY, "JPY")
    assert jp.tolist() == pytest.approx([0.01, 0.01])
    assert jp.index[0] == pd.Timestamp("2026-09-01")
    gb = bis.parse_rates(FULL, "GBP")
    assert gb.tolist() == pytest.approx([0.0375, 0.035])  # NaN day dropped
    assert list(gb.index) == [pd.Timestamp("2026-08-28"), pd.Timestamp("2026-09-01")]


def test_other_areas_are_ignored_and_empty_is_an_error() -> None:
    with pytest.raises(DataProviderError, match="no policy rates for EUR"):
        bis.parse_rates(DATAONLY, "EUR")
    with pytest.raises(DataProviderError, match="format"):
        bis.parse_rates(b"a,b\n1,2\n", "JPY")


def test_currency_mapping() -> None:
    assert bis.area_for("eur") == "XM"
    assert bis.area_for("USD") == "US"
    with pytest.raises(InvalidInputError, match="SGD"):
        bis.area_for("SGD")
