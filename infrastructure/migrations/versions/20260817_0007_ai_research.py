"""add multi-provider AI research runs and immutable outputs

Revision ID: 20260817_0007
Revises: 20260816_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0007"
down_revision: str | None = "20260816_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("research_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("context_version", sa.String(40), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("output_schema_version", sa.String(40), nullable=False),
        sa.Column("model_route_version", sa.String(40), nullable=False),
        sa.Column("route_hash", sa.String(64), nullable=False),
        sa.Column("current_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_research_run_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_ai_research_run_status",
        ),
    )
    op.create_index("ix_ai_research_runs_status", "ai_research_runs", ["status"])
    op.create_index(
        "ix_ai_research_run_symbol_started", "ai_research_runs", ["symbol", "started_at"]
    )

    op.create_table(
        "ai_research_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_research_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("research_type", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("context_version", sa.String(40), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("output_schema_version", sa.String(40), nullable=False),
        sa.Column("model_route_version", sa.String(40), nullable=False),
        sa.Column("route_hash", sa.String(64), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("coverage_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_ai_research_output_run"),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_research_output_idempotency"),
    )
    op.create_index(
        "ix_ai_research_output_symbol_generated",
        "ai_research_outputs",
        ["symbol", "generated_at"],
    )

    op.add_column(
        "llm_calls",
        sa.Column(
            "ai_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_research_runs.id", ondelete="CASCADE"),
        ),
    )
    op.add_column("llm_calls", sa.Column("attempt_index", sa.Integer()))
    op.add_column("llm_calls", sa.Column("finish_reason", sa.String(80)))
    op.add_column("llm_calls", sa.Column("error_code", sa.String(64)))
    op.alter_column(
        "llm_calls",
        "model",
        existing_type=sa.String(80),
        type_=sa.String(160),
        existing_nullable=False,
    )
    op.create_index("ix_llm_calls_ai_run_id", "llm_calls", ["ai_run_id"])
    op.create_index("ix_llm_calls_error_code", "llm_calls", ["error_code"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_error_code", table_name="llm_calls")
    op.drop_index("ix_llm_calls_ai_run_id", table_name="llm_calls")
    op.alter_column(
        "llm_calls",
        "model",
        existing_type=sa.String(160),
        type_=sa.String(80),
        existing_nullable=False,
    )
    op.drop_column("llm_calls", "error_code")
    op.drop_column("llm_calls", "finish_reason")
    op.drop_column("llm_calls", "attempt_index")
    op.drop_column("llm_calls", "ai_run_id")
    op.drop_table("ai_research_outputs")
    op.drop_table("ai_research_runs")
