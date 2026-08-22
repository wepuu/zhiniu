"""Add company timeline query support and safe signal projection metadata.

Revision ID: 20260822_0020
Revises: 20260821_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0020"
down_revision: str | None = "20260821_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_signals",
        sa.Column(
            "projection_mode",
            sa.String(24),
            nullable=False,
            server_default="historical_backfill",
        ),
    )
    op.add_column(
        "research_signals",
        sa.Column("alert_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_index("ix_research_signal_symbol_known", table_name="research_signals")
    op.create_index(
        "ix_research_signal_symbol_known",
        "research_signals",
        ["symbol", sa.text("known_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_corporate_event_symbol_family_known",
        "corporate_events",
        ["symbol", "event_family", sa.text("known_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_disclosure_symbol_known",
        "disclosure_documents",
        ["symbol", sa.text("known_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_disclosure_symbol_known", table_name="disclosure_documents")
    op.drop_index("ix_corporate_event_symbol_family_known", table_name="corporate_events")
    op.drop_index("ix_research_signal_symbol_known", table_name="research_signals")
    op.create_index("ix_research_signal_symbol_known", "research_signals", ["symbol", "known_at"])
    op.drop_column("research_signals", "alert_eligible")
    op.drop_column("research_signals", "projection_mode")
