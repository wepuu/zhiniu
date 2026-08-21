"""Add operator controls and production provider audit.

Revision ID: 20260821_0018
Revises: 20260821_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0018"
down_revision: str | None = "20260821_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("operator_elevated_until", sa.DateTime(timezone=True)))
    op.add_column(
        "transactional_email_deliveries", sa.Column("logical_delivery_key", sa.String(96))
    )
    op.add_column(
        "transactional_email_deliveries", sa.Column("submitted_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "transactional_email_deliveries", sa.Column("delivered_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "transactional_email_deliveries", sa.Column("last_event_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        "ix_transactional_email_logical_key",
        "transactional_email_deliveries",
        ["logical_delivery_key"],
        unique=True,
        postgresql_where=sa.text("logical_delivery_key IS NOT NULL"),
    )
    op.add_column("llm_calls", sa.Column("requested_model", sa.String(160)))
    op.add_column("llm_calls", sa.Column("actual_model", sa.String(160)))
    op.add_column("llm_calls", sa.Column("capability_mode", sa.String(32)))

    op.create_table(
        "operator_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "role IN ('viewer', 'support', 'operations', 'security_admin')",
            name="ck_operator_membership_role",
        ),
    )
    op.create_index(
        "uq_operator_membership_active_user",
        "operator_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_operator_membership_role_active",
        "operator_memberships",
        ["role", "created_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "operator_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("action_key", sa.String(96), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(120)),
        sa.Column("request_id", sa.String(80)),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(96)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "result IN ('succeeded', 'denied', 'failed')", name="ck_operator_audit_result"
        ),
    )
    op.create_index(
        "ix_operator_audit_created", "operator_audit_events", ["created_at", "action_key"]
    )
    op.create_index(
        "ix_operator_audit_actor", "operator_audit_events", ["actor_user_id", "created_at"]
    )

    op.create_table(
        "provider_diagnostic_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("reason_code", sa.String(96)),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "status IN ('disabled', 'unknown', 'healthy', 'degraded', 'unavailable')",
            name="ck_provider_diagnostic_status",
        ),
    )
    op.create_index(
        "ix_provider_diagnostic_latest",
        "provider_diagnostic_runs",
        ["provider", "capability", "checked_at"],
    )

    op.create_table(
        "transactional_email_provider_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("event_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(96)),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_transactional_email_provider_event"
        ),
    )
    op.create_index(
        "ix_email_provider_event_message",
        "transactional_email_provider_events",
        ["provider", "provider_message_id", "event_created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_provider_event_message", table_name="transactional_email_provider_events"
    )
    op.drop_table("transactional_email_provider_events")
    op.drop_index("ix_provider_diagnostic_latest", table_name="provider_diagnostic_runs")
    op.drop_table("provider_diagnostic_runs")
    op.drop_index("ix_operator_audit_actor", table_name="operator_audit_events")
    op.drop_index("ix_operator_audit_created", table_name="operator_audit_events")
    op.drop_table("operator_audit_events")
    op.drop_index("ix_operator_membership_role_active", table_name="operator_memberships")
    op.drop_index("uq_operator_membership_active_user", table_name="operator_memberships")
    op.drop_table("operator_memberships")
    op.drop_column("llm_calls", "capability_mode")
    op.drop_column("llm_calls", "actual_model")
    op.drop_column("llm_calls", "requested_model")
    op.drop_index("ix_transactional_email_logical_key", table_name="transactional_email_deliveries")
    op.drop_column("transactional_email_deliveries", "last_event_at")
    op.drop_column("transactional_email_deliveries", "delivered_at")
    op.drop_column("transactional_email_deliveries", "submitted_at")
    op.drop_column("transactional_email_deliveries", "logical_delivery_key")
    op.drop_column("user_sessions", "operator_elevated_until")
