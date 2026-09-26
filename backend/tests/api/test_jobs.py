"""Background jobs: submit, long-poll, ownership, failures and recovery of abandoned runs."""

from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import update

from ardentum.db.models import Job
from tests.api.conftest import DEMO_TICKERS, login, universe


def _wait(client: TestClient, job_id: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    for _ in range(40):
        r = client.get(f"/api/v1/jobs/{job_id}?wait=5", headers=headers or {})
        assert r.status_code == 200, r.text
        if r.json()["status"] in ("succeeded", "failed"):
            return r.json()  # type: ignore[no-any-return]
    raise AssertionError("job did not finish")


def test_job_result_equals_synchronous_endpoint(client: TestClient) -> None:
    w = {t: 1 / len(DEMO_TICKERS) for t in DEMO_TICKERS}
    req = {"universe": universe(), "weights": w, "n_paths": 300, "horizon_years": 2, "seed": 7}
    r = client.post("/api/v1/jobs", json={"kind": "montecarlo", "request": req})
    assert r.status_code == 202, r.text
    assert r.json()["status"] in ("queued", "running", "succeeded")
    job = _wait(client, r.json()["id"])
    assert job["status"] == "succeeded"
    assert job["attempts"] == 1
    assert job["finished_at"] is not None
    sync = client.post("/api/v1/montecarlo", json=req).json()
    assert job["result"]["percentiles"] == sync["percentiles"]
    assert job["result"]["seed"] == 7


def test_invalid_request_rejected_at_submission(client: TestClient) -> None:
    r = client.post(
        "/api/v1/jobs", json={"kind": "optimise", "request": {"universe": {"tickers": []}}}
    )
    assert r.status_code == 422
    assert r.json()["error"]["message"].startswith("request.universe")
    r = client.post("/api/v1/jobs", json={"kind": "nope", "request": {}})
    assert r.status_code == 422


def test_failed_job_reports_user_facing_error(client: TestClient) -> None:
    body = {
        "universe": universe(),
        "objective": {"objective": "target_return", "target_return": 1.5},
    }
    job = _wait(
        client, client.post("/api/v1/jobs", json={"kind": "optimise", "request": body}).json()["id"]
    )
    assert job["status"] == "failed"
    assert job["error"]["type"] == "infeasible"
    assert job["error"]["status"] == 422
    assert "exceeds the maximum achievable" in job["error"]["message"]
    assert job["result"] is None


def test_jobs_of_signed_in_users_are_private(client: TestClient) -> None:
    alice = login(client, "alice@example.com")
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    jid = client.post(
        "/api/v1/jobs", json={"kind": "analytics", "request": body}, headers=alice
    ).json()["id"]
    assert _wait(client, jid, alice)["status"] == "succeeded"
    assert client.get(f"/api/v1/jobs/{jid}").status_code == 404
    bob = login(client, "bob@example.com")
    assert client.get(f"/api/v1/jobs/{jid}", headers=bob).status_code == 404
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 404
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 404


def _insert_abandoned(client: TestClient, attempts: int) -> str:
    """A job whose instance died mid-run: 'running' with an old heartbeat."""
    jid = uuid.uuid4()
    old = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    body = {"universe": universe(tickers=["NWS.SYN", "GOVB.SYN"])}
    factory = client.app.state.sessionmaker  # type: ignore[attr-defined]
    with factory() as session, session.begin():
        session.add(
            Job(
                id=jid,
                owner_id=None,
                kind="analytics",
                status="running",
                request=body,
                attempts=attempts,
                created_at=old,
                started_at=old,
                heartbeat_at=old,
            )
        )
    return str(jid)


def test_abandoned_job_is_resumed_by_a_poll(client: TestClient) -> None:
    jid = _insert_abandoned(client, attempts=1)
    job = _wait(client, jid)
    assert job["status"] == "succeeded"
    assert job["attempts"] == 2


def test_repeatedly_interrupted_job_fails(client: TestClient) -> None:
    jid = _insert_abandoned(client, attempts=2)
    r = client.get(f"/api/v1/jobs/{jid}?wait=1").json()
    assert r["status"] == "failed"
    assert r["error"]["type"] == "interrupted"


def test_running_job_with_fresh_heartbeat_is_not_claimed(client: TestClient) -> None:
    jid = _insert_abandoned(client, attempts=1)
    factory = client.app.state.sessionmaker  # type: ignore[attr-defined]
    with factory() as session, session.begin():
        session.execute(
            update(Job).where(Job.id == uuid.UUID(jid)).values(heartbeat_at=dt.datetime.now(dt.UTC))
        )
    start = time.monotonic()
    r = client.get(f"/api/v1/jobs/{jid}?wait=1").json()
    assert r["status"] == "running"
    assert r["attempts"] == 1
    assert time.monotonic() - start >= 0.9  # the long-poll waited
