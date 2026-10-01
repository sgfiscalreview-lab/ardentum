"""close Supabase's public data API to the app's tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01 09:00:00.000000

Supabase publishes the ``public`` schema through its Data API
(``https://<ref>.supabase.co/rest/v1``) and, by default, grants every new table there to
its ``anon`` and ``authenticated`` roles. The website holds the publishable key for
sign-in, so without this anyone could read or change these tables directly, bypassing
the API's checks. Only the API uses the database, as the tables' owner, and row-level
security does not apply to a table's owner.

* Row-level security on every table, with no policies: the Data API sees no rows.
* The Data API roles lose every privilege on these tables, and on tables and sequences
  created later in ``public``.

On PostgreSQL servers without those roles (local, CI) only row-level security is
enabled. Nothing happens on SQLite. The downgrade turns row-level security off but does
not grant anything back: re-opening the tables is never wanted.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "alembic_version",
    "users",
    "datasets",
    "portfolios",
    "provider_cache",
    "rate_limit_counters",
    "usage_counts",
    "jobs",
    "esg_overlays",
)
DATA_API_ROLES = ("anon", "authenticated")


def _postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgres():
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
    tables = ", ".join(f'public."{t}"' for t in TABLES)
    roles = ", ".join(f"'{r}'" for r in DATA_API_ROLES)
    op.execute(
        f"""
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY[{roles}] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON TABLE {tables} FROM %I', r);
              EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
              EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
            END IF;
          END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    if not _postgres():
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
