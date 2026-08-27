"""Add deterministic stock-search keys and readiness lookup index.

Revision ID: 20260828_0028
Revises: 20260826_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from zhaoniu_api.stock_search import stock_name_search_terms

revision: str = "20260828_0028"
down_revision: str | None = "20260826_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("search_name", sa.String(length=120), nullable=False, server_default=""),
    )
    op.add_column(
        "stocks",
        sa.Column("name_pinyin", sa.String(length=240), nullable=False, server_default=""),
    )
    op.add_column(
        "stocks",
        sa.Column("name_pinyin_initials", sa.String(length=120), nullable=False, server_default=""),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT symbol, name FROM stocks ORDER BY symbol")).all()
    updates = []
    for symbol, name in rows:
        search_name, pinyin, initials = stock_name_search_terms(str(name))
        updates.append(
            {
                "symbol": symbol,
                "search_name": search_name,
                "pinyin": pinyin,
                "initials": initials,
            }
        )
    if updates:
        connection.execute(
            sa.text(
                "UPDATE stocks SET search_name=:search_name, name_pinyin=:pinyin, "
                "name_pinyin_initials=:initials WHERE symbol=:symbol"
            ),
            updates,
        )
    op.create_index(
        "ix_stocks_search_name_prefix",
        "stocks",
        ["search_name"],
        postgresql_ops={"search_name": "varchar_pattern_ops"},
    )
    op.create_index(
        "ix_stocks_name_pinyin_prefix",
        "stocks",
        ["name_pinyin"],
        postgresql_ops={"name_pinyin": "varchar_pattern_ops"},
    )
    op.create_index(
        "ix_stocks_name_pinyin_initials_prefix",
        "stocks",
        ["name_pinyin_initials"],
        postgresql_ops={"name_pinyin_initials": "varchar_pattern_ops"},
    )
    op.add_column(
        "automation_run_steps",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_automation_step_symbol_status",
        "automation_run_steps",
        ["symbol", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_step_symbol_status", table_name="automation_run_steps")
    op.drop_column("automation_run_steps", "created_at")
    op.drop_index("ix_stocks_name_pinyin_initials_prefix", table_name="stocks")
    op.drop_index("ix_stocks_name_pinyin_prefix", table_name="stocks")
    op.drop_index("ix_stocks_search_name_prefix", table_name="stocks")
    op.drop_column("stocks", "name_pinyin_initials")
    op.drop_column("stocks", "name_pinyin")
    op.drop_column("stocks", "search_name")
