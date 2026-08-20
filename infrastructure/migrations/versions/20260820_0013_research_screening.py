"""add deterministic research screening foundation

Revision ID: 20260820_0013
Revises: 20260820_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0013"
down_revision: str | None = "20260820_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "screening_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("universe_fingerprint", sa.String(64), nullable=False),
        sa.Column("metric_version", sa.String(40), nullable=False),
        sa.Column("taxonomy_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("peer_producer_version", sa.String(80), nullable=False),
        sa.Column("event_radar_version", sa.String(40), nullable=False),
        sa.Column("selector_version", sa.String(40), nullable=False),
        sa.Column("coverage_manifest", JSONB, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_screening_snapshot_idempotency"),
    )
    op.create_index(
        "ix_screening_snapshot_cutoff", "screening_snapshots", ["knowledge_cutoff", "created_at"]
    )

    op.create_table(
        "screening_snapshot_members",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("screening_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issuer_type", sa.String(32), nullable=False),
        sa.Column("eligibility_status", sa.String(24), nullable=False),
        sa.Column("exclusion_reason", sa.String(120)),
        sa.UniqueConstraint("snapshot_id", "symbol", name="uq_screening_snapshot_member"),
    )
    op.create_index(
        "ix_screening_snapshot_member_status",
        "screening_snapshot_members",
        ["snapshot_id", "eligibility_status"],
    )

    op.create_table(
        "screening_snapshot_facts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("screening_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("criterion_key", sa.String(160), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "metric_point_id",
            UUID,
            sa.ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "valuation_observation_id",
            UUID,
            sa.ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "peer_position_id",
            UUID,
            sa.ForeignKey("company_peer_metric_positions.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "industry_membership_id",
            UUID,
            sa.ForeignKey("industry_memberships.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "event_radar_snapshot_id",
            UUID,
            sa.ForeignKey("event_radar_snapshots.id", ondelete="RESTRICT"),
        ),
        sa.CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN peer_position_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN industry_membership_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN event_radar_snapshot_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_screening_fact_one_source",
        ),
        sa.UniqueConstraint(
            "snapshot_id", "symbol", "criterion_key", name="uq_screening_snapshot_fact"
        ),
    )
    op.create_index(
        "ix_screening_fact_lookup",
        "screening_snapshot_facts",
        ["snapshot_id", "criterion_key", "symbol"],
    )

    op.create_table(
        "screen_executions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "screening_snapshot_id",
            UUID,
            sa.ForeignKey("screening_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("canonical_query", JSONB, nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("evaluated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unknown_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("excluded_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "user_id",
            "screening_snapshot_id",
            "query_hash",
            "engine_version",
            name="uq_screen_execution_identity",
        ),
    )
    op.create_index(
        "ix_screen_execution_user_created", "screen_executions", ["user_id", "created_at"]
    )

    op.create_table(
        "screen_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "execution_id",
            UUID,
            sa.ForeignKey("screen_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("sort_value", sa.Numeric(30, 8)),
        sa.Column("matched_condition_manifest", JSONB, nullable=False),
        sa.Column("evidence_refs", JSONB, nullable=False),
        sa.UniqueConstraint("execution_id", "symbol", name="uq_screen_result_symbol"),
        sa.UniqueConstraint("execution_id", "ordinal", name="uq_screen_result_ordinal"),
    )
    op.create_index("ix_screen_result_execution", "screen_results", ["execution_id", "ordinal"])
    op.create_index("ix_screen_result_symbol", "screen_results", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_screen_result_symbol", table_name="screen_results")
    op.drop_index("ix_screen_result_execution", table_name="screen_results")
    op.drop_table("screen_results")
    op.drop_index("ix_screen_execution_user_created", table_name="screen_executions")
    op.drop_table("screen_executions")
    op.drop_index("ix_screening_fact_lookup", table_name="screening_snapshot_facts")
    op.drop_table("screening_snapshot_facts")
    op.drop_index("ix_screening_snapshot_member_status", table_name="screening_snapshot_members")
    op.drop_table("screening_snapshot_members")
    op.drop_index("ix_screening_snapshot_cutoff", table_name="screening_snapshots")
    op.drop_table("screening_snapshots")
