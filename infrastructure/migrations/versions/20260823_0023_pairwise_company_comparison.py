"""Add pairwise company research comparison.

Revision ID: 20260823_0023
Revises: 20260822_0022
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0023"
down_revision: str | None = "20260822_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_V3 = UUID("10000000-0000-4000-8000-000000000007")
BASIC_V3 = UUID("10000000-0000-4000-8000-000000000008")
ADVANCED_V3 = UUID("10000000-0000-4000-8000-000000000009")
LEGACY_V2 = UUID("10000000-0000-4000-8000-000000000004")
BASIC_V2 = UUID("10000000-0000-4000-8000-000000000005")
ADVANCED_V2 = UUID("10000000-0000-4000-8000-000000000006")


def upgrade() -> None:
    op.create_table(
        "comparison_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canonical_symbol_low",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "canonical_symbol_high",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("comparison_schema_version", sa.String(40), nullable=False),
        sa.Column("comparison_rule_version", sa.String(40), nullable=False),
        sa.Column("input_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("structured_document", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("coverage_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("limitation_manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_comparison_snapshot_idempotency"),
    )
    op.create_index(
        "ix_comparison_snapshot_pair_created",
        "comparison_snapshots",
        ["canonical_symbol_low", "canonical_symbol_high", "created_at"],
    )

    op.create_table(
        "comparison_build_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canonical_symbol_low",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "canonical_symbol_high",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_comparison_build_run_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_comparison_build_run_status",
        ),
    )
    op.create_index(
        "ix_comparison_build_status_created",
        "comparison_build_runs",
        ["status", "created_at"],
    )

    op.create_table(
        "comparison_ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("context_version", sa.String(40), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("output_schema_version", sa.String(40), nullable=False),
        sa.Column("model_route_version", sa.String(40), nullable=False),
        sa.Column("route_hash", sa.String(64), nullable=False),
        sa.Column("current_attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_comparison_ai_run_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_comparison_ai_run_status",
        ),
    )
    op.create_index(
        "ix_comparison_ai_run_status_created", "comparison_ai_runs", ["status", "created_at"]
    )

    op.create_table(
        "comparison_ai_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_ai_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("context_version", sa.String(40), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("output_schema_version", sa.String(40), nullable=False),
        sa.Column("model_route_version", sa.String(40), nullable=False),
        sa.Column("route_hash", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_comparison_ai_output_run"),
        sa.UniqueConstraint("idempotency_key", name="uq_comparison_ai_output_idempotency"),
    )

    op.create_table(
        "comparison_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "left_symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "right_symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("requested_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("include_ai", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "build_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_build_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "ai_output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_ai_outputs.id", ondelete="SET NULL"),
        ),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "user_id", "client_request_id", name="uq_comparison_request_user_client"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'building', 'ready', 'partial', 'failed', 'unsupported')",
            name="ck_comparison_request_status",
        ),
    )
    op.create_index(
        "ix_comparison_request_user_created",
        "comparison_requests",
        ["user_id", "created_at"],
    )

    op.create_table(
        "saved_comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(80), nullable=False),
        sa.Column(
            "left_symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "right_symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column(
            "latest_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_requests.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_saved_comparison_user_name"),
    )
    op.create_index(
        "ix_saved_comparison_user_updated", "saved_comparisons", ["user_id", "updated_at"]
    )

    op.add_column(
        "llm_calls",
        sa.Column(
            "comparison_ai_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_ai_runs.id", ondelete="CASCADE"),
        ),
    )
    op.create_index("ix_llm_calls_comparison_ai_run_id", "llm_calls", ["comparison_ai_run_id"])

    _add_phase18_plan_versions()


def _add_phase18_plan_versions() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT DISTINCT ON (plan_code) plan_code, features, limits "
            "FROM plan_versions ORDER BY plan_code, created_at DESC"
        )
    ).mappings()
    current = {row["plan_code"]: row for row in rows}
    version_table = sa.table(
        "plan_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("plan_code", sa.String()),
        sa.column("version", sa.String()),
        sa.column("features", postgresql.JSONB()),
        sa.column("limits", postgresql.JSONB()),
    )
    inserts = []
    for plan_code, version_id, ai_enabled, saved_limit in (
        ("legacy_beta", LEGACY_V3, True, 10),
        ("basic", BASIC_V3, False, 0),
        ("advanced", ADVANCED_V3, True, 10),
    ):
        prior = current[plan_code]
        inserts.append(
            {
                "id": version_id,
                "plan_code": plan_code,
                "version": f"{plan_code}-phase18-v1",
                "features": {
                    **prior["features"],
                    "company_comparison": True,
                    "comparison_explanation": ai_enabled,
                },
                "limits": {**prior["limits"], "saved_comparisons": saved_limit},
            }
        )
    op.bulk_insert(version_table, inserts)
    connection.execute(
        sa.text(
            "UPDATE users SET base_plan_version_id = CASE "
            "WHEN base_plan_version_id = CAST(:legacy_old AS uuid) THEN CAST(:legacy_new AS uuid) "
            "ELSE CAST(:basic_new AS uuid) END "
            "WHERE base_plan_version_id IN (CAST(:legacy_old AS uuid), CAST(:basic_old AS uuid))"
        ),
        {
            "legacy_old": LEGACY_V2,
            "basic_old": BASIC_V2,
            "legacy_new": LEGACY_V3,
            "basic_new": BASIC_V3,
        },
    )
    connection.execute(
        sa.text(
            "UPDATE subscriptions SET plan_version_id = CAST(:advanced_new AS uuid) "
            "WHERE plan_code = 'advanced'"
        ),
        {"advanced_new": ADVANCED_V3},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users SET base_plan_version_id = CASE "
            "WHEN base_plan_version_id = CAST(:legacy_new AS uuid) THEN CAST(:legacy_old AS uuid) "
            "ELSE CAST(:basic_old AS uuid) END "
            "WHERE base_plan_version_id IN (CAST(:legacy_new AS uuid), CAST(:basic_new AS uuid))"
        ),
        {
            "legacy_new": LEGACY_V3,
            "basic_new": BASIC_V3,
            "legacy_old": LEGACY_V2,
            "basic_old": BASIC_V2,
        },
    )
    connection.execute(
        sa.text(
            "UPDATE subscriptions SET plan_version_id = CAST(:advanced_old AS uuid) "
            "WHERE plan_version_id = CAST(:advanced_new AS uuid)"
        ),
        {"advanced_old": ADVANCED_V2, "advanced_new": ADVANCED_V3},
    )
    connection.execute(
        sa.text(
            "DELETE FROM plan_versions WHERE id IN "
            "(CAST(:legacy AS uuid), CAST(:basic AS uuid), CAST(:advanced AS uuid))"
        ),
        {"legacy": LEGACY_V3, "basic": BASIC_V3, "advanced": ADVANCED_V3},
    )
    op.drop_index("ix_llm_calls_comparison_ai_run_id", table_name="llm_calls")
    op.drop_column("llm_calls", "comparison_ai_run_id")
    op.drop_index("ix_saved_comparison_user_updated", table_name="saved_comparisons")
    op.drop_table("saved_comparisons")
    op.drop_index("ix_comparison_request_user_created", table_name="comparison_requests")
    op.drop_table("comparison_requests")
    op.drop_table("comparison_ai_outputs")
    op.drop_index("ix_comparison_ai_run_status_created", table_name="comparison_ai_runs")
    op.drop_table("comparison_ai_runs")
    op.drop_index("ix_comparison_build_status_created", table_name="comparison_build_runs")
    op.drop_table("comparison_build_runs")
    op.drop_index("ix_comparison_snapshot_pair_created", table_name="comparison_snapshots")
    op.drop_table("comparison_snapshots")
