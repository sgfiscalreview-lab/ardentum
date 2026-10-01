"""The classroom worksheet's answer key matches what the API computes on the demo data.

The key lives in the frontend (src/lib/classroom-answers.json) and is shown to teachers;
these requests are the ones the workspace sends with its default settings.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

KEY = json.loads(
    (
        Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "classroom-answers.json"
    ).read_text()
)
TICKERS = [
    "NWS.SYN", "CLDR.SYN", "MDC.SYN", "HLX.SYN", "ARB.SYN", "CSP.SYN", "PTR.SYN",
    "SOL.SYN", "GRD.SYN", "HRV.SYN", "FRG.SYN", "GOVB.SYN", "CORP.SYN", "GOLD.SYN",
]  # fmt: skip
UNIVERSE = {
    "dataset_id": "demo",
    "tickers": TICKERS,
    "start": "2016-01-01",
    "end": "2025-12-31",
    "frequency": "daily",
}
ESTIMATION = {
    "mean_estimator": "historical",
    "covariance_estimator": "ledoit_wolf",
    "risk_free_rate": 0.02,
}
OBJECTIVE = {"objective": "max_sharpe", "cvar_confidence": 0.95}
CONSTRAINTS = {"min_weight": 0, "max_weight": 0.3}


def _post(client: TestClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _value(x: Any) -> float:
    return float(x["value"] if isinstance(x, dict) else x)


def test_exercise_1_diversification(client: TestClient) -> None:
    a = _post(client, "/api/v1/analytics", {"universe": UNIVERSE, "estimation": ESTIMATION})
    vols = {s["ticker"]: _value(s["performance"]["annualised_volatility"]) for s in a["assets"]}
    lowest = min(vols, key=lambda t: vols[t])
    assert lowest == KEY["lowest_single_asset_volatility"]["ticker"]
    assert round(vols[lowest], 3) == KEY["lowest_single_asset_volatility"]["value"]
    t, corr = a["tickers"], a["correlation"]
    i, j = min(itertools.combinations(range(len(t)), 2), key=lambda p: corr[p[0]][p[1]])
    assert {t[i], t[j]} == set(KEY["lowest_correlation"]["assets"])
    assert round(corr[i][j], 2) == KEY["lowest_correlation"]["value"]
    mv = _post(
        client,
        "/api/v1/optimise",
        {
            "universe": UNIVERSE,
            "estimation": ESTIMATION,
            "objective": {"objective": "min_volatility"},
            "constraints": CONSTRAINTS,
        },
    )
    assert round(mv["result"]["volatility"], 3) == KEY["min_volatility_portfolio"]
    assert mv["result"]["volatility"] < vols[lowest]  # the point of the exercise


def test_exercises_2_and_3_promise_backtest_and_simulation(client: TestClient) -> None:
    ms = _post(
        client,
        "/api/v1/optimise",
        {
            "universe": UNIVERSE,
            "estimation": ESTIMATION,
            "objective": OBJECTIVE,
            "constraints": CONSTRAINTS,
        },
    )
    assert round(ms["result"]["sharpe_ratio"], 2) == KEY["max_sharpe_promised"]

    ds = client.get("/api/v1/datasets/demo").json()
    bt = _post(
        client,
        "/api/v1/backtest",
        {
            "universe": {**UNIVERSE, "start": ds["start"], "end": ds["end"]},
            "estimation": ESTIMATION,
            "strategy": {"type": "optimised", "objective": OBJECTIVE, "constraints": CONSTRAINTS},
            "lookback_years": 3,
            "rebalance": "monthly",
            "transaction_cost_bps": 10,
            "benchmark": {"type": "equal_weight"},
        },
    )
    key = KEY["backtest"]
    assert [bt["evaluation_start"], bt["evaluation_end"]] == key["evaluation"]
    p, b = bt["performance"], bt["benchmark_performance"]
    assert round(_value(p["sharpe_ratio"]), 2) == key["strategy_sharpe"]
    assert round(_value(p["cagr"]), 3) == key["strategy_cagr"]
    assert round(_value(b["sharpe_ratio"]), 2) == key["equal_weight_sharpe"]
    assert round(_value(b["cagr"]), 3) == key["equal_weight_cagr"]
    assert round(bt["annualised_turnover"], 2) == key["annual_turnover"]

    weights = {h["ticker"]: h["weight"] for h in ms["result"]["holdings"] if h["weight"] > 1e-9}
    for years, name in ((1, "one_year"), (10, "ten_years")):
        mc = _post(
            client,
            "/api/v1/montecarlo",
            {
                "universe": {**UNIVERSE, "tickers": list(weights)},
                "estimation": ESTIMATION,
                "weights": weights,
                "method": "parametric",
                "n_paths": 5000,
                "horizon_years": years,
                "initial_value": 10000,
                "target_value": 20000,
                "seed": 20260926,
            },
        )
        exp = KEY["monte_carlo"][name]
        assert round(mc["probability_of_loss"], 2) == exp["probability_of_loss"]
        for q in ("p05", "p50", "p95"):
            assert round(mc["terminal_percentiles"][q]) == exp[q]


def test_extension_esg(client: TestClient) -> None:
    esg = _post(
        client,
        "/api/v1/esg/impact",
        {
            "universe": UNIVERSE,
            "estimation": ESTIMATION,
            "objective": OBJECTIVE,
            "constraints": {**CONSTRAINTS, "min_esg_score": 70, "exclude_unscored_assets": True},
        },
    )
    key = KEY["esg"]
    assert round(esg["baseline"]["sharpe_ratio"], 2) == key["baseline_sharpe"]
    assert round(esg["esg"]["sharpe_ratio"], 2) == key["esg_sharpe"]
    assert round(esg["baseline"]["volatility"], 2) == key["baseline_volatility"]
    assert round(esg["esg"]["volatility"], 2) == key["esg_volatility"]
