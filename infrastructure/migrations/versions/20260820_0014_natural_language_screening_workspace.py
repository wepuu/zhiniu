"""add natural-language screening workspace

Revision ID: 20260820_0014
Revises: 20260820_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0014"
down_revision: str | None = "20260820_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "natural_language_screen_parse_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_length", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("semantic_status", sa.String(32)),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("output_schema_version", sa.String(40), nullable=False),
        sa.Column("catalog_version", sa.String(40), nullable=False),
        sa.Column("catalog_hash", sa.String(64), nullable=False),
        sa.Column("criteria_contract_hash", sa.String(64), nullable=False),
        sa.Column("parser_route_hash", sa.String(64), nullable=False),
        sa.Column("current_attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_document", JSONB),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_summary", sa.String(300)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "input_hash", "parser_route_hash", name="uq_nl_parse_run"),
    )
    op.create_index(
        "ix_nl_parse_user_created", "natural_language_screen_parse_runs", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_nl_parse_user_status", "natural_language_screen_parse_runs", ["user_id", "status"]
    )

    op.create_table(
        "saved_screens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(240)),
        sa.Column("canonical_query", JSONB, nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("dsl_version", sa.String(40), nullable=False),
        sa.Column("catalog_version", sa.String(40), nullable=False),
        sa.Column("catalog_hash", sa.String(64), nullable=False),
        sa.Column("criteria_contract_hash", sa.String(64), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column(
            "source_parse_run_id",
            UUID,
            sa.ForeignKey("natural_language_screen_parse_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("original_text", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_saved_screen_user_name"),
    )
    op.create_index("ix_saved_screen_user_updated", "saved_screens", ["user_id", "updated_at"])

    op.create_table(
        "screen_execution_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "execution_id",
            UUID,
            sa.ForeignKey("screen_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("saved_screen_id", UUID, sa.ForeignKey("saved_screens.id", ondelete="SET NULL")),
        sa.Column(
            "confirmed_parse_run_id",
            UUID,
            sa.ForeignKey("natural_language_screen_parse_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("request_source", sa.String(24), nullable=False),
        sa.Column("reused_execution", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_screen_execution_request_user_created",
        "screen_execution_requests",
        ["user_id", "created_at"],
    )

    op.add_column(
        "llm_calls",
        sa.Column(
            "parse_run_id",
            UUID,
            sa.ForeignKey("natural_language_screen_parse_runs.id", ondelete="CASCADE"),
        ),
    )
    op.add_column(
        "llm_calls",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_index("ix_llm_calls_parse_run_id", "llm_calls", ["parse_run_id"])
    op.create_index("ix_llm_calls_user_id", "llm_calls", ["user_id"])

    op.add_column("screen_results", sa.Column("user_id", UUID, nullable=True))
    op.execute(
        "UPDATE screen_results SET user_id = screen_executions.user_id "
        "FROM screen_executions WHERE screen_results.execution_id = screen_executions.id"
    )
    op.alter_column("screen_results", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_screen_results_user_id",
        "screen_results",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_screen_results_user_id", "screen_results", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_screen_results_user_id", table_name="screen_results")
    op.drop_constraint("fk_screen_results_user_id", "screen_results", type_="foreignkey")
    op.drop_column("screen_results", "user_id")
    op.drop_index("ix_llm_calls_user_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_parse_run_id", table_name="llm_calls")
    op.drop_column("llm_calls", "user_id")
    op.drop_column("llm_calls", "parse_run_id")
    op.drop_index(
        "ix_screen_execution_request_user_created", table_name="screen_execution_requests"
    )
    op.drop_table("screen_execution_requests")
    op.drop_index("ix_saved_screen_user_updated", table_name="saved_screens")
    op.drop_table("saved_screens")
    op.drop_index("ix_nl_parse_user_status", table_name="natural_language_screen_parse_runs")
    op.drop_index("ix_nl_parse_user_created", table_name="natural_language_screen_parse_runs")
    op.drop_table("natural_language_screen_parse_runs")
