"""Add retained Provider and Beta data acceptance evidence.

Revision ID: 20260825_0024
Revises: 20260823_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0024"
down_revision: str | None = "20260823_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_acceptance_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("usage_scope", sa.String(32), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("mandatory_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("succeeded_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unsupported_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("beta_eligible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'blocked')", name="ck_provider_acceptance_run_status"
        ),
    )
    op.create_index(
        "ix_provider_acceptance_latest",
        "provider_acceptance_runs",
        ["environment", "created_at"],
    )
    op.create_table(
        "provider_acceptance_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_acceptance_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
        ),
        sa.Column("scenario", sa.String(64), nullable=False),
        sa.Column("requirement", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(120)),
        sa.Column("observed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_artifact_at", sa.DateTime(timezone=True)),
        sa.Column("detail_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "run_id",
            "provider",
            "dataset",
            "symbol",
            "scenario",
            name="uq_provider_acceptance_item",
        ),
        sa.CheckConstraint(
            "requirement IN ('mandatory', 'conditional', 'optional')",
            name="ck_provider_acceptance_item_requirement",
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'blocked', 'unsupported')",
            name="ck_provider_acceptance_item_status",
        ),
    )
    op.create_index(
        "ix_provider_acceptance_item_run_status",
        "provider_acceptance_items",
        ["run_id", "status", "symbol"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_acceptance_item_run_status", table_name="provider_acceptance_items")
    op.drop_table("provider_acceptance_items")
    op.drop_index("ix_provider_acceptance_latest", table_name="provider_acceptance_runs")
    op.drop_table("provider_acceptance_runs")
