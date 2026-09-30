"""Anonymous usage counts: what is counted, what is not, and what is stored."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from ardentum.db.models import UsageCount
from ardentum.services import usage
from tests.api.conftest import login, universe

MONITOR = {"X-Ardentum-Monitor": "1"}


def _counts(client: TestClient) -> dict[str, dict[str, Any]]:
    r = client.get("/api/v1/usage")
    assert r.status_code == 200, r.text
    return {e["event"]: e for e in r.json()["events"]}


def test_empty_before_any_use(client: TestClient) -> None:
    r = client.get("/api/v1/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["since"] is None
    assert body["total_calculations"] == 0
    assert body["months"] == []
    assert {e["event"] for e in body["events"]} == set(usage.EVENTS)


def test_successful_calculations_are_counted_once(client: TestClient) -> None:
    for _ in range(2):
        assert client.post("/api/v1/optimise", json={"universe": universe()}).status_code == 200
    assert client.post("/api/v1/analytics", json={"universe": universe()}).status_code == 200
    counts = _counts(client)
    assert counts["optimise"]["total"] == 2
    assert counts["optimise"]["last_30_days"] == 2
    assert counts["analytics"]["total"] == 1
    body = client.get("/api/v1/usage").json()
    today = dt.datetime.now(dt.UTC).date()
    assert body["since"] == today.isoformat()
    assert body["total_calculations"] == 3
    assert body["months"] == [{"month": today.strftime("%Y-%m"), "calculations": 3}]


def test_failed_requests_and_monitoring_are_not_counted(client: TestClient) -> None:
    bad = {"universe": universe(tickers=["NWS.SYN", "NOPE.SYN"])}  # unknown ticker
    assert client.post("/api/v1/optimise", json=bad).status_code >= 400
    ok = {"universe": universe()}
    assert client.post("/api/v1/optimise", json=ok, headers=MONITOR).status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert _counts(client)["optimise"]["total"] == 0
    assert client.get("/api/v1/usage").json()["total_calculations"] == 0


def test_saves_and_exports_are_counted(client: TestClient) -> None:
    auth = login(client)
    body = {
        "name": "Counted",
        "dataset_id": "demo",
        "weights": {"NWS.SYN": 0.5, "GOVB.SYN": 0.5},
    }
    r = client.post("/api/v1/portfolios", json=body, headers=auth)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert (
        client.get(f"/api/v1/portfolios/{pid}/export?format=csv", headers=auth).status_code == 200
    )
    counts = _counts(client)
    assert counts["portfolio_saved"]["total"] == 1
    assert counts["portfolio_exported"]["total"] == 1
    # Saves are not calculations.
    assert client.get("/api/v1/usage").json()["total_calculations"] == 0


def _wait(client: TestClient, job_id: str, headers: dict[str, str] | None = None) -> None:
    for _ in range(60):
        r = client.get(f"/api/v1/jobs/{job_id}?wait=5", headers=headers or {})
        if r.json()["status"] in {"succeeded", "failed"}:
            return
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_jobs_count_when_they_succeed(client: TestClient) -> None:
    req = {"universe": universe()}
    r = client.post("/api/v1/jobs", json={"kind": "analytics", "request": req})
    _wait(client, r.json()["id"])
    # Written with the job's final status, so it is visible as soon as the job is.
    assert _counts(client)["analytics"]["total"] == 1
    r = client.post("/api/v1/jobs", json={"kind": "analytics", "request": req}, headers=MONITOR)
    _wait(client, r.json()["id"])
    assert _counts(client)["analytics"]["total"] == 1


def test_a_failing_count_never_fails_the_job(client: TestClient) -> None:
    with client.app.state.engine.begin() as conn:  # type: ignore[attr-defined]
        conn.exec_driver_sql("DROP TABLE usage_counts")
    r = client.post("/api/v1/jobs", json={"kind": "analytics", "request": {"universe": universe()}})
    job_id = r.json()["id"]
    _wait(client, job_id)
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "succeeded"
    assert client.post("/api/v1/optimise", json={"universe": universe()}).status_code == 200


def test_only_day_event_and_count_are_stored(client: TestClient) -> None:
    columns = {c["name"] for c in inspect(client.app.state.engine).get_columns("usage_counts")}  # type: ignore[attr-defined]
    assert columns == {"day", "event", "count"}
    client.post("/api/v1/optimise", json={"universe": universe()})
    with client.app.state.sessionmaker() as session:  # type: ignore[attr-defined]
        rows = session.execute(select(UsageCount)).scalars().all()
    assert [(r.event, r.count) for r in rows] == [("optimise", 1)]


def test_summary_windows_and_months(client: TestClient) -> None:
    factory = client.app.state.sessionmaker  # type: ignore[attr-defined]
    today = dt.date(2026, 11, 20)
    usage.record(factory, "backtest", today)
    usage.record(factory, "backtest", today - dt.timedelta(days=29))  # inside 30 days
    usage.record(factory, "backtest", today - dt.timedelta(days=30))  # outside
    usage.record(factory, "portfolio_saved", dt.date(2026, 10, 1))
    with factory() as session:
        out = usage.summary(session, today)
    backtest = next(e for e in out["events"] if e["event"] == "backtest")  # type: ignore[union-attr]
    assert backtest == {"event": "backtest", "total": 3, "last_30_days": 2}
    assert out["since"] == dt.date(2026, 10, 1)
    assert out["total_calculations"] == 3
    assert out["months"] == [
        {"month": "2026-10", "calculations": 2},
        {"month": "2026-11", "calculations": 1},
    ]


def test_event_mapping() -> None:
    assert usage.event_for("POST", "/api/v1/frontier/cvar") == "cvar_frontier"
    assert usage.event_for("POST", "/api/v1/jobs") is None  # counted on completion instead
    assert usage.event_for("GET", "/api/v1/optimise") is None
    assert usage.event_for("GET", "/api/v1/portfolios/abc/export") == "portfolio_exported"
    assert usage.event_for("DELETE", "/api/v1/portfolios") is None
