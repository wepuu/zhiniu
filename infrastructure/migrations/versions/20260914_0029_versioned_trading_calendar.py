"""Add the versioned A-share trading-session contract.

Revision ID: 20260914_0029
Revises: 20260828_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260914_0029"
down_revision: str | None = "20260828_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trading_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("session_open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calendar_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "trade_date",
            "calendar_version",
            name="uq_trading_session_identity",
        ),
        sa.CheckConstraint(
            "exchange IN ('SSE', 'SZSE')",
            name="ck_trading_sessions_exchange",
        ),
    )
    op.create_index(
        "ix_trading_sessions_exchange_date",
        "trading_sessions",
        ["exchange", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_trading_sessions_exchange_date", table_name="trading_sessions")
    op.drop_table("trading_sessions")
