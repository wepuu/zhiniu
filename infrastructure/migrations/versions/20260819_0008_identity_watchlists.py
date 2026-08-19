"""add SaaS identity sessions and persistent watchlist constraints

Revision ID: 20260819_0008
Revises: 20260817_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_0008"
down_revision: str | None = "20260817_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(240)),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_created", "user_sessions", ["user_id", "created_at"])

    op.add_column(
        "watchlists",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint("uq_watchlists_user_name", "watchlists", ["user_id", "name"])
    op.create_index(
        "uq_watchlists_user_default",
        "watchlists",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_index(
        "ix_watchlist_items_watchlist_created",
        "watchlist_items",
        ["watchlist_id", "created_at"],
    )
    op.drop_column("watchlist_items", "user_id")


def downgrade() -> None:
    op.add_column(
        "watchlist_items",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE watchlist_items
        SET user_id = watchlists.user_id
        FROM watchlists
        WHERE watchlist_items.watchlist_id = watchlists.id
        """
    )
    op.alter_column("watchlist_items", "user_id", nullable=False)
    op.create_foreign_key(
        "watchlist_items_user_id_fkey",
        "watchlist_items",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_watchlist_items_watchlist_created", table_name="watchlist_items")
    op.drop_index("uq_watchlists_user_default", table_name="watchlists")
    op.drop_constraint("uq_watchlists_user_name", "watchlists", type_="unique")
    op.drop_column("watchlists", "is_default")
    op.drop_index("ix_user_sessions_user_created", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_column("users", "last_login_at")
