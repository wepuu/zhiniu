from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    issuer_type: Mapped[str] = mapped_column(String(32), default="general")
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


class FinancialReportRevisionRecord(Base):
    __tablename__ = "financial_report_revisions"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "provider",
            "period_end",
            "statement_scope",
            "normalizer_version",
            "payload_checksum",
            name="uq_financial_report_revision_identity",
        ),
        Index("ix_financial_report_symbol_period", "symbol", "period_end"),
        Index("ix_financial_report_symbol_known_at", "symbol", "known_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    fiscal_year: Mapped[int]
    fiscal_period: Mapped[str] = mapped_column(String(4))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    statement_scope: Mapped[str] = mapped_column(String(24))
    currency: Mapped[str] = mapped_column(String(8))
    provider: Mapped[str] = mapped_column(String(40))
    provider_record_id: Mapped[str] = mapped_column(String(160))
    provider_revision: Mapped[str] = mapped_column(String(80))
    normalizer_version: Mapped[str] = mapped_column(String(40))
    payload_checksum: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at_precision: Mapped[str] = mapped_column(String(16))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_audited: Mapped[bool | None] = mapped_column(Boolean)
    issuer_type: Mapped[str] = mapped_column(String(32))
    quality_warnings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IncomeStatementRecord(Base):
    __tablename__ = "income_statement_facts"

    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_report_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_revenue: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    operating_cost: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    selling_expenses: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    administrative_expenses: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    research_expenses: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    finance_expenses: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    operating_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    total_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    income_tax_expense: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    parent_net_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))


class BalanceSheetRecord(Base):
    __tablename__ = "balance_sheet_facts"

    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_report_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cash: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    accounts_receivable: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    inventory: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    contract_assets: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    current_assets: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    short_term_borrowings: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    current_portion_noncurrent_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    long_term_borrowings: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    bonds_payable: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    lease_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    contract_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    current_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    total_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    parent_equity: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    goodwill: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))


class CashFlowStatementRecord(Base):
    __tablename__ = "cash_flow_statement_facts"

    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_report_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    investing_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    financing_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    cash_paid_for_long_term_assets: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))
    ending_cash: Mapped[Decimal | None] = mapped_column(Numeric(30, 4))


class FundamentalSnapshotRecord(Base):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "data_version", "metric_version", name="uq_fundamental_snapshot_identity"
        ),
        Index("ix_fundamental_snapshot_symbol_as_of", "symbol", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_version: Mapped[str] = mapped_column(String(64))
    metric_version: Mapped[str] = mapped_column(String(40))
    latest_period_end: Mapped[date | None] = mapped_column(Date)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FundamentalMetricRecord(Base):
    __tablename__ = "fundamental_metric_values"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "code", name="uq_fundamental_metric_snapshot_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("fundamental_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    unit: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32))
    period_end: Mapped[date | None] = mapped_column(Date)
    basis: Mapped[str] = mapped_column(String(24))
    input_report_ids: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    detail: Mapped[str | None] = mapped_column(String(240))


class ValuationObservationRecord(TimestampMixin, Base):
    __tablename__ = "valuation_observations"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_date",
            "metric_code",
            "provider",
            name="uq_valuation_observation_identity",
        ),
        Index("ix_valuation_symbol_metric_date", "symbol", "metric_code", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date)
    metric_code: Mapped[str] = mapped_column(String(40))
    value: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    unit: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(40))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
