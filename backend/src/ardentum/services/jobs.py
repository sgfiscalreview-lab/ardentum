"""Background jobs that survive request-based CPU billing (e.g. Cloud Run).

Serverless platforms throttle the CPU when no request is in flight, so work must
run *while* a request is open. Jobs therefore run in a thread started by the
request that creates them, and every poll (``GET /jobs/{id}?wait=...``) keeps a
request open while the job runs. Any instance that sees a job still ``queued``, or
``running`` with a heartbeat older than ``STALE_AFTER`` (its instance died), claims
it with an atomic conditional UPDATE and runs it. Calculations are deterministic
given their inputs (simulations carry a seed), so a re-run gives the same result;
after ``MAX_ATTEMPTS`` interrupted runs the job fails with a clear message.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import random
import threading
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, delete, or_, update
from sqlalchemy.orm import Session, sessionmaker

from ardentum.api import schemas as s
from ardentum.api.auth import Principal
from ardentum.api.errors import classify
from ardentum.config import Settings
from ardentum.db.models import Job
from ardentum.quant.errors import InvalidInputError
from ardentum.services import analysis
from ardentum.services.market_data import MarketDataService, NotFoundError

log = logging.getLogger("ardentum.jobs")

HEARTBEAT_SECONDS = 5.0
STALE_AFTER = dt.timedelta(seconds=30)
MAX_ATTEMPTS = 2
RETENTION = dt.timedelta(hours=24)
TERMINAL = frozenset({"succeeded", "failed"})

Runner = Callable[[MarketDataService, Any], BaseModel]
KINDS: dict[str, tuple[type[BaseModel], Runner]] = {
    "analytics": (s.AnalyticsRequest, analysis.asset_analytics),
    "optimise": (s.OptimiseRequest, analysis.run_optimise),
    "frontier": (s.FrontierRequest, analysis.run_frontier),
    "cvar_frontier": (s.CvarFrontierRequest, analysis.run_cvar_frontier),
    "esg_impact": (s.EsgImpactRequest, analysis.run_esg_impact),
    "montecarlo": (s.MonteCarloRequest, analysis.run_montecarlo),
    "backtest": (s.BacktestRequest, analysis.run_backtest_service),
    "compare": (s.CompareRequest, analysis.run_compare),
}

# Jobs executing in this process -> event set on completion (wakes local long-polls).
_LOCAL: dict[uuid.UUID, threading.Event] = {}
_LOCAL_LOCK = threading.Lock()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    """SQLite returns naive datetimes; all stored times are UTC."""
    if t is None:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=dt.UTC)


def validate_request(kind: str, payload: dict[str, Any]) -> BaseModel:
    model, _ = KINDS[kind]
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(str(p) for p in err.get("loc", ()))
        raise InvalidInputError(
            f"request.{where}: {err.get('msg', 'invalid value')}" if where else str(err.get("msg"))
        ) from exc


class JobService:
    def __init__(
        self, settings: Settings, factory: sessionmaker[Session], principal: Principal | None
    ) -> None:
        self.settings = settings
        self.factory = factory
        self.principal = principal

    # ---------------------------------------------------------------- create / read

    def create(self, kind: str, payload: dict[str, Any]) -> Job:
        req = validate_request(kind, payload)
        job = Job(
            id=uuid.uuid4(),
            owner_id=self.principal.user_id if self.principal else None,
            kind=kind,
            status="queued",
            request=req.model_dump(mode="json"),
            attempts=0,
            created_at=_now(),
        )
        with self.factory() as session, session.begin():
            session.add(job)
            if random.randrange(50) == 0:
                session.execute(delete(Job).where(Job.created_at < _now() - RETENTION))
        self.start(job.id)
        return job

    def get(self, job_id: str | uuid.UUID) -> Job:
        try:
            jid = uuid.UUID(str(job_id))
        except ValueError as exc:
            raise NotFoundError("Job not found.") from exc
        with self.factory() as session:
            job = session.get(Job, jid)
        if job is None or (
            job.owner_id is not None
            and (self.principal is None or self.principal.user_id != job.owner_id)
        ):
            raise NotFoundError("Job not found (jobs expire after 24 hours).")
        return job

    # ---------------------------------------------------------------- execution

    def _claim(self, job_id: uuid.UUID) -> bool:
        now = _now()
        claimable = or_(
            Job.status == "queued",
            and_(
                Job.status == "running",
                Job.heartbeat_at < now - STALE_AFTER,
                Job.attempts < MAX_ATTEMPTS,
            ),
        )
        with self.factory() as session, session.begin():
            res = session.execute(
                update(Job)
                .where(Job.id == job_id, claimable)
                .values(
                    status="running",
                    attempts=Job.attempts + 1,
                    started_at=now,
                    heartbeat_at=now,
                )
            )
            if res.rowcount == 1:  # type: ignore[attr-defined]
                return True
            # Abandon jobs whose runs keep being interrupted.
            session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.heartbeat_at < now - STALE_AFTER,
                    Job.attempts >= MAX_ATTEMPTS,
                )
                .values(
                    status="failed",
                    finished_at=now,
                    error={
                        "type": "interrupted",
                        "message": "The calculation was interrupted repeatedly; try again or "
                        "reduce its size.",
                        "status": 503,
                    },
                )
            )
        return False

    def start(self, job_id: uuid.UUID) -> bool:
        """Run the job in a background thread if it can be claimed; True if started."""
        if not self._claim(job_id):
            return False
        done = threading.Event()
        with _LOCAL_LOCK:
            _LOCAL[job_id] = done
        threading.Thread(target=self._execute, args=(job_id, done), daemon=True).start()
        return True

    def _heartbeat(self, job_id: uuid.UUID, stop: threading.Event) -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                with self.factory() as session, session.begin():
                    session.execute(
                        update(Job)
                        .where(Job.id == job_id, Job.status == "running")
                        .values(heartbeat_at=_now())
                    )
            except Exception:
                log.warning("heartbeat failed for job %s", job_id, exc_info=True)

    def _execute(self, job_id: uuid.UUID, done: threading.Event) -> None:
        stop = threading.Event()
        threading.Thread(target=self._heartbeat, args=(job_id, stop), daemon=True).start()
        values: dict[str, Any]
        try:
            with self.factory() as session:
                job = session.get(Job, job_id)
                assert job is not None
                principal = Principal(job.owner_id, None) if job.owner_id else None
                model, run = KINDS[job.kind]
                service = MarketDataService(self.settings, session, principal)
                result = run(service, model.model_validate(job.request))
            blob = gzip.compress(json.dumps(result.model_dump(mode="json")).encode("utf-8"))
            values = {"status": "succeeded", "result": blob}
        except Exception as exc:
            kind, message, status = classify(exc)
            if status >= 500:
                log.exception("job %s failed", job_id)
            values = {
                "status": "failed",
                "error": {"type": kind, "message": message, "status": status},
            }
        finally:
            stop.set()
        try:
            with self.factory() as session, session.begin():
                session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == "running")
                    .values(finished_at=_now(), **values)
                )
        finally:
            done.set()
            with _LOCAL_LOCK:
                _LOCAL.pop(job_id, None)

    # ---------------------------------------------------------------- output

    @staticmethod
    def local_event(job_id: uuid.UUID) -> threading.Event | None:
        with _LOCAL_LOCK:
            return _LOCAL.get(job_id)

    @staticmethod
    def out(job: Job) -> s.JobOut:
        result = None
        if job.status == "succeeded" and job.result is not None:
            result = json.loads(gzip.decompress(job.result))
        return s.JobOut(
            id=str(job.id),
            kind=job.kind,
            status=job.status,
            attempts=job.attempts,
            created_at=_aware(job.created_at) or _now(),
            started_at=_aware(job.started_at),
            finished_at=_aware(job.finished_at),
            result=result,
            error=s.JobErrorOut(**job.error) if job.error else None,
        )
