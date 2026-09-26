"""Relational schema (SQLAlchemy 2.0). PostgreSQL in production; SQLite for tests."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, LargeBinary, String, Text, func
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
