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
    __table_args__ = (
        Index("ix_transactional_email_user_created", "user_id", "created_at"),
        Index(
            "ix_transactional_email_logical_key",
            "logical_delivery_key",
            unique=True,
            postgresql_where=text("logical_delivery_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    template_key: Mapped[str] = mapped_column(String(48), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logical_delivery_key: Mapped[str | None] = mapped_column(String(96), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    operator_elevated_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OperatorMembershipRecord(Base):
    __tablename__ = "operator_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('viewer', 'support', 'operations', 'security_admin')",
            name="ck_operator_membership_role",
        ),
        Index(
            "uq_operator_membership_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_operator_membership_role_active",
            "role",
            "created_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperatorAuditEventRecord(Base):
    __tablename__ = "operator_audit_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('succeeded', 'denied', 'failed')", name="ck_operator_audit_result"
        ),
        Index("ix_operator_audit_created", "created_at", "action_key"),
        Index("ix_operator_audit_actor", "actor_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action_key: Mapped[str] = mapped_column(String(96), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120))
    request_id: Mapped[str | None] = mapped_column(String(80))
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(96))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProviderDiagnosticRunRecord(Base):
    __tablename__ = "provider_diagnostic_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('disabled', 'unknown', 'healthy', 'degraded', 'unavailable')",
            name="ck_provider_diagnostic_status",
        ),
        CheckConstraint(
            "target IN ('active', 'draft')",
            name="ck_provider_diagnostic_target",
        ),
        Index("ix_provider_diagnostic_latest", "provider", "capability", "checked_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    latency_ms: Mapped[int | None]
    reason_code: Mapped[str | None] = mapped_column(String(96))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    configuration_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_configuration_revisions.id", ondelete="SET NULL"),
    )
    credential_generation: Mapped[int | None]
    target: Mapped[str] = mapped_column(String(16), default="active", nullable=False)


class ProviderConfigurationRecord(Base):
    __tablename__ = "provider_configurations"
    __table_args__ = (
        UniqueConstraint("provider", "environment", name="uq_provider_configuration_scope"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    environment: Mapped[str] = mapped_column(String(24), nullable=False)
    active_revision: Mapped[int | None]
    draft_revision: Mapped[int | None]
    row_version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProviderConfigurationRevisionRecord(Base):
    __tablename__ = "provider_configuration_revisions"
    __table_args__ = (
        UniqueConstraint("configuration_id", "revision", name="uq_provider_configuration_revision"),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_provider_configuration_revision_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    configuration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_configurations.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column("configuration", JSONB)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_generation: Mapped[int | None]
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderCredentialRecord(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("configuration_id", "slot", name="uq_provider_credential_slot"),
        CheckConstraint("slot IN ('active', 'candidate')", name="ck_provider_credential_slot"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    configuration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_configurations.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    key_id: Mapped[str] = mapped_column(String(48), nullable=False)
    generation: Mapped[int] = mapped_column(nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransactionalEmailProviderEventRecord(Base):
    __tablename__ = "transactional_email_provider_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_transactional_email_provider_event"
        ),
        Index(
            "ix_email_provider_event_message",
            "provider",
            "provider_message_id",
            "event_created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    event_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(96))


class StockRecord(TimestampMixin, Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), nullable=False)
    name: Mapped[str] = mapped_column(String(120))
    search_name: Mapped[str] = mapped_column(
        String(120), nullable=False, default="", server_default=""
    )
    name_pinyin: Mapped[str] = mapped_column(
        String(240), nullable=False, default="", server_default=""
    )
    name_pinyin_initials: Mapped[str] = mapped_column(
        String(120), nullable=False, default="", server_default=""
    )
    exchange: Mapped[str] = mapped_column(String(16), index=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(24), default="stock")
    board: Mapped[str] = mapped_column(String(24), default="unknown")
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="listed")
    issuer_type: Mapped[str] = mapped_column(String(32), default="general")
    source: Mapped[str] = mapped_column(String(40))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_stocks_ticker_exchange"),
        Index(
            "ix_stocks_search_name_prefix",
            "search_name",
            postgresql_ops={"search_name": "varchar_pattern_ops"},
        ),
        Index(
            "ix_stocks_name_pinyin_prefix",
            "name_pinyin",
            postgresql_ops={"name_pinyin": "varchar_pattern_ops"},
        ),
        Index(
            "ix_stocks_name_pinyin_initials_prefix",
            "name_pinyin_initials",
            postgresql_ops={"name_pinyin_initials": "varchar_pattern_ops"},
        ),
    )


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


class ProviderAcceptanceRunRecord(Base):
    __tablename__ = "provider_acceptance_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('passed', 'failed', 'blocked')",
            name="ck_provider_acceptance_run_status",
        ),
        Index("ix_provider_acceptance_latest", "environment", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    usage_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    mandatory_items: Mapped[int] = mapped_column(default=0, nullable=False)
    succeeded_items: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_items: Mapped[int] = mapped_column(default=0, nullable=False)
    blocked_items: Mapped[int] = mapped_column(default=0, nullable=False)
    unsupported_items: Mapped[int] = mapped_column(default=0, nullable=False)
    beta_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProviderAcceptanceItemRecord(Base):
    __tablename__ = "provider_acceptance_items"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "provider",
            "dataset",
            "symbol",
            "scenario",
            name="uq_provider_acceptance_item",
        ),
        CheckConstraint(
            "requirement IN ('mandatory', 'conditional', 'optional')",
            name="ck_provider_acceptance_item_requirement",
        ),
        CheckConstraint(
            "status IN ('passed', 'failed', 'blocked', 'unsupported')",
            name="ck_provider_acceptance_item_status",
        ),
        Index("ix_provider_acceptance_item_run_status", "run_id", "status", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_acceptance_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT")
    )
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(120))
    observed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    latest_artifact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    question_key: Mapped[str | None] = mapped_column(String(64))
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
        Index(
            "ix_ai_research_output_explanation",
            "symbol",
            "question_key",
            "generated_at",
        ),
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
    question_key: Mapped[str | None] = mapped_column(String(64))
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


class AIExplanationRequestRecord(Base):
    __tablename__ = "ai_explanation_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_ai_explanation_user_client"),
        CheckConstraint(
            "status IN ('pending', 'building', 'ready', 'failed')",
            name="ck_ai_explanation_request_status",
        ),
        Index("ix_ai_explanation_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False
    )
    question_key: Mapped[str] = mapped_column(String(64), nullable=False)
    client_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_research_runs.id", ondelete="SET NULL")
    )
    output_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_research_outputs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    quota_day: Mapped[date] = mapped_column(Date, nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIExplanationDailyUsageRecord(Base):
    __tablename__ = "ai_explanation_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_day", name="uq_ai_explanation_usage_day"),
        CheckConstraint("used_count >= 0", name="ck_ai_explanation_usage_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    quota_day: Mapped[date] = mapped_column(Date, nullable=False)
    used_count: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    comparison_ai_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comparison_ai_runs.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    attempt_index: Mapped[int | None]
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(160))
    requested_model: Mapped[str | None] = mapped_column(String(160))
    actual_model: Mapped[str | None] = mapped_column(String(160))
    capability_mode: Mapped[str | None] = mapped_column(String(32))
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
        Index("ix_disclosure_symbol_known", "symbol", text("known_at DESC")),
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
        Index("ix_corporate_event_build_runs_status", "status"),
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
        Index(
            "ix_corporate_event_symbol_family_known",
            "symbol",
            "event_family",
            text("known_at DESC"),
            text("id DESC"),
        ),
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
        Index(
            "ix_research_signal_symbol_known",
            "symbol",
            text("known_at DESC"),
            text("id DESC"),
        ),
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
    projection_mode: Mapped[str] = mapped_column(
        String(24), nullable=False, default="historical_backfill"
    )
    alert_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
        UniqueConstraint("code_hmac", name="registration_invites_code_hmac_key"),
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


