"""align peer research timestamp nullability and index names

Revision ID: 20260819_0010
Revises: 20260819_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0010"
down_revision: str | None = "20260819_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name, columns in {
        "company_peer_metric_positions": ("created_at",),
        "industries": ("created_at", "updated_at"),
        "industry_memberships": ("created_at", "updated_at"),
        "industry_taxonomies": ("created_at", "updated_at"),
        "peer_benchmark_runs": ("started_at",),
        "peer_benchmark_snapshots": ("created_at",),
        "user_sessions": ("created_at",),
    }.items():
        for column_name in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )
    op.drop_index("ix_peer_benchmark_run_status", table_name="peer_benchmark_runs")
    op.create_index(
        "ix_peer_benchmark_runs_status",
        "peer_benchmark_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_peer_benchmark_runs_status", table_name="peer_benchmark_runs")
    op.create_index("ix_peer_benchmark_run_status", "peer_benchmark_runs", ["status"])
    for table_name, columns in {
        "user_sessions": ("created_at",),
        "peer_benchmark_snapshots": ("created_at",),
        "peer_benchmark_runs": ("started_at",),
        "industry_taxonomies": ("created_at", "updated_at"),
        "industry_memberships": ("created_at", "updated_at"),
        "industries": ("created_at", "updated_at"),
        "company_peer_metric_positions": ("created_at",),
    }.items():
        for column_name in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                nullable=True,
            )
