import numpy as np
import pytest

from ardentum.data.providers import demo
from ardentum.data.validation import align_prices
from ardentum.quant.errors import InvalidInputError
from ardentum.quant.returns import simple_returns


def test_demo_is_deterministic_and_pinned() -> None:
    demo._generate.cache_clear()
    a = demo._generate().copy()
    demo._generate.cache_clear()
    b = demo._generate()
    np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())
    # Pin the generator: any change must be deliberate (bump GENERATOR_VERSION).
    assert demo.GENERATOR_VERSION == "1.0.0"
    assert a.shape == (3913, 20)
    assert a.index[0].isoformat()[:10] == "2011-01-03"


def test_demo_is_clearly_labelled_synthetic() -> None:
    info = demo.dataset_info()
    assert info.provenance.is_synthetic
    assert all(a.ticker.endswith(".SYN") for a in info.assets)
    assert all("synthetic" in a.name.lower() for a in info.assets)
    for a in info.assets:
        if a.esg is not None:
            assert a.esg.is_synthetic
            assert "not from any ESG rating provider" in a.esg.source
    assert any(a.is_benchmark for a in info.assets)
    assert any(a.esg is None for a in info.assets)  # exercises missing-score handling


def test_demo_statistics_are_plausible() -> None:
    prices = demo.load_prices([a.ticker for a in demo.dataset_info().assets]).prices
    aligned, report = align_prices(prices)
    assert report.ok
    r = simple_returns(aligned)
    vol = r.std() * np.sqrt(252)
    assert vol["MKT.SYN"] == pytest.approx(0.18, abs=0.04)
    assert vol["GOVB.SYN"] < 0.08
    equities = [a.ticker for a in demo.dataset_info().assets if a.asset_class.value == "equity"]
    assert (vol[equities] > 0.12).all()
    assert (vol[equities] < 0.45).all()
    corr = r.corr()
    assert corr.loc["NWS.SYN", "CLDR.SYN"] > corr.loc["NWS.SYN", "GRD.SYN"]  # sector effect
    assert corr.loc["GOVB.SYN", "MKT.SYN"] < 0
    # Volatility clustering: |r| autocorrelated, r itself nearly not.
    m = r["MKT.SYN"]
    assert m.abs().autocorr(1) > 0.1
    assert abs(m.autocorr(1)) < 0.1


def test_demo_slicing_and_unknown_ticker() -> None:
    import datetime as dt

    pd_ = demo.load_prices(["MKT.SYN"], dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert pd_.prices.index[0].year == 2020
    assert pd_.prices.index[-1].year == 2020
    with pytest.raises(InvalidInputError):
        demo.load_prices(["AAPL"])
