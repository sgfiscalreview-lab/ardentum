import httpx
import numpy as np
import pytest
import respx

from ardentum.data.errors import DataProviderError
from ardentum.data.providers import kenfrench as kf
from tests.fixtures.kenfrench import (
    factors_daily_text,
    industries_daily_text,
    industries_monthly_text,
    zipped,
)


def test_parse_tables_and_value_weighted_returns() -> None:
    text = industries_daily_text(n_days=10, missing_first=3)
    tables = kf.parse_tables(text)
    assert [t.title for t in tables] == [
        "Average Value Weighted Returns -- Daily",
        "Average Equal Weighted Returns -- Daily",
    ]
    r = kf.industry_returns(text)
    assert list(r.columns) == [c.upper() for c in kf.IND12]  # padded headers are stripped
    assert r.index[0].isoformat()[:10] == "2020-01-02"
    assert r["NODUR"].iloc[:3].isna().all()  # -99.99 is missing, never a -99.99% return
    raw = tables[0].frame.iloc[5, 1]
    assert r.iloc[5, 1] == pytest.approx(raw / 100)


def test_factor_returns_market_is_excess_plus_rf() -> None:
    text = factors_daily_text(n_days=5)
    t = kf.parse_tables(text)[0]
    f = kf.factor_returns(text)
    np.testing.assert_allclose(
        f["MKT"].to_numpy(), (t.frame["Mkt-RF"] + t.frame["RF"]).to_numpy() / 100
    )
    np.testing.assert_allclose(f["RF"].to_numpy(), 0.00008)
    assert len(f) == 5  # copyright footer is not data


def test_market_caps_use_latest_month() -> None:
    caps = kf.market_caps(industries_monthly_text())
    assert caps["NODUR"] == pytest.approx(100 * 1000)
    assert len(caps) == 12


def test_returns_to_prices_round_trip() -> None:
    r = kf.industry_returns(industries_daily_text(n_days=50))
    p = kf.returns_to_prices(r)
    np.testing.assert_allclose(
        (p / p.shift(1) - 1).iloc[1:].to_numpy(), r.iloc[1:].to_numpy(), atol=1e-12
    )


def test_crlf_only_cr_and_cp1252_handled() -> None:
    text = industries_daily_text(n_days=5).replace("\r\n", "\r")
    assert len(kf.industry_returns(text)) == 5
    payload = zipped("x", "caf\xe9 header\r\n\r\n,A\r\n20200102, 1.00\r\n")
    assert "20200102" in kf.unzip_text(payload)


def test_bad_payloads() -> None:
    with pytest.raises(DataProviderError):
        kf.unzip_text(b"not a zip")
    with pytest.raises(DataProviderError):
        kf.parse_tables("no tables here")


@respx.mock
def test_download_errors() -> None:
    respx.get(f"{kf.BASE_URL}X_CSV.zip").mock(return_value=httpx.Response(404))
    with pytest.raises(DataProviderError, match="HTTP 404"):
        kf.download("X")
