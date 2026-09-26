"""Background jobs: submit a long calculation, then long-poll for its result."""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from starlette.concurrency import run_in_threadpool

from ardentum.api import schemas as s
from ardentum.api.deps import OptionalPrincipal, SettingsDep
from ardentum.services.jobs import TERMINAL, JobService

router = APIRouter(tags=["jobs"])
MAX_WAIT = 25.0  # below common proxy/request timeouts


def _service(request: Request, settings: SettingsDep, principal: OptionalPrincipal) -> JobService:
    return JobService(settings, request.app.state.sessionmaker, principal)


@router.post("/jobs", response_model=s.JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    body: s.JobCreate, request: Request, settings: SettingsDep, principal: OptionalPrincipal
) -> s.JobOut:
    """Start a calculation in the background. The request is validated immediately."""
    svc = _service(request, settings, principal)
    return svc.out(svc.create(body.kind, body.request))


@router.get("/jobs/{job_id}", response_model=s.JobOut)
async def get_job(
    job_id: str,
    request: Request,
    settings: SettingsDep,
    principal: OptionalPrincipal,
    wait: Annotated[float, Query(ge=0.0, le=MAX_WAIT)] = 0.0,
) -> s.JobOut:
    """Job status; with ``wait`` > 0, hold the request until the job finishes or ``wait``
    seconds pass. Keep polling while the status is ``queued`` or ``running``."""
    svc = _service(request, settings, principal)
    job = await run_in_threadpool(svc.get, job_id)
    deadline = time.monotonic() + wait
    while job.status not in TERMINAL:
        await run_in_threadpool(svc.start, job.id)  # resumes queued or abandoned jobs
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        event = svc.local_event(job.id)
        if event is not None:
            await run_in_threadpool(event.wait, min(remaining, 1.0))
        else:
            await asyncio.sleep(min(remaining, 0.5))
        job = await run_in_threadpool(svc.get, job_id)
    return svc.out(job)
