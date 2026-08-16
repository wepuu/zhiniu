"""add deterministic change, evidence, and research snapshot foundation

Revision ID: 20260816_0006
Revises: 20260816_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0006"
down_revision: str | None = "20260816_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fundamental_metric_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("value", sa.Numeric(30, 8)),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("fiscal_period", sa.String(12), nullable=False),
        sa.Column("basis", sa.String(24), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_version", sa.String(40), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "input_report_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "input_valuation_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "detail",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("input_fingerprint", name="uq_fundamental_metric_point_fingerprint"),
    )
    op.create_index(
        "ix_fundamental_metric_point_series",
        "fundamental_metric_points",
        ["symbol", "code", "period_end"],
    )

    op.drop_constraint("uq_research_snapshot_identity", "research_snapshots", type_="unique")
    op.alter_column("research_snapshots", "model_version", new_column_name="producer_version")
    op.add_column(
        "research_snapshots",
        sa.Column(
            "metric_version",
            sa.String(40),
            nullable=False,
            server_default="fundamentals-v1",
        ),
    )
    op.add_column(
        "research_snapshots",
        sa.Column("rule_set_version", sa.String(80), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "research_snapshots",
        sa.Column(
            "snapshot_schema_version",
            sa.String(40),
            nullable=False,
            server_default="research-snapshot-v1",
        ),
    )
    op.add_column(
        "research_snapshots",
        sa.Column("producer_kind", sa.String(24), nullable=False, server_default="deterministic"),
    )
    op.add_column(
        "research_snapshots",
        sa.Column(
            "knowledge_cutoff",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "research_snapshots",
        sa.Column(
            "input_manifest",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_unique_constraint(
        "uq_research_snapshot_identity",
        "research_snapshots",
        [
            "symbol",
            "data_version",
            "research_template_version",
            "metric_version",
            "rule_set_version",
            "producer_version",
        ],
    )
    op.create_index(
        "ix_research_snapshot_symbol_cutoff",
        "research_snapshots",
        ["symbol", "knowledge_cutoff"],
    )

    op.create_table(
        "research_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("observation_family", sa.String(120), nullable=False),
        sa.Column("observation_type", sa.String(48), nullable=False),
        sa.Column("attention_level", sa.String(24), nullable=False),
        sa.Column("movement", sa.String(24), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("current_period", sa.Date(), nullable=False),
        sa.Column("comparison_periods", postgresql.JSONB(), nullable=False),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("rule_version", sa.String(24), nullable=False),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("detail_payload", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id", "content_fingerprint", name="uq_research_observation_content"
        ),
    )
    op.create_index(
        "ix_research_observation_symbol_snapshot",
        "research_observations",
        ["symbol", "snapshot_id"],
    )
    op.create_index(
        "ix_research_observations_observation_key",
        "research_observations",
        ["observation_key"],
    )

    op.create_table(
        "research_observation_inputs",
        sa.Column(
            "observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_observations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(48), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column(
            "metric_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fundamental_metric_points.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "report_revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_report_revisions.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "valuation_observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("valuation_observations.id", ondelete="RESTRICT"),
        ),
        sa.CheckConstraint(
            "(CASE WHEN metric_point_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN report_revision_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN valuation_observation_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_research_observation_input_one_reference",
        ),
    )

    op.create_table(
        "research_build_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("data_version", sa.String(80), nullable=False),
        sa.Column("metric_version", sa.String(40), nullable=False),
        sa.Column("rule_set_version", sa.String(80), nullable=False),
        sa.Column("research_template_version", sa.String(40), nullable=False),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_research_build_runs_symbol", "research_build_runs", ["symbol"])
    op.create_index("ix_research_build_runs_status", "research_build_runs", ["status"])


def downgrade() -> None:
    op.drop_table("research_build_runs")
    op.drop_table("research_observation_inputs")
    op.drop_table("research_observations")
    op.drop_index("ix_research_snapshot_symbol_cutoff", table_name="research_snapshots")
    op.drop_constraint("uq_research_snapshot_identity", "research_snapshots", type_="unique")
    op.drop_column("research_snapshots", "input_manifest")
    op.drop_column("research_snapshots", "knowledge_cutoff")
    op.drop_column("research_snapshots", "producer_kind")
    op.drop_column("research_snapshots", "snapshot_schema_version")
    op.drop_column("research_snapshots", "rule_set_version")
    op.drop_column("research_snapshots", "metric_version")
    op.alter_column("research_snapshots", "producer_version", new_column_name="model_version")
    op.create_unique_constraint(
        "uq_research_snapshot_identity",
        "research_snapshots",
        ["symbol", "data_version", "research_template_version", "model_version"],
    )
    op.drop_table("fundamental_metric_points")
