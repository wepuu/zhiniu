from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        Index("ix_users_email", "email", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")


class StockRecord(TimestampMixin, Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), nullable=False)
    name: Mapped[str] = mapped_column(String(120))
    exchange: Mapped[str] = mapped_column(String(16), index=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(24), default="stock")
    board: Mapped[str] = mapped_column(String(24), default="unknown")
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="listed")
    source: Mapped[str] = mapped_column(String(40))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("ticker", "exchange", name="uq_stocks_ticker_exchange"),)


class StockDailyBarRecord(TimestampMixin, Base):
    __tablename__ = "stock_daily_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", "adjust_type", name="uq_stock_daily_bar_identity"),
        Index("ix_stock_daily_bars_symbol_date", "symbol", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjust_type: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    open: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(30, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataSyncRunRecord(Base):
    __tablename__ = "data_sync_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    requested_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    received_count: Mapped[int] = mapped_column(default=0)
    written_count: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
