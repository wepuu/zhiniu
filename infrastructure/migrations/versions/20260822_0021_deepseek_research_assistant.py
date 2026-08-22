"""Enable evidence-grounded DeepSeek research explanations.

Revision ID: 20260822_0021
Revises: 20260822_0020
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0021"
down_revision: str | None = "20260822_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_V2 = UUID("10000000-0000-4000-8000-000000000004")
BASIC_V2 = UUID("10000000-0000-4000-8000-000000000005")
ADVANCED_V2 = UUID("10000000-0000-4000-8000-000000000006")


def upgrade() -> None:
    op.add_column("ai_research_runs", sa.Column("question_key", sa.String(64)))
    op.add_column("ai_research_outputs", sa.Column("question_key", sa.String(64)))
    op.create_index(
        "ix_ai_research_output_explanation",
        "ai_research_outputs",
        ["symbol", "question_key", "generated_at"],
    )

    op.create_table(
        "ai_explanation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(64), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_research_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_research_outputs.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("quota_day", sa.Date(), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_ai_explanation_user_client"),
        sa.CheckConstraint(
            "status IN ('pending', 'building', 'ready', 'failed')",
            name="ck_ai_explanation_request_status",
        ),
    )
    op.create_index(
        "ix_ai_explanation_user_created",
        "ai_explanation_requests",
        ["user_id", "created_at"],
    )
    op.create_table(
        "ai_explanation_daily_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quota_day", sa.Date(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "quota_day", name="uq_ai_explanation_usage_day"),
        sa.CheckConstraint("used_count >= 0", name="ck_ai_explanation_usage_nonnegative"),
    )

    version_table = sa.table(
        "plan_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("plan_code", sa.String()),
        sa.column("version", sa.String()),
        sa.column("features", postgresql.JSONB()),
        sa.column("limits", postgresql.JSONB()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT DISTINCT ON (plan_code) plan_code, features, limits "
            "FROM plan_versions ORDER BY plan_code, created_at DESC"
        )
    ).mappings()
    current = {row["plan_code"]: row for row in rows}
    inserts = []
    for plan_code, version_id, enabled, limit in (
        ("legacy_beta", LEGACY_V2, True, 30),
        ("basic", BASIC_V2, False, 0),
        ("advanced", ADVANCED_V2, True, 10),
    ):
        prior = current[plan_code]
        inserts.append(
            {
                "id": version_id,
                "plan_code": plan_code,
                "version": f"{plan_code}-phase17-v1",
                "features": {**prior["features"], "ai_research_explanation": enabled},
                "limits": {**prior["limits"], "ai_explanations_daily": limit},
            }
        )
    op.bulk_insert(version_table, inserts)
    connection.execute(
        sa.text(
            "UPDATE users SET base_plan_version_id = CASE "
            "WHEN base_plan_version_id = "
            "'10000000-0000-4000-8000-000000000001'::uuid THEN CAST(:legacy AS uuid) "
            "ELSE CAST(:basic AS uuid) END WHERE base_plan_version_id IN "
            "('10000000-0000-4000-8000-000000000001'::uuid,"
            "'10000000-0000-4000-8000-000000000002'::uuid)"
        ),
        {"legacy": LEGACY_V2, "basic": BASIC_V2},
    )
    connection.execute(
        sa.text(
            "UPDATE subscriptions SET plan_version_id = CAST(:advanced AS uuid) "
            "WHERE plan_code = 'advanced'"
        ),
        {"advanced": ADVANCED_V2},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users SET base_plan_version_id = CASE "
            "WHEN base_plan_version_id = CAST(:legacy AS uuid) THEN "
            "'10000000-0000-4000-8000-000000000001'::uuid "
            "ELSE '10000000-0000-4000-8000-000000000002'::uuid END "
            "WHERE base_plan_version_id IN (CAST(:legacy AS uuid), CAST(:basic AS uuid))"
        ),
        {"legacy": LEGACY_V2, "basic": BASIC_V2},
    )
    connection.execute(
        sa.text(
            "UPDATE subscriptions SET plan_version_id = "
            "'10000000-0000-4000-8000-000000000003'::uuid "
            "WHERE plan_version_id = CAST(:advanced AS uuid)"
        ),
        {"advanced": ADVANCED_V2},
    )
    connection.execute(
        sa.text("DELETE FROM plan_versions WHERE id IN (:legacy, :basic, :advanced)"),
        {"legacy": LEGACY_V2, "basic": BASIC_V2, "advanced": ADVANCED_V2},
    )
    op.drop_table("ai_explanation_daily_usage")
    op.drop_index("ix_ai_explanation_user_created", table_name="ai_explanation_requests")
    op.drop_table("ai_explanation_requests")
    op.drop_index("ix_ai_research_output_explanation", table_name="ai_research_outputs")
    op.drop_column("ai_research_outputs", "question_key")
    op.drop_column("ai_research_runs", "question_key")
