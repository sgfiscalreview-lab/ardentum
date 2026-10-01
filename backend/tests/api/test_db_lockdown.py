"""The migrations close every table to Supabase's public Data API.

Supabase publishes the ``public`` schema at ``/rest/v1`` and grants new tables there to
its ``anon`` and ``authenticated`` roles; the website holds the key for those roles. This
recreates that setup on the test server, migrates, and checks that the roles can reach
nothing, including tables created later. A table added by a future migration without
row-level security fails here. PostgreSQL only (``ARDENTUM_TEST_DATABASE_URL``).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from ardentum.config import get_settings
from ardentum.db.models import Base
from ardentum.db.session import make_engine

PG_URL = os.environ.get("ARDENTUM_TEST_DATABASE_URL", "")
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
DATA_API_ROLES = ("anon", "authenticated")

pytestmark = pytest.mark.skipif(
    not PG_URL.startswith("postgres"), reason="needs ARDENTUM_TEST_DATABASE_URL (PostgreSQL)"
)


def _reset(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    engine = make_engine(PG_URL)
    _reset(engine)
    with engine.begin() as c:
        for role in DATA_API_ROLES:
            exists = c.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
            if not exists:
                c.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        # Supabase's defaults: the API roles may use the schema and get every new table.
        c.execute(text("GRANT USAGE ON SCHEMA public TO anon, authenticated"))
        c.execute(
            text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated"
            )
        )
    monkeypatch.setenv("ARDENTUM_DATABASE_URL", PG_URL)
    get_settings.cache_clear()
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "head")
    try:
        yield engine
    finally:
        command.downgrade(cfg, "base")
        _reset(engine)
        get_settings.cache_clear()
        engine.dispose()


def test_every_table_has_row_level_security_and_no_data_api_access(migrated: Engine) -> None:
    with migrated.connect() as c:
        rows = c.execute(
            text(
                "SELECT relname, relrowsecurity,"
                " has_table_privilege('anon', oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE'),"
                " has_table_privilege('authenticated', oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"
                " FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
            )
        ).all()
    tables = {r[0] for r in rows}
    assert set(Base.metadata.tables) | {"alembic_version"} <= tables
    assert [r[0] for r in rows if not r[1]] == [], "tables without row-level security"
    assert [r[0] for r in rows if r[2] or r[3]] == [], "tables the Data API roles can use"


def test_tables_created_later_are_not_granted_to_the_data_api(migrated: Engine) -> None:
    with migrated.begin() as c:
        c.execute(text("CREATE TABLE lockdown_probe (id integer)"))
        try:
            granted = c.scalar(
                text("SELECT has_table_privilege('anon', 'lockdown_probe', 'SELECT')")
            )
        finally:
            c.execute(text("DROP TABLE lockdown_probe"))
    assert granted is False
