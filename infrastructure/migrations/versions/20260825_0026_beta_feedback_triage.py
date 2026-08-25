"""Add Invite Beta feedback triage fields.

Revision ID: 20260825_0026
Revises: 20260825_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0026"
down_revision: str | None = "20260825_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "beta_feedback_items",
        sa.Column("severity", sa.String(length=2), server_default="P2", nullable=False),
    )
    op.add_column(
        "beta_feedback_items",
        sa.Column("assigned_operator_user_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "beta_feedback_items",
        sa.Column("due_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "beta_feedback_items",
        sa.Column("resolution_code", sa.String(length=64)),
    )
    op.add_column("beta_feedback_items", sa.Column("internal_note", sa.Text()))
    op.create_foreign_key(
        "fk_beta_feedback_assignee",
        "beta_feedback_items",
        "users",
        ["assigned_operator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_beta_feedback_severity",
        "beta_feedback_items",
        "severity IN ('P0', 'P1', 'P2', 'P3')",
    )
    op.create_index(
        "ix_beta_feedback_severity_status",
        "beta_feedback_items",
        ["severity", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_beta_feedback_severity_status", table_name="beta_feedback_items")
    op.drop_constraint(
        "ck_beta_feedback_severity", "beta_feedback_items", type_="check"
    )
    op.drop_constraint(
        "fk_beta_feedback_assignee", "beta_feedback_items", type_="foreignkey"
    )
    op.drop_column("beta_feedback_items", "internal_note")
    op.drop_column("beta_feedback_items", "resolution_code")
    op.drop_column("beta_feedback_items", "due_at")
    op.drop_column("beta_feedback_items", "assigned_operator_user_id")
    op.drop_column("beta_feedback_items", "severity")
