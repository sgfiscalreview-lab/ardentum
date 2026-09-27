"""Engine construction (the app keeps its engine and sessionmaker on ``app.state``)."""

from __future__ import annotations

from sqlalchemy import URL, Engine, create_engine, event, make_url
from sqlalchemy.pool import StaticPool

# Query options that ORMs add to connection strings but libpq rejects
# ("invalid connection option"). Supabase's Prisma snippet ends in ?pgbouncer=true.
_NON_LIBPQ_OPTIONS = ("pgbouncer", "connection_limit", "pool_timeout", "schema")


def postgres_url(url: str) -> URL:
    """Parse a PostgreSQL URL for SQLAlchemy with the psycopg 3 driver."""
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.difference_update_query(_NON_LIBPQ_OPTIONS)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    # prepare_threshold=None disables server-side prepared statements, which are
    # incompatible with transaction-mode poolers such as Supabase's PgBouncer.
    return create_engine(
        postgres_url(url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"prepare_threshold": None},
    )
