import itertools

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import DEMO_TICKERS, universe


def test_health_and_meta(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    meta = client.get("/api/v1/meta").json()
    assert meta["auth_mode"] == "dev"
    assert meta["live_data_available"] is False
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Request-ID" in r.headers


def test_openapi_schema(client: TestClient) -> None:
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/optimise" in spec["paths"]


def test_datasets(client: TestClient) -> None:
    lst = client.get("/api/v1/datasets").json()
    assert lst[0]["id"] == "demo"
    assert lst[0]["is_synthetic"] is True
    d = client.get("/api/v1/datasets/demo").json()
    assert len(d["assets"]) == 20
    assert "Information Technology" in d["sectors"]
    assert client.get("/api/v1/datasets/tiingo").status_code == 503
    assert client.get("/api/v1/datasets/not-a-uuid").status_code == 404


def test_analytics(client: TestClient) -> None:
    r = client.post("/api/v1/analytics", json={"universe": universe(), "benchmark": "MKT.SYN"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["provenance"]["is_synthetic"] is True
    assert len(body["assets"]) == len(DEMO_TICKERS)
    corr = np.array(body["correlation"])
    np.testing.assert_allclose(np.diag(corr), 1.0)
    assert body["assets"][0]["performance"]["beta"]["value"] is not None
    assert body["normalised_prices"]["NWS.SYN"][0] == pytest.approx(100.0)


def test_optimise_max_sharpe_with_explanation(client: TestClient) -> None:
    r = client.post(
        "/api/v1/optimise",
        json={
            "universe": universe(),
            "estimation": {"risk_free_rate": 0.02},
            "objective": {"objective": "max_sharpe"},
            "constraints": {"max_weight": 0.35},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    w = [h["weight"] for h in body["result"]["holdings"]]
    assert sum(w) == pytest.approx(1.0, abs=1e-9)
    assert max(w) <= 0.35 + 1e-9
    assert body["explanation"]["headline"]
    assert body["explanation"]["assumptions"]
    assert sum(h["risk_contribution_pct"] for h in body["result"]["holdings"]) == pytest.approx(1.0)
    assert body["estimation"]["covariance_estimator"] == "ledoit_wolf"


def test_optimise_is_deterministic(client: TestClient) -> None:
    req = {"universe": universe(), "objective": {"objective": "min_volatility"}}
    a = client.post("/api/v1/optimise", json=req).json()
    b = client.post("/api/v1/optimise", json=req).json()
    assert a["result"] == b["result"]


def test_optimise_stability_is_seeded(client: TestClient) -> None:
    req = {
        "universe": universe(tickers=DEMO_TICKERS[:4]),
        "objective": {"objective": "max_sharpe"},
        "stability_resamples": 8,
        "seed": 5,
    }
    a = client.post("/api/v1/optimise", json=req).json()
    b = client.post("/api/v1/optimise", json=req).json()
    assert a["stability"] == b["stability"]
    assert a["seed"] == 5


def test_infeasible_returns_422_with_message(client: TestClient) -> None:
    r = client.post(
        "/api/v1/optimise",
        json={"universe": universe(), "constraints": {"max_weight": 0.05}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["type"] == "infeasible"
    assert "fully invested" in r.json()["error"]["message"]


def test_validation_errors_are_consistent(client: TestClient) -> None:
    r = client.post("/api/v1/optimise", json={"universe": universe(tickers=[]), "bogus": 1})
    assert r.status_code == 422
    assert r.json()["error"]["type"] == "validation_error"
    r = client.post(
        "/api/v1/optimise",
        json={"universe": universe(), "objective": {"objective": "target_return"}},
    )
    assert r.status_code == 422
    assert "target_return" in r.json()["error"]["message"]


def test_unknown_ticker(client: TestClient) -> None:
    r = client.post("/api/v1/optimise", json={"universe": universe(tickers=["AAPL", "NWS.SYN"])})
    assert r.status_code == 422
    assert "Unknown demo tickers" in r.json()["error"]["message"]


def test_frontier(client: TestClient) -> None:
    r = client.post(
        "/api/v1/frontier",
        json={
            "universe": universe(),
            "constraints": {"min_esg_score": 60, "exclude_unscored_assets": True},
            "n_points": 12,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    vols = [p["volatility"] for p in body["points"]]
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(vols))
    assert body["unconstrained_points"] is not None
    assert all(p["esg_score"] >= 60 - 1e-6 for p in body["points"])
    # ESG-constrained min vol cannot beat the unconstrained one.
    assert body["min_volatility"]["volatility"] >= body["unconstrained_points"][0]["volatility"] * (
        1 - 1e-6
    )


def test_esg_impact(client: TestClient) -> None:
    r = client.post(
        "/api/v1/esg/impact",
        json={
            "universe": universe(),
            "objective": {"objective": "max_sharpe"},
            "constraints": {"min_esg_score": 65, "excluded_sectors": ["Energy"]},
        },
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["esg"]["esg_score"] >= 65 - 1e-6
    assert b["delta_sharpe_ratio"] <= 1e-9
    assert b["ex_ante_tracking_error"] >= 0
    assert any("synthetic" in n.lower() for n in b["esg_data_notes"])
    assert b["esg_frontier"]
    energy = [c for c in b["weight_changes"] if c["sector"] == "Energy"]
    assert all(c["esg_weight"] == 0 for c in energy)


def test_esg_impact_requires_esg_settings(client: TestClient) -> None:
    r = client.post("/api/v1/esg/impact", json={"universe": universe(), "constraints": {}})
    assert r.status_code == 422


def test_montecarlo_reproducible(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    req = {"universe": universe(), "weights": w, "n_paths": 500, "horizon_years": 3, "seed": 99}
    a = client.post("/api/v1/montecarlo", json=req)
    assert a.status_code == 200, a.text
    b = client.post("/api/v1/montecarlo", json=req)
    assert a.json()["percentiles"] == b.json()["percentiles"]
    body = a.json()
    assert body["seed"] == 99
    assert "p50" in body["percentiles"]
    boot = client.post("/api/v1/montecarlo", json={**req, "method": "block_bootstrap"})
    assert boot.status_code == 200, boot.text


def test_montecarlo_withdrawals_report_depletion(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    req = {
        "universe": universe(),
        "weights": w,
        "n_paths": 500,
        "horizon_years": 20,
        "seed": 5,
        "initial_value": 100_000,
        "annual_cash_flow": -12_000,
        "cash_flows_per_year": 12,
    }
    r = client.post("/api/v1/montecarlo", json=req)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["net_cash_flow"] == pytest.approx(-240_000)
    assert 0 < body["probability_of_depletion"] <= 1
    assert set(body["depletion_years_percentiles"]) == {"p10", "p50", "p90"}
    assert any("depleted" in a for a in body["assumptions"])
    plain = client.post("/api/v1/montecarlo", json={**req, "annual_cash_flow": 0}).json()
    assert plain["probability_of_depletion"] is None
    # Time-weighted growth does not depend on cash flows (same seed, same draws).
    assert plain["cagr_percentiles"] == body["cagr_percentiles"]


def test_montecarlo_rejects_bad_weights(client: TestClient) -> None:
    r = client.post(
        "/api/v1/montecarlo",
        json={"universe": universe(), "weights": {"NWS.SYN": 0.5}, "n_paths": 200},
    )
    assert r.status_code == 422
    assert "sum to 100%" in r.json()["error"]["message"]


def test_backtest_optimised_vs_equal_weight(client: TestClient) -> None:
    r = client.post(
        "/api/v1/backtest",
        json={
            "universe": universe(start="2014-01-01", end="2020-12-31"),
            "strategy": {"type": "optimised", "objective": {"objective": "min_volatility"}},
            "lookback_years": 2,
            "rebalance": "quarterly",
            "transaction_cost_bps": 10,
            "benchmark": {"type": "equal_weight"},
        },
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["evaluation_start"] > b["estimation_start"]
    assert len(b["dates"]) == len(b["portfolio"]["wealth"]) - 1
    total = sum(c["contribution"] for c in b["asset_contributions"])
    assert total == pytest.approx(b["performance"]["total_return"], abs=1e-9)
    assert b["brinson"] is not None
    assert b["benchmark_performance"] is not None
    assert b["performance"]["tracking_error"] is not None


def test_backtest_asset_benchmark(client: TestClient) -> None:
    r = client.post(
        "/api/v1/backtest",
        json={
            "universe": universe(start="2015-01-01", end="2019-12-31"),
            "strategy": {"type": "equal_weight"},
            "lookback_years": 1,
            "benchmark": {"type": "asset", "ticker": "MKT.SYN"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["benchmark"]["name"] == "MKT.SYN"


def test_compare(client: TestClient) -> None:
    n = len(DEMO_TICKERS)
    r = client.post(
        "/api/v1/compare",
        json={
            "universe": universe(),
            "portfolios": [
                {"name": "Equal", "weights": dict.fromkeys(DEMO_TICKERS, 1 / n)},
                {"name": "Bonds heavy", "weights": {"GOVB.SYN": 0.7, "NWS.SYN": 0.3}},
            ],
        },
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert len(b["portfolios"]) == 2
    assert b["in_sample_warning"]
    assert b["return_correlation"][0][0] == pytest.approx(1.0)


def test_weekly_frequency(client: TestClient) -> None:
    r = client.post("/api/v1/analytics", json={"universe": universe(frequency="weekly")})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["periods_per_year"] == 52


def test_wealth_dates_align_with_wealth(client: TestClient) -> None:
    n = len(DEMO_TICKERS)
    r = client.post(
        "/api/v1/compare",
        json={
            "universe": universe(),
            "portfolios": [
                {"name": "A", "weights": dict.fromkeys(DEMO_TICKERS, 1 / n)},
                {"name": "B", "weights": {"GOVB.SYN": 1.0}},
            ],
        },
    ).json()
    assert len(r["wealth_dates"]) == len(r["portfolios"][0]["wealth"])
    assert r["wealth_dates"][0] < r["dates"][0]
    b = client.post(
        "/api/v1/backtest",
        json={"universe": universe(), "strategy": {"type": "equal_weight"}, "lookback_years": 1},
    ).json()
    assert len(b["wealth_dates"]) == len(b["portfolio"]["wealth"])
    assert b["wealth_dates"][0] == b["events"][0]["date"]


def test_health_db(client: TestClient) -> None:
    assert client.get("/api/v1/health/db").json() == {"status": "ok", "database": "ok"}


def test_cors_allows_configured_origin(client: TestClient) -> None:
    r = client.options(
        "/api/v1/optimise",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.options(
        "/api/v1/optimise",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers
