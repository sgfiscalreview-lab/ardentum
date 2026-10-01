"""Risk parity through the API: equal risk shares on the demo data, named constraint
breaks, and use as a walk-forward strategy."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import DEMO_TICKERS, universe

OPEN = {"max_weight": 1.0}


def test_every_holding_carries_the_same_share_of_risk(client: TestClient) -> None:
    body = {"universe": universe(), "objective": {"objective": "risk_parity"}, "constraints": OPEN}
    r = client.post("/api/v1/optimise", json=body)
    assert r.status_code == 200, r.text
    holdings = r.json()["result"]["holdings"]
    assert len(holdings) == len(DEMO_TICKERS)
    for h in holdings:
        assert h["risk_contribution_pct"] == pytest.approx(1 / len(DEMO_TICKERS), abs=1e-9)
        assert h["status"] == "held"
    assert sum(h["weight"] for h in holdings) == pytest.approx(1.0, abs=1e-12)
    assert r.json()["explanation"]["headline"].startswith(
        "Every holding contributes the same share of risk (12.5% each)"
    )


def test_a_weight_limit_it_breaks_is_named(client: TestClient) -> None:
    body = {
        "universe": universe(),
        "objective": {"objective": "risk_parity"},
        "constraints": {"max_weight": 0.3},
    }
    r = client.post("/api/v1/optimise", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["type"] == "infeasible"
    assert "GOVB.SYN gets" in r.json()["error"]["message"]
    assert "above its maximum of 30.0%" in r.json()["error"]["message"]


def test_walk_forward_backtest_with_risk_parity(client: TestClient) -> None:
    body = {
        "universe": universe(start="2016-01-01", end="2020-12-31"),
        "strategy": {
            "type": "optimised",
            "objective": {"objective": "risk_parity"},
            "constraints": OPEN,
        },
        "lookback_years": 2,
        "rebalance": "quarterly",
    }
    r = client.post("/api/v1/backtest", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["performance"]["annualised_volatility"] > 0
    assert r.json()["strategy"] == "Optimised (risk parity)"
