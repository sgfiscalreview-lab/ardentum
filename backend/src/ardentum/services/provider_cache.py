"""Persistent cache for external data payloads (PostgreSQL), with an in-process layer.

Providers publish end-of-day or monthly data, so payloads are reused until they are
older than ``max_age``. If a refresh fails, the last good copy is served and the
caller is told it is stale (so the UI can say so) rather than failing outright.
"""

from __future__ import annotations

import datetime as dt
import gzip
import logging
import random
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ardentum.data.errors import DataProviderError
from ardentum.db.models import ProviderCache as CacheRow
from ardentum.db.session import end_read

log = logging.getLogger("ardentum.cache")
_MEMORY: OrderedDict[tuple[str, str], tuple[bytes, dt.datetime]] = OrderedDict()
_MEMORY_LIMIT = 64
_LOCK = threading.Lock()

# Providers whose keys keep growing (one row per ticker or per query) drop rows nobody
# has refreshed for this long; checked on about one write in PURGE_EVERY. Sources with a
# fixed set of files keep their rows, which are the stale fallback when a source is down.
PURGE_AFTER = {"wikirate": dt.timedelta(days=30), "tiingo": dt.timedelta(days=90)}
PURGE_EVERY = 50


@dataclass(frozen=True)
class CachedPayload:
    payload: bytes
    fetched_at: dt.datetime
    stale: bool = False


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _remember(k: tuple[str, str], payload: bytes, at: dt.datetime) -> None:
    with _LOCK:
        _MEMORY[k] = (payload, at)
        _MEMORY.move_to_end(k)
        while len(_MEMORY) > _MEMORY_LIMIT:
            _MEMORY.popitem(last=False)


def clear_memory() -> None:
    with _LOCK:
        _MEMORY.clear()


class ProviderCache:
    def __init__(self, session: Session | None) -> None:
        self.session = session

    def get_or_fetch(
        self,
        provider: str,
        key: str,
        max_age: dt.timedelta,
        fetch: Callable[[], bytes],
        validate: Callable[[bytes], object] | None = None,
        persist: bool = True,
    ) -> CachedPayload:
        """The payload for ``(provider, key)``: fresh from cache, else fetched.

        ``validate`` parses a fresh download and raises :class:`DataProviderError` if it is
        malformed (an error page served with status 200, a truncated archive); a payload
        that fails is never cached, and the last good copy is served as stale instead.
        ``persist=False`` keeps the payload in memory only (free-text searches, whose keys
        are unbounded and not worth a database row each).
        """
        k = (provider, key)
        now = _now()
        with _LOCK:
            mem = _MEMORY.get(k)
        if mem and now - mem[1] <= max_age:
            return CachedPayload(mem[0], mem[1])

        row: CacheRow | None = None
        if self.session is not None and persist:
            try:
                row = self.session.get(CacheRow, k)
            except SQLAlchemyError:
                log.warning("provider cache read failed for %s/%s", provider, key, exc_info=True)
                self.session.rollback()
            # The download below can take many seconds: do not hold a connection meanwhile.
            end_read(self.session)
        if row is not None and now - _aware(row.fetched_at) <= max_age:
            payload = gzip.decompress(row.payload)
            _remember(k, payload, _aware(row.fetched_at))
            return CachedPayload(payload, _aware(row.fetched_at))

        try:
            payload = fetch()
            if validate is not None:
                validate(payload)
        except DataProviderError:
            fallback = mem or (
                (gzip.decompress(row.payload), _aware(row.fetched_at)) if row else None
            )
            if fallback is None:
                raise
            log.warning("serving stale %s/%s after refresh failure", provider, key)
            return CachedPayload(fallback[0], fallback[1], stale=True)

        _remember(k, payload, now)
        if self.session is not None and persist:
            try:
                self.session.merge(
                    CacheRow(
                        provider=provider, key=key, fetched_at=now, payload=gzip.compress(payload)
                    )
                )
                if provider in PURGE_AFTER and random.randrange(PURGE_EVERY) == 0:
                    self.session.execute(
                        delete(CacheRow).where(
                            CacheRow.provider == provider,
                            CacheRow.fetched_at < now - PURGE_AFTER[provider],
                        )
                    )
                self.session.commit()
            except SQLAlchemyError:
                log.warning("provider cache write failed for %s/%s", provider, key, exc_info=True)
                self.session.rollback()
        return CachedPayload(payload, now)
