"""Add managed provider configuration and encrypted credentials.

Revision ID: 20260822_0022
Revises: 20260822_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0022"
down_revision: str | None = "20260822_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("environment", sa.String(24), nullable=False),
        sa.Column("active_revision", sa.Integer()),
        sa.Column("draft_revision", sa.Integer()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("provider", "environment", name="uq_provider_configuration_scope"),
    )
    op.create_table(
        "provider_configuration_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "configuration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_configurations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("credential_generation", sa.Integer()),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "published_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "configuration_id", "revision", name="uq_provider_configuration_revision"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_provider_configuration_revision_status",
        ),
    )
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "configuration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_configurations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(32), nullable=False),
        sa.Column("key_id", sa.String(48), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("configuration_id", "slot", name="uq_provider_credential_slot"),
        sa.CheckConstraint("slot IN ('active', 'candidate')", name="ck_provider_credential_slot"),
    )
    op.add_column(
        "provider_diagnostic_runs",
        sa.Column(
            "configuration_revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_configuration_revisions.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("provider_diagnostic_runs", sa.Column("credential_generation", sa.Integer()))
    op.add_column(
        "provider_diagnostic_runs",
        sa.Column("target", sa.String(16), nullable=False, server_default="active"),
    )
    op.create_check_constraint(
        "ck_provider_diagnostic_target",
        "provider_diagnostic_runs",
        "target IN ('active', 'draft')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_provider_diagnostic_target", "provider_diagnostic_runs", type_="check")
    op.drop_column("provider_diagnostic_runs", "target")
    op.drop_column("provider_diagnostic_runs", "credential_generation")
    op.drop_column("provider_diagnostic_runs", "configuration_revision_id")
    op.drop_table("provider_credentials")
    op.drop_table("provider_configuration_revisions")
    op.drop_table("provider_configurations")