class BetaInviteCohortRecord(Base):
    __tablename__ = "beta_invite_cohorts"
    __table_args__ = (
        CheckConstraint("target_size > 0 AND target_size <= 100", name="ck_beta_cohort_size"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'dispatching', 'active', "
            "'paused', 'closed', 'cancelled')",
            name="ck_beta_cohort_status",
        ),
        Index("ix_beta_cohort_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    target_size: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acceptance_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("provider_acceptance_runs.id", ondelete="RESTRICT")
    )
    invite_batch_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("registration_invite_batches.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reason_code: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BetaInviteRecipientRecord(Base):
    __tablename__ = "beta_invite_recipients"
    __table_args__ = (
        UniqueConstraint("cohort_id", "email_hmac", name="uq_beta_cohort_recipient_email"),
        UniqueConstraint("invite_id", name="uq_beta_recipient_invite"),
        UniqueConstraint("delivery_id", name="uq_beta_recipient_delivery"),
        CheckConstraint(
            "status IN ('staged', 'queued', 'registered', 'withdrawn', 'expired', 'failed')",
            name="ck_beta_recipient_status",
        ),
        Index("ix_beta_recipient_email", "email_hmac", "status"),
        Index("ix_beta_recipient_cohort_status", "cohort_id", "status"),
        Index("ix_beta_recipient_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cohort_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("beta_invite_cohorts.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    invite_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("registration_invites.id", ondelete="SET NULL")
    )
    delivery_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transactional_email_deliveries.id", ondelete="SET NULL")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BetaOnboardingStateRecord(Base):
    __tablename__ = "beta_onboarding_states"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("beta_invite_recipients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
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
        UniqueConstraint("code_hmac", name="access_activation_codes_code_hmac_key"),
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
        UniqueConstraint(
            "activation_code_id",
            name="access_activation_redemptions_activation_code_id_key",
        ),
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


class BetaResearchUniverseSnapshotRecord(Base):
    __tablename__ = "beta_research_universe_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "universe_fingerprint",
            name="beta_research_universe_snapshots_universe_fingerprint_key",
        ),
        Index("ix_beta_universe_cutoff", "knowledge_cutoff", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BetaResearchUniverseMemberRecord(Base):
    __tablename__ = "beta_research_universe_members"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "symbol", name="uq_beta_universe_member"),
        Index("ix_beta_universe_member_priority", "snapshot_id", "priority_rank", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("beta_research_universe_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    priority_rank: Mapped[int] = mapped_column(nullable=False)
    reason_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchCoverageSnapshotRecord(Base):
    __tablename__ = "research_coverage_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "content_fingerprint",
            name="research_coverage_snapshots_content_fingerprint_key",
        ),
        Index("ix_research_coverage_cutoff", "knowledge_cutoff", "evaluated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    universe_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("beta_research_universe_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchCoverageMemberRecord(Base):
    __tablename__ = "research_coverage_members"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "symbol", name="uq_research_coverage_member"),
        Index("ix_research_coverage_member_symbol", "symbol", "snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_coverage_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    dimension_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoverageBackfillRunRecord(Base):
    __tablename__ = "coverage_backfill_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="coverage_backfill_runs_idempotency_key_key"),
        Index("ix_coverage_backfill_run_status", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    universe_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("beta_research_universe_snapshots.id"), nullable=False
    )
    coverage_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_coverage_snapshots.id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    target_profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    planned_items: Mapped[int] = mapped_column(default=0, nullable=False)
    succeeded_items: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_items: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_items: Mapped[int] = mapped_column(default=0, nullable=False)
    blocked_items: Mapped[int] = mapped_column(default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoverageBackfillItemRecord(Base):
    __tablename__ = "coverage_backfill_items"
    __table_args__ = (
        UniqueConstraint("run_id", "symbol", "action_key", name="uq_coverage_backfill_item"),
        Index("ix_coverage_backfill_item_claim", "run_id", "status", "dependency_order"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("coverage_backfill_runs.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    action_key: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    dependency_order: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    before_fingerprint: Mapped[str | None] = mapped_column(String(64))
    after_fingerprint: Mapped[str | None] = mapped_column(String(64))
    changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_call_count: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_received: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_written: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationPolicyRecord(Base):
    __tablename__ = "automation_policies"
    __table_args__ = (UniqueConstraint("policy_key", name="uq_automation_policy_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "automation_policy_revisions.id",
            name="fk_automation_policy_current_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AutomationPolicyRevisionRecord(Base):
    __tablename__ = "automation_policy_revisions"
    __table_args__ = (
        UniqueConstraint("policy_id", "revision", name="uq_automation_policy_revision"),
        UniqueConstraint("policy_id", "configuration_hash", name="uq_automation_policy_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_policies.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AutomationRunRecord(Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_automation_run_idempotency"),
        Index("ix_automation_run_status_created", "status", "created_at"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'succeeded_with_warnings', "
            "'partial', 'failed', 'blocked', 'skipped')",
            name="ck_automation_run_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_policies.id", ondelete="RESTRICT")
    )
    policy_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_policy_revisions.id", ondelete="RESTRICT")
    )
    universe_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("beta_research_universe_snapshots.id")
    )
    trigger_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    universe_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    universe_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_steps: Mapped[int] = mapped_column(default=0, nullable=False)
    succeeded_steps: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_steps: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_steps: Mapped[int] = mapped_column(default=0, nullable=False)
    warning_steps: Mapped[int] = mapped_column(default=0, nullable=False)
    provider_call_count: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_received: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_written: Mapped[int] = mapped_column(default=0, nullable=False)
    signal_count: Mapped[int] = mapped_column(default=0, nullable=False)
    alert_count: Mapped[int] = mapped_column(default=0, nullable=False)
    ai_output_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AutomationRunStepRecord(Base):
    __tablename__ = "automation_run_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "scope_type", "scope_key", "step_key", name="uq_automation_run_step"
        ),
        Index("ix_automation_step_claim", "run_id", "status", "dependency_order"),
        Index("ix_automation_step_symbol_status", "symbol", "status", "created_at"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked')",
            name="ck_automation_step_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_runs.id", ondelete="CASCADE")
    )
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(180), nullable=False)
    symbol: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT")
    )
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    dependency_order: Mapped[int] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    before_fingerprint: Mapped[str | None] = mapped_column(String(64))
    after_fingerprint: Mapped[str | None] = mapped_column(String(64))
    changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_call_count: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_received: Mapped[int] = mapped_column(default=0, nullable=False)
    rows_written: Mapped[int] = mapped_column(default=0, nullable=False)
    duration_ms: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AutomationStepAttemptRecord(Base):
    __tablename__ = "automation_step_attempts"
    __table_args__ = (
        UniqueConstraint("step_id", "attempt_number", name="uq_automation_step_attempt"),
        Index("ix_automation_step_attempt_started", "step_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    step_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_run_steps.id", ondelete="CASCADE")
    )
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    duration_ms: Mapped[int | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComparisonSnapshotRecord(Base):
    __tablename__ = "comparison_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_comparison_snapshot_idempotency"),
        Index(
            "ix_comparison_snapshot_pair_created",
            "canonical_symbol_low",
            "canonical_symbol_high",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    canonical_symbol_low: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    canonical_symbol_high: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    comparison_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    comparison_rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coverage_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    limitation_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ComparisonBuildRunRecord(Base):
    __tablename__ = "comparison_build_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_comparison_build_run_idempotency"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_comparison_build_run_status",
        ),
        Index("ix_comparison_build_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    canonical_symbol_low: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    canonical_symbol_high: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    requested_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("comparison_snapshots.id", ondelete="SET NULL")
    )
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ComparisonAIRunRecord(Base):
    __tablename__ = "comparison_ai_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_comparison_ai_run_idempotency"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_comparison_ai_run_status",
        ),
        Index("ix_comparison_ai_run_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comparison_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    context_version: Mapped[str] = mapped_column(String(40), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_route_version: Mapped[str] = mapped_column(String(40), nullable=False)
    route_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_attempt: Mapped[int] = mapped_column(default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ComparisonAIOutputRecord(Base):
    __tablename__ = "comparison_ai_outputs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_comparison_ai_output_run"),
        UniqueConstraint("idempotency_key", name="uq_comparison_ai_output_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comparison_ai_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comparison_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context_version: Mapped[str] = mapped_column(String(40), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_route_version: Mapped[str] = mapped_column(String(40), nullable=False)
    route_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ComparisonRequestRecord(Base):
    __tablename__ = "comparison_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_comparison_request_user_client"),
        CheckConstraint(
            "status IN ('pending', 'building', 'ready', 'partial', 'failed', 'unsupported')",
            name="ck_comparison_request_status",
        ),
        Index("ix_comparison_request_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    client_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    left_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    right_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    include_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    build_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("comparison_build_runs.id", ondelete="SET NULL")
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("comparison_snapshots.id", ondelete="SET NULL")
    )
    ai_output_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("comparison_ai_outputs.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedComparisonRecord(Base):
    __tablename__ = "saved_comparisons"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_saved_comparison_user_name"),
        Index("ix_saved_comparison_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False)
    left_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    right_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="RESTRICT"), nullable=False
    )
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    latest_request_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("comparison_requests.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BetaFeedbackItemRecord(Base):
    __tablename__ = "beta_feedback_items"
    __table_args__ = (
        Index("ix_beta_feedback_status_created", "status", "created_at"),
        Index("ix_beta_feedback_user_created", "user_id", "created_at"),
        Index(
            "ix_beta_feedback_severity_status",
            "severity",
            "status",
            "created_at",
        ),
        CheckConstraint(
            "severity IN ('P0', 'P1', 'P2', 'P3')",
            name="ck_beta_feedback_severity",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String(48), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="new", nullable=False)
    severity: Mapped[str] = mapped_column(
        String(2), default="P2", server_default="P2", nullable=False
    )
    assigned_operator_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_code: Mapped[str | None] = mapped_column(String(64))
    internal_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProductionReleaseCandidateRecord(Base):
    __tablename__ = "production_release_candidates"
    __table_args__ = (
        UniqueConstraint(
            "target_environment",
            "commit_sha",
            "configuration_fingerprint",
            name="uq_release_candidate_identity",
        ),
        CheckConstraint("target_environment = 'production'", name="ck_release_candidate_env"),
        CheckConstraint(
            "status IN ('draft', 'blocked', 'ready_closed', 'deployed_observing', "
            "'ready_invites', 'released', 'rolled_back', 'rejected')",
            name="ck_release_candidate_status",
        ),
        CheckConstraint(
            "quality_gate_status IN ('passed', 'failed') AND "
            "e2e_status IN ('passed', 'failed') AND "
            "security_scan_status IN ('passed', 'failed')",
            name="ck_release_candidate_evidence_status",
        ),
        Index("ix_release_candidate_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    migration_head: Mapped[str] = mapped_column(String(32), nullable=False)
    api_image_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    web_image_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    sbom_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    restore_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_gate_status: Mapped[str] = mapped_column(String(16), nullable=False)
    e2e_status: Mapped[str] = mapped_column(String(16), nullable=False)
    security_scan_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductionReleaseGateRunRecord(Base):
    __tablename__ = "production_release_gate_runs"
    __table_args__ = (
        CheckConstraint(
            "gate_type IN ('closed_deployment', 'invite_activation')",
            name="ck_release_gate_type",
        ),
        CheckConstraint("status IN ('passed', 'blocked')", name="ck_release_gate_status"),
        Index("ix_release_gate_candidate_started", "candidate_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("production_release_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    gate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductionReleaseGateItemRecord(Base):
    __tablename__ = "production_release_gate_items"
    __table_args__ = (
        UniqueConstraint("run_id", "check_key", name="uq_release_gate_item_key"),
        CheckConstraint(
            "status IN ('passed', 'failed', 'not_applicable')", name="ck_release_item_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("production_release_gate_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_key: Mapped[str] = mapped_column(String(96), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(120))
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductionReleaseApprovalRecord(Base):
    __tablename__ = "production_release_approvals"
    __table_args__ = (
        UniqueConstraint("candidate_id", "approval_role", name="uq_release_approval_role"),
        UniqueConstraint("candidate_id", "actor_user_id", name="uq_release_approval_actor"),
        CheckConstraint(
            "approval_role IN ('engineering', 'data_compliance', 'product_operations')",
            name="ck_release_approval_role",
        ),
        CheckConstraint(
            "decision IN ('approved', 'rejected')", name="ck_release_approval_decision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("production_release_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    approval_role: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductionDeploymentEventRecord(Base):
    __tablename__ = "production_deployment_events"
    __table_args__ = (
        UniqueConstraint("candidate_id", "event_type", name="uq_deployment_candidate_event"),
        CheckConstraint(
            "event_type IN ('deployed', 'released', 'failed', 'rolled_back')",
            name="ck_deployment_event_type",
        ),
        Index("ix_deployment_event_candidate_created", "candidate_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("production_release_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    deployment_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(120))
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
