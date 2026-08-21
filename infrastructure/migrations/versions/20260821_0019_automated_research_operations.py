"""Add automated research operations and scheduling.

Revision ID: 20260821_0019
Revises: 20260821_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0019"
down_revision: str | None = "20260821_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_key", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("policy_key", name="uq_automation_policy_key"),
    )
    op.create_table(
        "automation_policy_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("policy_id", "revision", name="uq_automation_policy_revision"),
        sa.UniqueConstraint("policy_id", "configuration_hash", name="uq_automation_policy_hash"),
    )
    op.create_foreign_key(
        "fk_automation_policy_current_revision",
        "automation_policies",
        "automation_policy_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "automation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_policies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "policy_revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_policy_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "universe_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_research_universe_snapshots.id"),
        ),
        sa.Column("trigger_kind", sa.String(24), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("universe_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("universe_hash", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("succeeded_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warning_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("signal_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alert_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ai_output_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(120)),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_automation_run_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'succeeded_with_warnings', "
            "'partial', 'failed', 'blocked', 'skipped')",
            name="ck_automation_run_status",
        ),
    )
    op.create_index("ix_automation_run_status_created", "automation_runs", ["status", "created_at"])
    op.create_table(
        "automation_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(24), nullable=False),
        sa.Column("scope_key", sa.String(180), nullable=False),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
        ),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("dependency_order", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("before_fingerprint", sa.String(64)),
        sa.Column("after_fingerprint", sa.String(64)),
        sa.Column("changed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("provider_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.String(120)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "run_id", "scope_type", "scope_key", "step_key", name="uq_automation_run_step"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked')",
            name="ck_automation_step_status",
        ),
    )
    op.create_index(
        "ix_automation_step_claim",
        "automation_run_steps",
        ["run_id", "status", "dependency_order"],
    )
    op.create_table(
        "automation_step_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_run_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error_code", sa.String(120)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("step_id", "attempt_number", name="uq_automation_step_attempt"),
    )
    op.create_index(
        "ix_automation_step_attempt_started",
        "automation_step_attempts",
        ["step_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_step_attempt_started", table_name="automation_step_attempts")
    op.drop_table("automation_step_attempts")
    op.drop_index("ix_automation_step_claim", table_name="automation_run_steps")
    op.drop_table("automation_run_steps")
    op.drop_index("ix_automation_run_status_created", table_name="automation_runs")
    op.drop_table("automation_runs")
    op.drop_constraint(
        "fk_automation_policy_current_revision", "automation_policies", type_="foreignkey"
    )
    op.drop_table("automation_policy_revisions")
    op.drop_table("automation_policies")
