"""Rate limiting for compute-heavy endpoints.

Each client — the verified user, or the client IP address for anonymous or invalid
tokens — may make ``limit`` compute requests per ``window`` seconds.

Two stores implement the same ``check`` interface:

* :class:`RateLimiter` — in-process sliding log; exact, but per instance.
* :class:`DatabaseRateLimiter` — a sliding-window *counter* shared by all instances
  through one table: per key, counts for the current and previous fixed windows,
  with the estimate ``prev * (1 - elapsed) + current``. One atomic upsert per
  request (``INSERT ... ON CONFLICT DO UPDATE ... RETURNING``). If the database is
  unavailable the request is allowed and a warning is logged: rate limiting must
  not take the API down.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import defaultdict, deque
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ardentum.db.models import RateLimitCounter

log = logging.getLogger("ardentum.ratelimit")

COMPUTE_PATHS = frozenset(
    {
        "/api/v1/analytics",
        "/api/v1/optimise",
        "/api/v1/frontier",
        "/api/v1/esg/impact",
        "/api/v1/montecarlo",
        "/api/v1/backtest",
        "/api/v1/compare",
        "/api/v1/risk-free",
        "/api/v1/jobs",
    }
)


class Limiter(Protocol):
    def check(self, key: str, now: float | None = None) -> float | None: ...


class RateLimiter:
    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float | None:
        """Record a hit; return seconds to wait if the key is over its limit."""
        t = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= t - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return q[0] + self.window - t
            q.append(t)
            if len(self._hits) > 10_000:  # bound memory: drop idle keys
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return None


class DatabaseRateLimiter:
    def __init__(
        self, factory: sessionmaker[Session], limit: int, window: int = 60, purge_every: int = 100
    ) -> None:
        self.factory = factory
        self.limit = limit
        self.window = window
        self.purge_every = purge_every

    def _increment(self, session: Session, key: str, win: int) -> int:
        dialect = session.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        upsert = (
            insert(RateLimitCounter)
            .values(key=key, window=win, count=1)
            .on_conflict_do_update(
                index_elements=["key", "window"], set_={"count": RateLimitCounter.count + 1}
            )
            .returning(RateLimitCounter.count)
        )
        return int(session.execute(upsert).scalar_one())

    def check(self, key: str, now: float | None = None) -> float | None:
        t = time.time() if now is None else now
        win = int(t // self.window)
        elapsed = (t - win * self.window) / self.window
        try:
            with self.factory() as session, session.begin():
                current = self._increment(session, key[:80], win)
                previous = session.scalar(
                    select(RateLimitCounter.count).where(
                        RateLimitCounter.key == key[:80], RateLimitCounter.window == win - 1
                    )
                )
                if random.randrange(self.purge_every) == 0:
                    session.execute(
                        delete(RateLimitCounter).where(RateLimitCounter.window < win - 1)
                    )
        except SQLAlchemyError as exc:
            log.warning("rate limiter unavailable, allowing request: %s", exc)
            return None
        estimate = (previous or 0) * (1.0 - elapsed) + current
        if estimate <= self.limit:
            return None
        # Earliest time the estimate can fall back under the limit within this window,
        # otherwise the start of the next window.
        if previous and current <= self.limit:
            needed = 1.0 - (self.limit - current) / previous
            return max(0.0, (needed - elapsed) * self.window)
        return (1.0 - elapsed) * self.window


def client_ip(forwarded_for: str | None, peer: str | None, trusted_hops: int) -> str:
    """Client address: the socket peer, or the entry ``trusted_hops`` from the right of
    X-Forwarded-For (entries further left can be forged by the client)."""
    if trusted_hops > 0 and forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    return peer or "unknown"
