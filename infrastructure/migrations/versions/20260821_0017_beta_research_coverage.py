"""Add beta research coverage and bounded backfill.

Revision ID: 20260821_0017
Revises: 20260821_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0017"
down_revision: str | None = "20260821_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, primary_key: bool = False, nullable: bool = True) -> sa.Column:
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), primary_key=primary_key, nullable=nullable
    )


def upgrade() -> None:
    op.create_table(
        "beta_research_universe_snapshots",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("universe_fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("source_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_beta_universe_cutoff",
        "beta_research_universe_snapshots",
        ["knowledge_cutoff", "created_at"],
    )
    op.create_table(
        "beta_research_universe_members",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_research_universe_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("reason_flags", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("snapshot_id", "symbol", name="uq_beta_universe_member"),
    )
    op.create_index(
        "ix_beta_universe_member_priority",
        "beta_research_universe_members",
        ["snapshot_id", "priority_rank", "symbol"],
    )
    op.create_table(
        "research_coverage_snapshots",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "universe_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_research_universe_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage_schema_version", sa.String(40), nullable=False),
        sa.Column("evaluator_version", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_research_coverage_cutoff",
        "research_coverage_snapshots",
        ["knowledge_cutoff", "evaluated_at"],
    )
    op.create_table(
        "research_coverage_members",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_coverage_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dimension_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("snapshot_id", "symbol", name="uq_research_coverage_member"),
    )
    op.create_index(
        "ix_research_coverage_member_symbol", "research_coverage_members", ["symbol", "snapshot_id"]
    )
    op.create_table(
        "coverage_backfill_runs",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "universe_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beta_research_universe_snapshots.id"),
            nullable=False,
        ),
        sa.Column(
            "coverage_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_coverage_snapshots.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("planner_version", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("target_profile_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("planned_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("succeeded_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_coverage_backfill_run_status", "coverage_backfill_runs", ["status", "created_at"]
    )
    op.create_table(
        "coverage_backfill_items",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_backfill_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action_key", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("dependency_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("before_fingerprint", sa.String(64)),
        sa.Column("after_fingerprint", sa.String(64)),
        sa.Column("changed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("provider_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.String(120)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "symbol", "action_key", name="uq_coverage_backfill_item"),
    )
    op.create_index(
        "ix_coverage_backfill_item_claim",
        "coverage_backfill_items",
        ["run_id", "status", "dependency_order"],
    )
    op.create_table(
        "beta_feedback_items",
        _uuid("id", primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(48), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), server_default="new", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_beta_feedback_status_created", "beta_feedback_items", ["status", "created_at"]
    )
    op.create_index(
        "ix_beta_feedback_user_created", "beta_feedback_items", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_beta_feedback_user_created", table_name="beta_feedback_items")
    op.drop_index("ix_beta_feedback_status_created", table_name="beta_feedback_items")
    op.drop_table("beta_feedback_items")
    op.drop_index("ix_coverage_backfill_item_claim", table_name="coverage_backfill_items")
    op.drop_table("coverage_backfill_items")
    op.drop_index("ix_coverage_backfill_run_status", table_name="coverage_backfill_runs")
    op.drop_table("coverage_backfill_runs")
    op.drop_index("ix_research_coverage_member_symbol", table_name="research_coverage_members")
    op.drop_table("research_coverage_members")
    op.drop_index("ix_research_coverage_cutoff", table_name="research_coverage_snapshots")
    op.drop_table("research_coverage_snapshots")
    op.drop_index("ix_beta_universe_member_priority", table_name="beta_research_universe_members")
    op.drop_table("beta_research_universe_members")
    op.drop_index("ix_beta_universe_cutoff", table_name="beta_research_universe_snapshots")
    op.drop_table("beta_research_universe_snapshots")
