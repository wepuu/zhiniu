"""add corporate disclosure and event radar

Revision ID: 20260819_0011
Revises: 20260819_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_0011"
down_revision: str | None = "20260819_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "disclosure_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_owner", sa.String(40), nullable=False),
        sa.Column("source_document_id", sa.String(160), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_published_precision", sa.String(16), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "source_owner", "source_document_id", name="uq_disclosure_source_identity"
        ),
    )
    op.create_index(
        "ix_disclosure_symbol_published", "disclosure_documents", ["symbol", "source_published_at"]
    )
    op.create_table(
        "disclosure_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disclosure_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_family", sa.String(40)),
        sa.Column("event_type", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("classifier_version", sa.String(40), nullable=False),
        sa.Column("matched_rule", sa.String(120)),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id", "classifier_version", name="uq_disclosure_classification"
        ),
    )
    op.create_table(
        "corporate_event_source_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_owner", sa.String(40), nullable=False),
        sa.Column("source_fact_id", sa.String(160), nullable=False),
        sa.Column("event_family", sa.String(40), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True)),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "matched_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disclosure_documents.id", ondelete="SET NULL"),
        ),
        sa.Column("match_status", sa.String(24), nullable=False),
        sa.UniqueConstraint(
            "source_owner", "source_fact_id", name="uq_corporate_event_source_fact"
        ),
    )
    op.create_index(
        "ix_corporate_event_fact_symbol_family",
        "corporate_event_source_facts",
        ["symbol", "event_family"],
    )
    op.create_table(
        "corporate_event_build_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("run_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_health", sa.String(24), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("written_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("idempotency_key", name="uq_corporate_event_build_run"),
    )
    op.create_index(
        "ix_corporate_event_build_run_symbol",
        "corporate_event_build_runs",
        ["symbol", "started_at"],
    )
    op.create_index(
        "ix_corporate_event_build_runs_status", "corporate_event_build_runs", ["status"]
    )
    op.create_table(
        "corporate_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_family", sa.String(40), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("event_thread_key", sa.String(64), nullable=False),
        sa.Column("event_version_fingerprint", sa.String(64), nullable=False),
        sa.Column("identity_basis", sa.String(120), nullable=False),
        sa.Column(
            "previous_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("corporate_events.id", ondelete="RESTRICT"),
        ),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_published_precision", sa.String(16), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_effective_from", sa.Date()),
        sa.Column("event_effective_to", sa.Date()),
        sa.Column("event_time_precision", sa.String(16)),
        sa.Column("extraction_status", sa.String(24), nullable=False),
        sa.Column("typed_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_lineage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("event_version_fingerprint", name="uq_corporate_event_version"),
    )
    op.create_index("ix_corporate_event_symbol_known", "corporate_events", ["symbol", "known_at"])
    op.create_index(
        "ix_corporate_event_thread", "corporate_events", ["event_thread_key", "known_at"]
    )
    op.create_table(
        "corporate_event_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("corporate_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disclosure_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("corporate_event_source_facts.id", ondelete="RESTRICT"),
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.UniqueConstraint("event_id", "document_id", name="uq_corporate_event_input_document"),
    )
    op.create_table(
        "event_radar_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("source_health", sa.String(24), nullable=False),
        sa.Column("coverage_status", sa.String(24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_event_radar_snapshot"),
    )
    op.create_index(
        "ix_event_radar_snapshot_symbol_cutoff",
        "event_radar_snapshots",
        ["symbol", "knowledge_cutoff"],
    )
    op.create_table(
        "event_radar_snapshot_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event_radar_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("corporate_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("section", sa.String(24), nullable=False),
        sa.Column("attention_level", sa.String(24), nullable=False),
        sa.Column("attention_rule_id", sa.String(120), nullable=False),
        sa.Column("attention_rule_version", sa.String(40), nullable=False),
        sa.Column("attention_reason", sa.String(240), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("snapshot_id", "event_id", name="uq_event_radar_snapshot_item"),
    )


def downgrade() -> None:
    op.drop_table("event_radar_snapshot_items")
    op.drop_index("ix_event_radar_snapshot_symbol_cutoff", table_name="event_radar_snapshots")
    op.drop_table("event_radar_snapshots")
    op.drop_table("corporate_event_inputs")
    op.drop_index("ix_corporate_event_thread", table_name="corporate_events")
    op.drop_index("ix_corporate_event_symbol_known", table_name="corporate_events")
    op.drop_table("corporate_events")
    op.drop_index("ix_corporate_event_build_run_symbol", table_name="corporate_event_build_runs")
    op.drop_index("ix_corporate_event_build_runs_status", table_name="corporate_event_build_runs")
    op.drop_table("corporate_event_build_runs")
    op.drop_index(
        "ix_corporate_event_fact_symbol_family", table_name="corporate_event_source_facts"
    )
    op.drop_table("corporate_event_source_facts")
    op.drop_table("disclosure_classifications")
    op.drop_index("ix_disclosure_symbol_published", table_name="disclosure_documents")
    op.drop_table("disclosure_documents")
