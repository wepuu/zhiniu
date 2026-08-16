"""Create Phase 0 foundation tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "stocks",
        sa.Column("symbol", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("exchange", sa.String(16), nullable=False),
        sa.Column("industry_code", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "plans",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("entitlements", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_watchlists_user_created", "watchlists", ["user_id", "created_at"])
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),
    )
    op.create_table(
        "research_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(16), sa.ForeignKey("stocks.symbol"), nullable=False),
        sa.Column("data_version", sa.String(80), nullable=False),
        sa.Column("research_template_version", sa.String(40), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "symbol",
            "data_version",
            "research_template_version",
            "model_version",
            name="uq_research_snapshot_identity",
        ),
    )
    op.create_index("ix_research_snapshots_symbol", "research_snapshots", ["symbol"])
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_microunits", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_code", sa.String(40), sa.ForeignKey("plans.code"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in (
        "subscriptions",
        "llm_calls",
        "research_snapshots",
        "watchlist_items",
        "watchlists",
        "plans",
        "stocks",
        "users",
    ):
        op.drop_table(table)
