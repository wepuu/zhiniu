"""Add invite-only registration and advanced feature activation.

Revision ID: 20260821_0015
Revises: 20260820_0014
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0015"
down_revision: str | None = "20260820_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000001")
BASIC_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000002")
ADVANCED_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000003")


def upgrade() -> None:
    plan_table = sa.table(
        "plans",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("entitlements", postgresql.JSONB()),
    )
    op.bulk_insert(
        plan_table,
        [
            {"code": "legacy_beta", "name": "Legacy Beta", "entitlements": {}},
            {"code": "basic", "name": "Basic", "entitlements": {}},
            {"code": "advanced", "name": "Advanced", "entitlements": {}},
        ],
    )
    op.create_table(
        "plan_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_code", sa.String(40), sa.ForeignKey("plans.code"), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("limits", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
    )
    version_table = sa.table(
        "plan_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("plan_code", sa.String()),
        sa.column("version", sa.String()),
        sa.column("features", postgresql.JSONB()),
        sa.column("limits", postgresql.JSONB()),
    )
    common_features = {
        "research_feed": True,
        "peer_research": True,
        "event_radar": True,
        "screening": True,
        "ai_research": True,
    }
    common_limits = {"watchlist_groups": 5, "watchlist_memberships_total": 30}
    op.bulk_insert(
        version_table,
        [
            {
                "id": LEGACY_PLAN_VERSION_ID,
                "plan_code": "legacy_beta",
                "version": "legacy-beta-v1",
                "features": {**common_features, "natural_language_screening": True},
                "limits": {
                    **common_limits,
                    "saved_screens": 10,
                    "screen_parses_daily": 30,
                    "concurrent_screen_parses": 1,
                },
            },
            {
                "id": BASIC_PLAN_VERSION_ID,
                "plan_code": "basic",
                "version": "basic-v1",
                "features": {**common_features, "natural_language_screening": False},
                "limits": {
                    **common_limits,
                    "saved_screens": 3,
                    "screen_parses_daily": 0,
                    "concurrent_screen_parses": 0,
                },
            },
            {
                "id": ADVANCED_PLAN_VERSION_ID,
                "plan_code": "advanced",
                "version": "advanced-v1",
                "features": {**common_features, "natural_language_screening": True},
                "limits": {
                    **common_limits,
                    "saved_screens": 10,
                    "screen_parses_daily": 30,
                    "concurrent_screen_parses": 1,
                },
            },
        ],
    )

    op.add_column("users", sa.Column("base_plan_version_id", postgresql.UUID(as_uuid=True)))
    op.execute(
        sa.text("UPDATE users SET base_plan_version_id = :version_id").bindparams(
            version_id=LEGACY_PLAN_VERSION_ID
        )
    )
    op.alter_column("users", "base_plan_version_id", nullable=False)
    op.create_foreign_key(
        "fk_users_base_plan_version",
        "users",
        "plan_versions",
        ["base_plan_version_id"],
        ["id"],
    )

    op.add_column(
        "subscriptions",
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "subscriptions", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False)
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "activation_source", sa.String(32), server_default="activation_code", nullable=False
        ),
    )
    op.add_column("subscriptions", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_subscriptions_plan_version",
        "subscriptions",
        "plan_versions",
        ["plan_version_id"],
        ["id"],
    )
    op.create_unique_constraint("uq_subscriptions_user", "subscriptions", ["user_id"])
    op.create_check_constraint(
        "ck_subscriptions_period",
        "subscriptions",
        "current_period_end > current_period_start",
    )

    op.create_table(
        "registration_invite_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_operator", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("quantity > 0", name="ck_registration_invite_batch_quantity"),
    )
    op.create_table(
        "registration_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registration_invite_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hmac", sa.String(64), nullable=False, unique=True),
        sa.Column("code_prefix", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "consumed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_registration_invites_prefix", "registration_invites", ["code_prefix"])

    op.create_table(
        "access_activation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "plan_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plan_versions.id"),
            nullable=False,
        ),
        sa.Column("term_kind", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_operator", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("term_kind IN ('month', 'year')", name="ck_access_batch_term"),
        sa.CheckConstraint("quantity > 0", name="ck_access_batch_quantity"),
    )
    op.create_table(
        "access_activation_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("access_activation_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hmac", sa.String(64), nullable=False, unique=True),
        sa.Column("code_prefix", sa.String(24), nullable=False),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "redeemed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_access_activation_codes_prefix", "access_activation_codes", ["code_prefix"])
    op.create_index(
        "ix_access_activation_codes_user", "access_activation_codes", ["assigned_user_id"]
    )
    op.create_table(
        "access_activation_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activation_code_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("access_activation_codes.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "plan_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plan_versions.id"),
            nullable=False,
        ),
        sa.Column("term_kind", sa.String(16), nullable=False),
        sa.Column("previous_period_end", sa.DateTime(timezone=True)),
        sa.Column("new_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("term_kind IN ('month', 'year')", name="ck_access_redemption_term"),
        sa.CheckConstraint("new_period_end > new_period_start", name="ck_access_redemption_period"),
    )
    op.create_index(
        "ix_access_activation_redemptions_user",
        "access_activation_redemptions",
        ["user_id", "redeemed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_access_activation_redemptions_user", table_name="access_activation_redemptions"
    )
    op.drop_table("access_activation_redemptions")
    op.drop_index("ix_access_activation_codes_user", table_name="access_activation_codes")
    op.drop_index("ix_access_activation_codes_prefix", table_name="access_activation_codes")
    op.drop_table("access_activation_codes")
    op.drop_table("access_activation_batches")
    op.drop_index("ix_registration_invites_prefix", table_name="registration_invites")
    op.drop_table("registration_invites")
    op.drop_table("registration_invite_batches")
    op.drop_constraint("ck_subscriptions_period", "subscriptions", type_="check")
    op.drop_constraint("uq_subscriptions_user", "subscriptions", type_="unique")
    op.drop_constraint("fk_subscriptions_plan_version", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "revoked_at")
    op.drop_column("subscriptions", "activation_source")
    op.drop_column("subscriptions", "current_period_end")
    op.drop_column("subscriptions", "current_period_start")
    op.drop_column("subscriptions", "plan_version_id")
    op.drop_constraint("fk_users_base_plan_version", "users", type_="foreignkey")
    op.drop_column("users", "base_plan_version_id")
    op.drop_table("plan_versions")
    op.execute(sa.text("DELETE FROM plans WHERE code IN ('legacy_beta', 'basic', 'advanced')"))
