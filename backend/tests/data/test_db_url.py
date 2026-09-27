"""Connection strings as copied from Supabase's dashboard are accepted."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from ardentum.db.session import make_engine, postgres_url

SUPABASE_PRISMA = (
    "postgresql://postgres.abcdefghijklmnop:pa%3Fss.word@aws-0-ap-northeast-1.pooler.supabase.com"
    ":6543/postgres?pgbouncer=true"
)


def test_prisma_style_options_are_dropped_and_password_decoded() -> None:
    url = postgres_url(SUPABASE_PRISMA)
    assert url.drivername == "postgresql+psycopg"
    assert "pgbouncer" not in url.query
    assert url.password == "pa?ss.word"
    assert url.username == "postgres.abcdefghijklmnop"
    assert url.port == 6543


def test_libpq_options_are_kept() -> None:
    url = postgres_url("postgres://u:p@h:5432/db?sslmode=require&pgbouncer=true&schema=public")
    assert url.drivername == "postgresql+psycopg"
    assert dict(url.query) == {"sslmode": "require"}


def test_engine_connects_without_rejecting_the_url() -> None:
    # Nothing listens on port 1: the attempt must fail at the network, not with
    # psycopg's "invalid connection option" for the URL itself.
    engine = make_engine("postgresql://u:p%3F@127.0.0.1:1/db?pgbouncer=true&connect_timeout=2")
    with pytest.raises(OperationalError) as err:
        engine.connect()
    assert "invalid connection option" not in str(err.value)
