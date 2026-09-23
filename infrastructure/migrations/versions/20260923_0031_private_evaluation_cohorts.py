"""Separate private evaluation cohorts from controlled Beta cohorts.

Revision ID: 20260923_0031
Revises: 20260914_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0031"
down_revision: str | None = "20260914_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "beta_invite_cohorts",
        sa.Column(
            "program_kind",
            sa.String(length=32),
            server_default="controlled_beta",
            nullable=False,
        ),
    )
    op.add_column(
        "beta_invite_cohorts",
        sa.Column(
            "usage_scope",
            sa.String(length=32),
            server_default="production",
            nullable=False,
        ),
    )
    op.add_column(
        "beta_invite_cohorts",
        sa.Column(
            "notice_version",
            sa.String(length=40),
            server_default="controlled-beta-v1",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_beta_cohort_program_kind",
        "beta_invite_cohorts",
        "program_kind IN ('private_evaluation', 'controlled_beta')",
    )
    op.create_check_constraint(
        "ck_beta_cohort_usage_scope",
        "beta_invite_cohorts",
        "usage_scope IN ('development_evaluation', 'production')",
    )
    op.create_check_constraint(
        "ck_beta_cohort_program_scope",
        "beta_invite_cohorts",
        "(program_kind = 'private_evaluation' AND usage_scope = 'development_evaluation') "
        "OR (program_kind = 'controlled_beta' AND usage_scope = 'production')",
    )
    op.alter_column("beta_invite_cohorts", "program_kind", server_default=None)
    op.alter_column("beta_invite_cohorts", "usage_scope", server_default=None)
    op.alter_column("beta_invite_cohorts", "notice_version", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_beta_cohort_program_scope", "beta_invite_cohorts", type_="check")
    op.drop_constraint("ck_beta_cohort_usage_scope", "beta_invite_cohorts", type_="check")
    op.drop_constraint("ck_beta_cohort_program_kind", "beta_invite_cohorts", type_="check")
    op.drop_column("beta_invite_cohorts", "notice_version")
    op.drop_column("beta_invite_cohorts", "usage_scope")
    op.drop_column("beta_invite_cohorts", "program_kind")
