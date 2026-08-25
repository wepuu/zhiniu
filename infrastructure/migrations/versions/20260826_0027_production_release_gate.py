"""Add immutable production release gate evidence.

Revision ID: 20260826_0027
Revises: 20260825_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0027"
down_revision: str | None = "20260825_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "production_release_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("migration_head", sa.String(length=32), nullable=False),
        sa.Column("api_image_digest", sa.String(length=80), nullable=False),
        sa.Column("web_image_digest", sa.String(length=80), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("sbom_sha256", sa.String(length=64), nullable=False),
        sa.Column("backup_sha256", sa.String(length=64), nullable=False),
        sa.Column("restore_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_gate_status", sa.String(length=16), nullable=False),
        sa.Column("e2e_status", sa.String(length=16), nullable=False),
        sa.Column("security_scan_status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("target_environment = 'production'", name="ck_release_candidate_env"),
        sa.CheckConstraint(
            "status IN ('draft', 'blocked', 'ready_closed', 'deployed_observing', "
            "'ready_invites', 'released', 'rolled_back', 'rejected')",
            name="ck_release_candidate_status",
        ),
        sa.CheckConstraint(
            "quality_gate_status IN ('passed', 'failed') AND "
            "e2e_status IN ('passed', 'failed') AND "
            "security_scan_status IN ('passed', 'failed')",
            name="ck_release_candidate_evidence_status",
        ),
        sa.UniqueConstraint(
            "target_environment",
            "commit_sha",
            "configuration_fingerprint",
            name="uq_release_candidate_identity",
        ),
    )
    op.create_index(
        "ix_release_candidate_status_created",
        "production_release_candidates",
        ["status", "created_at"],
    )

    op.create_table(
        "production_release_gate_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_release_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rule_set_version", sa.String(length=64), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "gate_type IN ('closed_deployment', 'invite_activation')",
            name="ck_release_gate_type",
        ),
        sa.CheckConstraint("status IN ('passed', 'blocked')", name="ck_release_gate_status"),
    )
    op.create_index(
        "ix_release_gate_candidate_started",
        "production_release_gate_runs",
        ["candidate_id", "started_at"],
    )

    op.create_table(
        "production_release_gate_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_release_gate_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_key", sa.String(length=96), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=120)),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'not_applicable')", name="ck_release_item_status"
        ),
        sa.UniqueConstraint("run_id", "check_key", name="uq_release_gate_item_key"),
    )

    op.create_table(
        "production_release_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_release_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("approval_role", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "approval_role IN ('engineering', 'data_compliance', 'product_operations')",
            name="ck_release_approval_role",
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')", name="ck_release_approval_decision"
        ),
        sa.UniqueConstraint("candidate_id", "approval_role", name="uq_release_approval_role"),
        sa.UniqueConstraint("candidate_id", "actor_user_id", name="uq_release_approval_actor"),
    )

    op.create_table(
        "production_deployment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_release_candidates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("deployment_ref", sa.String(length=160), nullable=False),
        sa.Column("reason_code", sa.String(length=120)),
        sa.Column(
            "recorded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('deployed', 'released', 'failed', 'rolled_back')",
            name="ck_deployment_event_type",
        ),
        sa.UniqueConstraint("candidate_id", "event_type", name="uq_deployment_candidate_event"),
    )
    op.create_index(
        "ix_deployment_event_candidate_created",
        "production_deployment_events",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deployment_event_candidate_created", table_name="production_deployment_events"
    )
    op.drop_table("production_deployment_events")
    op.drop_table("production_release_approvals")
    op.drop_table("production_release_gate_items")
    op.drop_index("ix_release_gate_candidate_started", table_name="production_release_gate_runs")
    op.drop_table("production_release_gate_runs")
    op.drop_index("ix_release_candidate_status_created", table_name="production_release_candidates")
    op.drop_table("production_release_candidates")
