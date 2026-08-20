from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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
    base_plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id"))
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EmailVerificationTokenRecord(Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_email_verification_tokens_hash"),
        Index("ix_email_verification_tokens_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email_snapshot: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetTokenRecord(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_password_reset_tokens_hash"),
        Index("ix_password_reset_tokens_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionalEmailDeliveryRecord(Base):
    __tablename__ = "transactional_email_deliveries"
    __table_args__ = (Index("ix_transactional_email_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    template_key: Mapped[str] = mapped_column(String(48), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserLegalAcceptanceRecord(Base):
    __tablename__ = "user_legal_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "document_type", "document_version", name="uq_user_legal_acceptance"
        ),
        Index("ix_user_legal_acceptances_user", "user_id", "accepted_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(48), nullable=False)
    document_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserSessionRecord(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        Index("ix_user_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(240), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class IndustryTaxonomyRecord(TimestampMixin, Base):
    __tablename__ = "industry_taxonomies"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_industry_taxonomy_identity"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    commercial_use_status: Mapped[str] = mapped_column(String(80), nullable=False)
    redistribution_status: Mapped[str] = mapped_column(String(80), nullable=False)


class IndustryRecord(TimestampMixin, Base):
    __tablename__ = "industries"
    __table_args__ = (
        UniqueConstraint(
            "taxonomy_code",
            "taxonomy_version",
            "code",
            name="uq_industry_identity",
        ),
        Index("ix_industries_taxonomy", "taxonomy_code", "taxonomy_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    taxonomy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    level: Mapped[int] = mapped_column(nullable=False, default=1)
    parent_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class IndustryMembershipRecord(TimestampMixin, Base):
    __tablename__ = "industry_memberships"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "taxonomy_code",
            "taxonomy_version",
            "industry_code",
            "known_at",
            name="uq_industry_membership_identity",
        ),
        Index("ix_industry_membership_symbol", "symbol", "taxonomy_code", "known_at"),
        Index(
            "ix_industry_membership_industry",
            "taxonomy_code",
            "taxonomy_version",
            "industry_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    industry_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lineage_hash: Mapped[str] = mapped_column(String(64), nullable=False)


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


class PeerBenchmarkRunRecord(Base):
    __tablename__ = "peer_benchmark_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_peer_benchmark_run_idempotency"),
        Index("ix_peer_benchmark_run_symbol_started", "symbol", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    taxonomy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    peer_universe_fingerprint: Mapped[str | None] = mapped_column(String(64))
    comparison_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PeerBenchmarkSnapshotRecord(Base):
    __tablename__ = "peer_benchmark_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_peer_benchmark_snapshot_idempotency"),
        Index("ix_peer_benchmark_snapshot_industry", "industry_id", "knowledge_cutoff"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    industry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("industries.id", ondelete="RESTRICT"), nullable=False
    )
    taxonomy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    peer_universe_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PeerBenchmarkMetricResultRecord(Base):
    __tablename__ = "peer_benchmark_metric_results"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "metric_code", name="uq_peer_benchmark_metric"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("peer_benchmark_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_code: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    fiscal_period: Mapped[str | None] = mapped_column(String(12))
    period_end: Mapped[date | None] = mapped_column(Date)
    basis: Mapped[str | None] = mapped_column(String(24))
    unit: Mapped[str | None] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_size: Mapped[int] = mapped_column(default=0, nullable=False)
    median: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    p25: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    p75: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    excluded_invalid_value_count: Mapped[int] = mapped_column(default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))


class PeerBenchmarkInputRecord(Base):
    __tablename__ = "peer_benchmark_inputs"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_peer_benchmark_input_one_reference",
        ),
        Index("ix_peer_benchmark_inputs_result", "metric_result_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    metric_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("peer_benchmark_metric_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False, default=0)
    metric_point_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
    )
    valuation_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
    )


class CompanyPeerMetricPositionRecord(Base):
    __tablename__ = "company_peer_metric_positions"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "benchmark_metric_result_id",
            name="uq_company_peer_metric_position",
        ),
        Index("ix_company_peer_position_symbol", "symbol", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    benchmark_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("peer_benchmark_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    benchmark_metric_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("peer_benchmark_metric_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_point_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
    )
    valuation_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
    )
    metric_code: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    company_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    numeric_percentile: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    numeric_rank_desc: Mapped[int | None]
    sample_size: Mapped[int] = mapped_column(default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PeerPositionObservationRecord(Base):
    __tablename__ = "peer_position_observations"
    __table_args__ = (
        UniqueConstraint("content_fingerprint", name="uq_peer_position_observation_content"),
        Index("ix_peer_position_observation_symbol_known", "symbol", "known_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    company_peer_metric_position_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("company_peer_metric_positions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_family: Mapped[str] = mapped_column(String(120), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(48), nullable=False)
    attention_level: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(24), nullable=False)
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    detail_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FundamentalMetricPointRecord(Base):
    __tablename__ = "fundamental_metric_points"
    __table_args__ = (
        UniqueConstraint("input_fingerprint", name="uq_fundamental_metric_point_fingerprint"),
        Index(
            "ix_fundamental_metric_point_series",
            "symbol",
            "code",
            "period_end",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(12), nullable=False)
    basis: Mapped[str] = mapped_column(String(24), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_report_ids: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    input_valuation_ids: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WatchlistRecord(TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
        Index("ix_watchlists_user_created", "user_id", "created_at"),
        Index(
            "uq_watchlists_user_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    items: Mapped[list["WatchlistItemRecord"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItemRecord(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),
        Index("ix_watchlist_items_watchlist_created", "watchlist_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
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
            "metric_version",
            "rule_set_version",
            "producer_version",
            name="uq_research_snapshot_identity",
        ),
        Index("ix_research_snapshot_symbol_cutoff", "symbol", "knowledge_cutoff"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), index=True)
    data_version: Mapped[str] = mapped_column(String(80))
    research_template_version: Mapped[str] = mapped_column(String(40))
    metric_version: Mapped[str] = mapped_column(String(40))
    rule_set_version: Mapped[str] = mapped_column(String(80))
    snapshot_schema_version: Mapped[str] = mapped_column(String(40))
    producer_kind: Mapped[str] = mapped_column(String(24))
    producer_version: Mapped[str] = mapped_column(String(80))
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    input_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchObservationRecord(Base):
    __tablename__ = "research_observations"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "content_fingerprint", name="uq_research_observation_content"
        ),
        Index("ix_research_observation_symbol_snapshot", "symbol", "snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_family: Mapped[str] = mapped_column(String(120), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(48), nullable=False)
    attention_level: Mapped[str] = mapped_column(String(24), nullable=False)
    movement: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    current_period: Mapped[date] = mapped_column(Date, nullable=False)
    comparison_periods: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(24), nullable=False)
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    detail_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResearchObservationInputRecord(Base):
    __tablename__ = "research_observation_inputs"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN report_revision_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_research_observation_input_one_reference",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_observations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(48), primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    metric_point_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
    )
    report_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("financial_report_revisions.id", ondelete="RESTRICT"),
    )
    valuation_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
    )


class ResearchBuildRunRecord(Base):
    __tablename__ = "research_build_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    data_version: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    research_template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_snapshots.id", ondelete="SET NULL")
    )
    observation_count: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIResearchRunRecord(Base):
    __tablename__ = "ai_research_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_research_run_idempotency"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_ai_research_run_status",
        ),
        Index("ix_ai_research_run_symbol_started", "symbol", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    research_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    context_version: Mapped[str] = mapped_column(String(40), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_route_version: Mapped[str] = mapped_column(String(40), nullable=False)
    route_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_attempt: Mapped[int] = mapped_column(default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIResearchOutputRecord(Base):
    __tablename__ = "ai_research_outputs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_ai_research_output_run"),
        UniqueConstraint("idempotency_key", name="uq_ai_research_output_idempotency"),
        Index("ix_ai_research_output_symbol_generated", "symbol", "generated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_research_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    research_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    context_version: Mapped[str] = mapped_column(String(40), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_route_version: Mapped[str] = mapped_column(String(40), nullable=False)
    route_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coverage_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LLMCallRecord(Base):
    __tablename__ = "llm_calls"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ai_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_research_runs.id", ondelete="CASCADE"), index=True
    )
    parse_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("natural_language_screen_parse_runs.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    attempt_index: Mapped[int | None]
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(160))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    latency_ms: Mapped[int]
    cost_microunits: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32), index=True)
    finish_reason: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DisclosureDocumentRecord(Base):
    __tablename__ = "disclosure_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_owner", "source_document_id", name="uq_disclosure_source_identity"
        ),
        Index("ix_disclosure_symbol_published", "symbol", "source_published_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    source_owner: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_published_precision: Mapped[str] = mapped_column(String(16), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class DisclosureClassificationRecord(Base):
    __tablename__ = "disclosure_classifications"
    __table_args__ = (
        UniqueConstraint("document_id", "classifier_version", name="uq_disclosure_classification"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disclosure_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_family: Mapped[str | None] = mapped_column(String(40))
    event_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(40), nullable=False)
    matched_rule: Mapped[str | None] = mapped_column(String(120))
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CorporateEventSourceFactRecord(Base):
    __tablename__ = "corporate_event_source_facts"
    __table_args__ = (
        UniqueConstraint("source_owner", "source_fact_id", name="uq_corporate_event_source_fact"),
        Index("ix_corporate_event_fact_symbol_family", "symbol", "event_family"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    source_owner: Mapped[str] = mapped_column(String(40), nullable=False)
    source_fact_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_family: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matched_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("disclosure_documents.id", ondelete="SET NULL")
    )
    match_status: Mapped[str] = mapped_column(String(24), nullable=False)


class CorporateEventBuildRunRecord(Base):
    __tablename__ = "corporate_event_build_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_corporate_event_build_run"),
        Index("ix_corporate_event_build_run_symbol", "symbol", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_health: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    written_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorporateEventRecord(Base):
    __tablename__ = "corporate_events"
    __table_args__ = (
        UniqueConstraint("event_version_fingerprint", name="uq_corporate_event_version"),
        Index("ix_corporate_event_symbol_known", "symbol", "known_at"),
        Index("ix_corporate_event_thread", "event_thread_key", "known_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    event_family: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    event_thread_key: Mapped[str] = mapped_column(String(64), nullable=False)
    event_version_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_basis: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_events.id", ondelete="RESTRICT")
    )
    source_published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_published_precision: Mapped[str] = mapped_column(String(16), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_effective_from: Mapped[date | None] = mapped_column(Date)
    event_effective_to: Mapped[date | None] = mapped_column(Date)
    event_time_precision: Mapped[str | None] = mapped_column(String(16))
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False)
    typed_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    field_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorporateEventInputRecord(Base):
    __tablename__ = "corporate_event_inputs"
    __table_args__ = (
        UniqueConstraint("event_id", "document_id", name="uq_corporate_event_input_document"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_events.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disclosure_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_fact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_event_source_facts.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class EventRadarSnapshotRecord(Base):
    __tablename__ = "event_radar_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_event_radar_snapshot"),
        Index("ix_event_radar_snapshot_symbol_cutoff", "symbol", "knowledge_cutoff"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_health: Mapped[str] = mapped_column(String(24), nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventRadarSnapshotItemRecord(Base):
    __tablename__ = "event_radar_snapshot_items"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "event_id", name="uq_event_radar_snapshot_item"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("event_radar_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_events.id", ondelete="RESTRICT"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(24), nullable=False)
    attention_level: Mapped[str] = mapped_column(String(24), nullable=False)
    attention_rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    attention_rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    attention_reason: Mapped[str] = mapped_column(String(240), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)


class ResearchSignalRecord(Base):
    __tablename__ = "research_signals"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN research_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN peer_position_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN corporate_event_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_research_signal_one_source",
        ),
        UniqueConstraint("source_kind", "semantic_fingerprint", name="uq_research_signal_semantic"),
        Index("ix_research_signal_symbol_known", "symbol", "known_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    research_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_observations.id", ondelete="RESTRICT")
    )
    peer_position_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("peer_position_observations.id", ondelete="RESTRICT"),
    )
    corporate_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_events.id", ondelete="RESTRICT")
    )
    signal_family: Mapped[str] = mapped_column(String(120), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    attention_level: Mapped[str] = mapped_column(String(24), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_on: Mapped[date | None] = mapped_column(Date)
    dedup_group_key: Mapped[str] = mapped_column(String(128), nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(String(800), nullable=False)
    display_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchSignalProjectionRunRecord(Base):
    __tablename__ = "research_signal_projection_runs"
    __table_args__ = (
        UniqueConstraint(
            "source_kind",
            "source_artifact_identity",
            "projection_version",
            name="uq_research_signal_projection_run",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_artifact_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    projected_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserResearchAlertSettingsRecord(Base):
    __tablename__ = "user_research_alert_settings"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_attention: Mapped[str] = mapped_column(String(24), default="important", nullable=False)
    fundamental_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    peer_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    corporate_event_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings_version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ScreeningSnapshotRecord(Base):
    __tablename__ = "screening_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_screening_snapshot_idempotency"),
        Index("ix_screening_snapshot_cutoff", "knowledge_cutoff", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    taxonomy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    peer_producer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    event_radar_version: Mapped[str] = mapped_column(String(40), nullable=False)
    selector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScreeningSnapshotMemberRecord(Base):
    __tablename__ = "screening_snapshot_members"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "symbol", name="uq_screening_snapshot_member"),
        Index("ix_screening_snapshot_member_status", "snapshot_id", "eligibility_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("screening_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    issuer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(24), nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(120))


class ScreeningSnapshotFactRecord(Base):
    __tablename__ = "screening_snapshot_facts"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN peer_position_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN industry_membership_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN event_radar_snapshot_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_screening_fact_one_source",
        ),
        UniqueConstraint(
            "snapshot_id", "symbol", "criterion_key", name="uq_screening_snapshot_fact"
        ),
        Index("ix_screening_fact_lookup", "snapshot_id", "criterion_key", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("screening_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    criterion_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_point_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT")
    )
    valuation_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("valuation_observations.id", ondelete="RESTRICT")
    )
    peer_position_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("company_peer_metric_positions.id", ondelete="RESTRICT"),
    )
    industry_membership_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("industry_memberships.id", ondelete="RESTRICT")
    )
    event_radar_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("event_radar_snapshots.id", ondelete="RESTRICT")
    )


class ScreenExecutionRecord(Base):
    __tablename__ = "screen_executions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "screening_snapshot_id",
            "query_hash",
            "engine_version",
            name="uq_screen_execution_identity",
        ),
        Index("ix_screen_execution_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    screening_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("screening_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_query: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_count: Mapped[int] = mapped_column(default=0, nullable=False)
    evaluated_count: Mapped[int] = mapped_column(default=0, nullable=False)
    unknown_count: Mapped[int] = mapped_column(default=0, nullable=False)
    excluded_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NaturalLanguageScreenParseRunRecord(Base):
    __tablename__ = "natural_language_screen_parse_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "input_hash", "parser_route_hash", name="uq_nl_parse_run"),
        Index("ix_nl_parse_user_created", "user_id", "created_at"),
        Index("ix_nl_parse_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_length: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    semantic_status: Mapped[str | None] = mapped_column(String(32))
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(40), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    criteria_contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_route_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_attempt: Mapped[int] = mapped_column(default=0, nullable=False)
    output_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(300))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedScreenRecord(Base):
    __tablename__ = "saved_screens"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_saved_screen_user_name"),
        Index("ix_saved_screen_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(240))
    canonical_query: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dsl_version: Mapped[str] = mapped_column(String(40), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(40), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    criteria_contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_parse_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("natural_language_screen_parse_runs.id", ondelete="SET NULL"),
    )
    original_text: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ScreenExecutionRequestRecord(Base):
    __tablename__ = "screen_execution_requests"
    __table_args__ = (Index("ix_screen_execution_request_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("screen_executions.id", ondelete="CASCADE"), nullable=False
    )
    saved_screen_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("saved_screens.id", ondelete="SET NULL")
    )
    confirmed_parse_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("natural_language_screen_parse_runs.id", ondelete="SET NULL"),
    )
    request_source: Mapped[str] = mapped_column(String(24), nullable=False)
    reused_execution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScreenResultRecord(Base):
    __tablename__ = "screen_results"
    __table_args__ = (
        UniqueConstraint("execution_id", "symbol", name="uq_screen_result_symbol"),
        UniqueConstraint("execution_id", "ordinal", name="uq_screen_result_ordinal"),
        Index("ix_screen_result_execution", "execution_id", "ordinal"),
        Index("ix_screen_result_symbol", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("screen_executions.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(nullable=False)
    sort_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    matched_condition_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class UserResearchAlertDeliveryRecord(Base):
    __tablename__ = "user_research_alert_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "signal_id", name="uq_user_research_alert_delivery"),
        Index("ix_user_research_alert_unread", "user_id", "read_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_signals.id", ondelete="CASCADE"), nullable=False
    )
    delivery_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    settings_version: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchAlertDispatchRunRecord(Base):
    __tablename__ = "research_alert_dispatch_runs"
    __table_args__ = (
        UniqueConstraint("signal_id", "matcher_version", name="uq_research_alert_dispatch_run"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    signal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_signals.id", ondelete="CASCADE"), nullable=False
    )
    matcher_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matched_user_count: Mapped[int] = mapped_column(default=0, nullable=False)
    delivery_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanRecord(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSONB)


class PlanVersionRecord(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubscriptionRecord(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_subscriptions_user"),
        CheckConstraint(
            "current_period_end > current_period_start", name="ck_subscriptions_period"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32))
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activation_source: Mapped[str] = mapped_column(
        String(32), default="activation_code", nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegistrationInviteBatchRecord(Base):
    __tablename__ = "registration_invite_batches"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_registration_invite_batch_quantity"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_operator: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegistrationInviteRecord(Base):
    __tablename__ = "registration_invites"
    __table_args__ = (
        UniqueConstraint("code_hmac", name="uq_registration_invites_code_hmac"),
        Index("ix_registration_invites_prefix", "code_prefix"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("registration_invite_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccessActivationBatchRecord(Base):
    __tablename__ = "access_activation_batches"
    __table_args__ = (
        CheckConstraint("term_kind IN ('month', 'year')", name="ck_access_batch_term"),
        CheckConstraint("quantity > 0", name="ck_access_batch_quantity"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id"), nullable=False)
    term_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_operator: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessActivationCodeRecord(Base):
    __tablename__ = "access_activation_codes"
    __table_args__ = (
        UniqueConstraint("code_hmac", name="uq_access_activation_codes_code_hmac"),
        Index("ix_access_activation_codes_prefix", "code_prefix"),
        Index("ix_access_activation_codes_user", "assigned_user_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("access_activation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    assigned_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccessActivationRedemptionRecord(Base):
    __tablename__ = "access_activation_redemptions"
    __table_args__ = (
        UniqueConstraint("activation_code_id", name="uq_access_redemptions_code"),
        CheckConstraint("term_kind IN ('month', 'year')", name="ck_access_redemption_term"),
        CheckConstraint("new_period_end > new_period_start", name="ck_access_redemption_period"),
        Index("ix_access_activation_redemptions_user", "user_id", "redeemed_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activation_code_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("access_activation_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id"), nullable=False)
    term_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
