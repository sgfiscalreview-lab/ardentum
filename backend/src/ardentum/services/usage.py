"""Anonymous usage counts: how many calculations of each kind completed per UTC day.

Only the day, the kind and a number are stored; nothing links a count to a person, an
account, an address or a device. Requests marked as monitoring (the live smoke test) are
not counted. Counting never fails a request: database errors are logged and ignored.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ardentum.db.models import UsageCount

log = logging.getLogger(__name__)

MONITOR_HEADER = "x-ardentum-monitor"

CALCULATIONS = (
    "analytics",
    "optimise",
    "frontier",
    "cvar_frontier",
    "esg_impact",
    "montecarlo",
    "backtest",
    "compare",
)
OTHER_EVENTS = ("portfolio_saved", "portfolio_exported", "dataset_uploaded")
EVENTS = CALCULATIONS + OTHER_EVENTS

_POST_EVENTS = {
    "/api/v1/analytics": "analytics",
    "/api/v1/optimise": "optimise",
    "/api/v1/frontier": "frontier",
    "/api/v1/frontier/cvar": "cvar_frontier",
    "/api/v1/esg/impact": "esg_impact",
    "/api/v1/montecarlo": "montecarlo",
    "/api/v1/backtest": "backtest",
    "/api/v1/compare": "compare",
    "/api/v1/portfolios": "portfolio_saved",
    "/api/v1/datasets": "dataset_uploaded",
}
_EXPORT = re.compile(r"/api/v1/portfolios/[^/]+/export")


def event_for(method: str, path: str) -> str | None:
    """The usage event a successful request counts as, if any (jobs count on completion)."""
    if method == "POST":
        return _POST_EVENTS.get(path.rstrip("/") or path)
    if method == "GET" and _EXPORT.fullmatch(path):
        return "portfolio_exported"
    return None


def _today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def increment(session: Session, event: str, day: dt.date | None = None) -> None:
    """Add one to today's total for ``event`` inside the caller's transaction."""
    if event not in EVENTS:
        raise ValueError(f"Unknown usage event {event!r}.")
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    session.execute(
        insert(UsageCount)
        .values(day=day or _today(), event=event, count=1)
        .on_conflict_do_update(
            index_elements=["day", "event"], set_={"count": UsageCount.count + 1}
        )
    )


def record(factory: sessionmaker[Session], event: str, day: dt.date | None = None) -> None:
    """Count ``event`` in its own transaction; never raises for database errors."""
    try:
        with factory() as session, session.begin():
            increment(session, event, day)
    except SQLAlchemyError as exc:
        log.warning("usage count not recorded: %s", exc)


def increment_quietly(session: Session, event: str) -> None:
    """Count ``event`` in the caller's transaction without risking it: a failure only
    rolls back a savepoint around the count."""
    try:
        with session.begin_nested():
            increment(session, event)
    except SQLAlchemyError as exc:
        log.warning("usage count not recorded: %s", exc)


def summary(session: Session, today: dt.date | None = None) -> dict[str, object]:
    """Totals per event, the last 30 days (today included) and calculations per month."""
    today = today or _today()
    recent_from = today - dt.timedelta(days=29)
    rows = session.execute(select(UsageCount.day, UsageCount.event, UsageCount.count)).all()
    totals = dict.fromkeys(EVENTS, 0)
    recent = dict.fromkeys(EVENTS, 0)
    months: dict[str, int] = {}
    for day, event, count in rows:
        if event not in totals:
            continue
        totals[event] += count
        if recent_from <= day <= today:
            recent[event] += count
        if event in CALCULATIONS:
            key = f"{day.year:04d}-{day.month:02d}"
            months[key] = months.get(key, 0) + count
    since = session.scalar(select(func.min(UsageCount.day)))
    return {
        "since": since,
        "as_of": today,
        "total_calculations": sum(totals[e] for e in CALCULATIONS),
        "events": [{"event": e, "total": totals[e], "last_30_days": recent[e]} for e in EVENTS],
        "months": [{"month": m, "calculations": months[m]} for m in sorted(months)],
    }
