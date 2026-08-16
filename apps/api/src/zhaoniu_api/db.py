from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")


class StockRecord(TimestampMixin, Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    exchange: Mapped[str] = mapped_column(String(16), index=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)


class WatchlistRecord(TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (Index("ix_watchlists_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80))
    items: Mapped[list["WatchlistItemRecord"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItemRecord(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    watchlist_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    watchlist: Mapped[WatchlistRecord] = relationship(back_populates="items")


class ResearchSnapshotRecord(Base):
    __tablename__ = "research_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "data_version",
            "research_template_version",
            "model_version",
            name="uq_research_snapshot_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), index=True)
    data_version: Mapped[str] = mapped_column(String(80))
    research_template_version: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str] = mapped_column(String(80))
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LLMCallRecord(Base):
    __tablename__ = "llm_calls"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    latency_ms: Mapped[int]
    cost_microunits: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanRecord(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SubscriptionRecord(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(32))
