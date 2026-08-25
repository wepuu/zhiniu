"""Add Invite Beta operational cohorts and onboarding state.

Revision ID: 20260825_0025
Revises: 20260825_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0025"
down_revision: str | None = "20260825_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beta_invite_cohorts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("target_size", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "acceptance_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_acceptance_runs.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "invite_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registration_invite_batches.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reason_code", sa.String(120)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("target_size > 0 AND target_size <= 100", name="ck_beta_cohort_size"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'dispatching', 'active', "
            "'paused', 'closed', 'cancelled')",
            name="ck_beta_cohort_status",
        ),
    )
    op.create_index(
        "ix_beta_cohort_status_created",
        "beta_invite_cohorts",
        ["status", "created_at"],
    )

    op.create_table(
        "beta_invite_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cohort_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_invite_cohorts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("email_hmac", sa.String(64), nullable=False),
        sa.Column(
            "invite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registration_invites.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "delivery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactional_email_deliveries.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("registered_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("cohort_id", "email_hmac", name="uq_beta_cohort_recipient_email"),
        sa.UniqueConstraint("invite_id", name="uq_beta_recipient_invite"),
        sa.UniqueConstraint("delivery_id", name="uq_beta_recipient_delivery"),
        sa.CheckConstraint(
            "status IN ('staged', 'queued', 'registered', 'withdrawn', 'expired', 'failed')",
            name="ck_beta_recipient_status",
        ),
    )
    op.create_index("ix_beta_recipient_email", "beta_invite_recipients", ["email_hmac", "status"])
    op.create_index(
        "ix_beta_recipient_cohort_status",
        "beta_invite_recipients",
        ["cohort_id", "status"],
    )
    op.create_index("ix_beta_recipient_user", "beta_invite_recipients", ["user_id"])

    op.create_table(
        "beta_onboarding_states",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_invite_recipients.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("beta_onboarding_states")
    op.drop_index("ix_beta_recipient_user", table_name="beta_invite_recipients")
    op.drop_index("ix_beta_recipient_cohort_status", table_name="beta_invite_recipients")
    op.drop_index("ix_beta_recipient_email", table_name="beta_invite_recipients")
    op.drop_table("beta_invite_recipients")
    op.drop_index("ix_beta_cohort_status_created", table_name="beta_invite_cohorts")
    op.drop_table("beta_invite_cohorts")
