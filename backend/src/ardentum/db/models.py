"""Relational schema (SQLAlchemy 2.0). PostgreSQL in production; SQLite for tests."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class User(Base):
    """A user known to Ardentum. ``id`` is the identity provider's subject (``sub``)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    portfolios: Mapped[list[Portfolio]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    datasets: Mapped[list[Dataset]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Dataset(Base):
    """A user-uploaded price dataset. Prices are stored as gzip-compressed canonical CSV."""

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    prices_csv_gz: Mapped[bytes] = mapped_column(LargeBinary)
    assets: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    start_date: Mapped[dt.date | None]
    end_date: Mapped[dt.date | None]
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="datasets")


class Portfolio(Base):
    """A saved portfolio: weights plus the exact specification that produced them."""

    __tablename__ = "portfolios"
    __table_args__ = (Index("ix_portfolios_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    dataset_id: Mapped[str] = mapped_column(String(64))
    weights: Mapped[dict[str, float]] = mapped_column(JsonType)
    spec: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="portfolios")


class ProviderCache(Base):
    """Raw payloads from external data providers (gzip), shared by all API instances."""

    __tablename__ = "provider_cache"

    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[bytes] = mapped_column(LargeBinary)


class RateLimitCounter(Base):
    """Requests per client per fixed window, shared by every API instance."""

    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # epoch // window length
    count: Mapped[int] = mapped_column(Integer, default=0)


class Job(Base):
    """A long-running computation, executed by whichever API instance polls it.

    Result payloads are gzip-compressed JSON of the corresponding synchronous response.
    ``owner_id`` is set for signed-in users (only they may read the job); anonymous jobs
    are readable by anyone holding their random id.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), index=True)  # queued/running/succeeded/failed
    request: Mapped[dict[str, Any]] = mapped_column(JsonType)
    result: Mapped[bytes | None] = mapped_column(LargeBinary)
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class EsgOverlay(Base):
    """ESG scores for a dataset's assets built from open data (e.g. WikiRate).

    ``entries`` holds, per ticker, the matched company, the answer year, raw value,
    derived 0-100 score and a link to the source answer; ``spec`` the metric and
    transform so the overlay can be explained and rebuilt.
    """

    __tablename__ = "esg_overlays"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    dataset_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(40))
    spec: Mapped[dict[str, Any]] = mapped_column(JsonType)
    entries: Mapped[list[dict[str, Any]]] = mapped_column(JsonType)
    license: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
