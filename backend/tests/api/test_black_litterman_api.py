"""Black-Litterman through the API: prior choice, views and explanations."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from ardentum.services import market_data
from ardentum.services.provider_cache import clear_memory
from tests.api.conftest import DEMO_TICKERS, universe
from tests.api.test_kenfrench_api import TICKERS as KF_TICKERS
from tests.api.test_kenfrench_api import _mock_downloads


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_memory()
    market_data._PARSED_CACHE._data.clear()
    yield
    clear_memory()


def _body(bl: dict[str, object], **u: object) -> dict[str, object]:
    return {
        "universe": universe(**u),
        "estimation": {"mean_estimator": "black_litterman", "black_litterman": bl},
        "objective": {"objective": "max_sharpe"},
    }


def test_market_cap_prior_needs_caps(client: TestClient) -> None:
    r = client.post("/api/v1/optimise", json=_body({}))
    assert r.status_code == 422
    msg = r.json()["error"]["message"]
    assert "No market capitalisation" in msg
    assert "equal or custom" in msg


def test_equal_weight_prior_with_views(client: TestClient) -> None:
    views = [
        {"weights": {"NWS.SYN": 1}, "expected_return": 0.20, "confidence": 1.0},
        {"weights": {"SOL.SYN": 1, "PTR.SYN": -1}, "expected_return": 0.03},
    ]
    bl = {"prior": "equal_weight", "views": views, "risk_aversion": 3.0}
    r = client.post("/api/v1/optimise", json=_body(bl))
    assert r.status_code == 200, r.text
    out = r.json()["estimation"]["black_litterman"]
    assert out["prior"] == "equal weights"
    assets = {a["ticker"]: a for a in out["assets"]}
    assert all(a["prior_weight"] == pytest.approx(1 / len(DEMO_TICKERS)) for a in assets.values())
    # A 100%-confidence absolute view holds exactly in the posterior.
    assert assets["NWS.SYN"]["posterior_return"] == pytest.approx(0.20, abs=1e-9)
    assert any("outperforms PTR.SYN" in v for v in out["views"])
    assert r.json()["estimation"]["mean_estimator"] == "black_litterman"


def test_custom_prior_validation(client: TestClient) -> None:
    r = client.post("/api/v1/optimise", json=_body({"prior": "custom"}))
    assert r.status_code == 422
    r = client.post(
        "/api/v1/optimise",
        json=_body(
            {"prior": "equal_weight", "views": [{"weights": {"ZZZ": 1}, "expected_return": 0.1}]}
        ),
    )
    assert r.status_code == 422
    assert "outside the selection" in r.json()["error"]["message"]


@respx.mock
def test_market_caps_from_kenfrench(client: TestClient) -> None:
    _mock_downloads()
    body = _body({}, dataset_id="kf12", tickers=KF_TICKERS, start=None, end=None)
    r = client.post("/api/v1/optimise", json=body)
    assert r.status_code == 200, r.text
    out = r.json()["estimation"]["black_litterman"]
    assert out["prior"] == "market capitalisation"
    weights = np.array([a["prior_weight"] for a in out["assets"]])
    assert weights.sum() == pytest.approx(1.0)
    assert len(set(np.round(weights, 8))) > 1  # not equal weights


def test_backtest_with_black_litterman(client: TestClient) -> None:
    body = {
        "universe": universe(),
        "estimation": {
            "mean_estimator": "black_litterman",
            "black_litterman": {"prior": "equal_weight"},
        },
        "strategy": {"type": "optimised", "objective": {"objective": "max_sharpe"}},
        "lookback_years": 2,
        "rebalance": "quarterly",
    }
    r = client.post("/api/v1/backtest", json=body)
    assert r.status_code == 200, r.text
