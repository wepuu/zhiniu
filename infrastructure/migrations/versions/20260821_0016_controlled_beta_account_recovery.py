"""Add controlled beta account verification and recovery.

Revision ID: 20260821_0016
Revises: 20260821_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0016"
down_revision: str | None = "20260821_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email_snapshot", sa.String(320), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_hash"),
    )
    op.create_index(
        "ix_email_verification_tokens_user_created",
        "email_verification_tokens",
        ["user_id", "created_at"],
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_created",
        "password_reset_tokens",
        ["user_id", "created_at"],
    )

    op.create_table(
        "transactional_email_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("template_key", sa.String(48), nullable=False),
        sa.Column("template_version", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_transactional_email_user_created",
        "transactional_email_deliveries",
        ["user_id", "created_at"],
    )

    op.create_table(
        "user_legal_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(48), nullable=False),
        sa.Column("document_version", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "document_type", "document_version", name="uq_user_legal_acceptance"
        ),
    )
    op.create_index(
        "ix_user_legal_acceptances_user", "user_legal_acceptances", ["user_id", "accepted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_legal_acceptances_user", table_name="user_legal_acceptances")
    op.drop_table("user_legal_acceptances")
    op.drop_index(
        "ix_transactional_email_user_created", table_name="transactional_email_deliveries"
    )
    op.drop_table("transactional_email_deliveries")
    op.drop_index("ix_password_reset_tokens_user_created", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(
        "ix_email_verification_tokens_user_created", table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
