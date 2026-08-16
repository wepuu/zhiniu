"""Align Phase 0 indexes and timestamp nullability with ORM metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0003"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, column in (
        ("users", "created_at"),
        ("users", "updated_at"),
        ("stocks", "created_at"),
        ("stocks", "updated_at"),
        ("watchlists", "created_at"),
        ("watchlists", "updated_at"),
        ("watchlist_items", "created_at"),
        ("research_snapshots", "generated_at"),
        ("llm_calls", "created_at"),
        ("subscriptions", "created_at"),
        ("subscriptions", "updated_at"),
        ("stock_daily_bars", "created_at"),
        ("stock_daily_bars", "updated_at"),
    ):
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
    op.create_index("ix_stocks_exchange", "stocks", ["exchange"])
    op.create_index("ix_llm_calls_task_type", "llm_calls", ["task_type"])
    op.create_index("ix_llm_calls_status", "llm_calls", ["status"])
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_llm_calls_status", table_name="llm_calls")
    op.drop_index("ix_llm_calls_task_type", table_name="llm_calls")
    op.drop_index("ix_stocks_exchange", table_name="stocks")
    for table, column in (
        ("stock_daily_bars", "updated_at"),
        ("stock_daily_bars", "created_at"),
        ("subscriptions", "updated_at"),
        ("subscriptions", "created_at"),
        ("llm_calls", "created_at"),
        ("research_snapshots", "generated_at"),
        ("watchlist_items", "created_at"),
        ("watchlists", "updated_at"),
        ("watchlists", "created_at"),
        ("stocks", "updated_at"),
        ("stocks", "created_at"),
        ("users", "updated_at"),
        ("users", "created_at"),
    ):
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
