"""add industry taxonomy and peer benchmark research

Revision ID: 20260819_0009
Revises: 20260819_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_0009"
down_revision: str | None = "20260819_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "industry_taxonomies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_reference", sa.String(240), nullable=False),
        sa.Column("commercial_use_status", sa.String(80), nullable=False),
        sa.Column("redistribution_status", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", "version", name="uq_industry_taxonomy_identity"),
    )
    op.create_table(
        "industries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("taxonomy_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "taxonomy_code",
            "taxonomy_version",
            "code",
            name="uq_industry_identity",
        ),
    )
    op.create_index("ix_industries_taxonomy", "industries", ["taxonomy_code", "taxonomy_version"])
    op.create_table(
        "industry_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("industry_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_reference", sa.String(240), nullable=False),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "symbol",
            "taxonomy_code",
            "taxonomy_version",
            "industry_code",
            "known_at",
            name="uq_industry_membership_identity",
        ),
    )
    op.create_index(
        "ix_industry_membership_symbol",
        "industry_memberships",
        ["symbol", "taxonomy_code", "known_at"],
    )
    op.create_index(
        "ix_industry_membership_industry",
        "industry_memberships",
        ["taxonomy_code", "taxonomy_version", "industry_code"],
    )
    op.create_table(
        "peer_benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("taxonomy_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("peer_universe_fingerprint", sa.String(64)),
        sa.Column("comparison_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("idempotency_key", name="uq_peer_benchmark_run_idempotency"),
    )
    op.create_index("ix_peer_benchmark_run_status", "peer_benchmark_runs", ["status"])
    op.create_index(
        "ix_peer_benchmark_run_symbol_started",
        "peer_benchmark_runs",
        ["symbol", "started_at"],
    )
    op.create_table(
        "peer_benchmark_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column(
            "industry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("industries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("taxonomy_code", sa.String(80), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("peer_universe_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("benchmark_schema_version", sa.String(40), nullable=False),
        sa.Column("producer_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_peer_benchmark_snapshot_idempotency"),
    )
    op.create_index(
        "ix_peer_benchmark_snapshot_industry",
        "peer_benchmark_snapshots",
        ["industry_id", "knowledge_cutoff"],
    )
    op.create_table(
        "peer_benchmark_metric_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_benchmark_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column("metric_kind", sa.String(24), nullable=False),
        sa.Column("fiscal_period", sa.String(12)),
        sa.Column("period_end", sa.Date()),
        sa.Column("basis", sa.String(24)),
        sa.Column("unit", sa.String(24)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("median", sa.Numeric(30, 8)),
        sa.Column("p25", sa.Numeric(30, 8)),
        sa.Column("p75", sa.Numeric(30, 8)),
        sa.Column("excluded_invalid_value_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(120)),
        sa.UniqueConstraint("snapshot_id", "metric_code", name="uq_peer_benchmark_metric"),
    )
    op.create_table(
        "peer_benchmark_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "metric_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_benchmark_metric_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "metric_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "valuation_observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
        ),
        sa.CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_peer_benchmark_input_one_reference",
        ),
    )
    op.create_index(
        "ix_peer_benchmark_inputs_result",
        "peer_benchmark_inputs",
        ["metric_result_id"],
    )
    op.create_table(
        "company_peer_metric_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "benchmark_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_benchmark_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "benchmark_metric_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_benchmark_metric_results.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "metric_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "valuation_observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
        ),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column("metric_kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("company_value", sa.Numeric(30, 8)),
        sa.Column("numeric_percentile", sa.Numeric(10, 4)),
        sa.Column("numeric_rank_desc", sa.Integer()),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "symbol",
            "benchmark_metric_result_id",
            name="uq_company_peer_metric_position",
        ),
    )
    op.create_index(
        "ix_company_peer_position_symbol",
        "company_peer_metric_positions",
        ["symbol", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_peer_position_symbol", table_name="company_peer_metric_positions")
    op.drop_table("company_peer_metric_positions")
    op.drop_index("ix_peer_benchmark_inputs_result", table_name="peer_benchmark_inputs")
    op.drop_table("peer_benchmark_inputs")
    op.drop_table("peer_benchmark_metric_results")
    op.drop_index("ix_peer_benchmark_snapshot_industry", table_name="peer_benchmark_snapshots")
    op.drop_table("peer_benchmark_snapshots")
    op.drop_index("ix_peer_benchmark_run_symbol_started", table_name="peer_benchmark_runs")
    op.drop_index("ix_peer_benchmark_run_status", table_name="peer_benchmark_runs")
    op.drop_table("peer_benchmark_runs")
    op.drop_index("ix_industry_membership_industry", table_name="industry_memberships")
    op.drop_index("ix_industry_membership_symbol", table_name="industry_memberships")
    op.drop_table("industry_memberships")
    op.drop_index("ix_industries_taxonomy", table_name="industries")
    op.drop_table("industries")
    op.drop_table("industry_taxonomies")
