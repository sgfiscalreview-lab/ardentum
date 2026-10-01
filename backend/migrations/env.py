"""Alembic environment: uses ARDENTUM_DATABASE_URL and the ORM metadata."""

from __future__ import annotations

from alembic import context

from ardentum.config import Environment, get_settings
from ardentum.db.models import Base
from ardentum.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url, settings.env is Environment.PRODUCTION)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
