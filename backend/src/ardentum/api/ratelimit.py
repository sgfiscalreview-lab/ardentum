"""In-process sliding-window rate limiting for compute-heavy endpoints.

A basic guard against accidental or abusive load: each client (authenticated
user, or IP address otherwise) may make ``limit`` compute requests per
``window`` seconds per worker process. Deployments with several instances
should add a shared limiter at the edge (e.g. the hosting platform's).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

COMPUTE_PATHS = frozenset(
    {
        "/api/v1/analytics",
        "/api/v1/optimise",
        "/api/v1/frontier",
        "/api/v1/esg/impact",
        "/api/v1/montecarlo",
        "/api/v1/backtest",
        "/api/v1/compare",
    }
)


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
