"""Add immutable controlled-Beta reliability observations.

Revision ID: 20260914_0030
Revises: 20260914_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260914_0030"
down_revision: str | None = "20260914_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beta_reliability_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rule_set_version", sa.String(length=64), nullable=False),
        sa.Column("release_commit", sa.String(length=64), nullable=False),
        sa.Column("api_image_digest", sa.String(length=71), nullable=False),
        sa.Column("web_image_digest", sa.String(length=71), nullable=False),
        sa.Column("migration_head", sa.String(length=32), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slo_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calendar_health", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blocking_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "environment IN ('staging', 'production')",
            name="ck_beta_reliability_observation_environment",
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_beta_reliability_observation_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "environment",
            "release_commit",
            "configuration_fingerprint",
            "window_started_at",
            "window_ended_at",
            name="uq_beta_reliability_observation_identity",
        ),
    )
    op.create_index(
        "ix_beta_reliability_observation_latest",
        "beta_reliability_observations",
        ["environment", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_beta_reliability_observation_latest",
        table_name="beta_reliability_observations",
    )
    op.drop_table("beta_reliability_observations")
