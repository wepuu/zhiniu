"""add personalized research feed and in-app alerts

Revision ID: 20260820_0012
Revises: 20260819_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0012"
down_revision: str | None = "20260819_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("csrf_token_hash", sa.String(64), nullable=True))
    # Legacy sessions have no recoverable raw CSRF token, so require a fresh login.
    op.execute(
        "UPDATE user_sessions SET csrf_token_hash = token_hash, "
        "revoked_at = COALESCE(revoked_at, now()) WHERE csrf_token_hash IS NULL"
    )
    op.alter_column("user_sessions", "csrf_token_hash", nullable=False)

    op.create_table(
        "peer_position_observations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_peer_metric_position_id",
            UUID,
            sa.ForeignKey("company_peer_metric_positions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observation_family", sa.String(120), nullable=False),
        sa.Column("observation_type", sa.String(48), nullable=False),
        sa.Column("attention_level", sa.String(24), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("rule_version", sa.String(24), nullable=False),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("detail_payload", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("content_fingerprint", name="uq_peer_position_observation_content"),
    )
    op.create_index(
        "ix_peer_position_observation_symbol_known",
        "peer_position_observations",
        ["symbol", "known_at"],
    )

    op.create_table(
        "research_signals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column(
            "research_observation_id",
            UUID,
            sa.ForeignKey("research_observations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "peer_position_observation_id",
            UUID,
            sa.ForeignKey("peer_position_observations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "corporate_event_id", UUID, sa.ForeignKey("corporate_events.id", ondelete="RESTRICT")
        ),
        sa.Column("signal_family", sa.String(120), nullable=False),
        sa.Column("signal_type", sa.String(64), nullable=False),
        sa.Column("attention_level", sa.String(24), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_on", sa.Date()),
        sa.Column("dedup_group_key", sa.String(128), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(64), nullable=False),
        sa.Column("projection_version", sa.String(40), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.String(800), nullable=False),
        sa.Column("display_payload", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(CASE WHEN research_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN peer_position_observation_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN corporate_event_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_research_signal_one_source",
        ),
        sa.UniqueConstraint(
            "source_kind", "semantic_fingerprint", name="uq_research_signal_semantic"
        ),
    )
    op.create_index("ix_research_signal_symbol_known", "research_signals", ["symbol", "known_at"])

    op.create_table(
        "research_signal_projection_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_artifact_identity", sa.String(160), nullable=False),
        sa.Column("projection_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("projected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "source_kind",
            "source_artifact_identity",
            "projection_version",
            name="uq_research_signal_projection_run",
        ),
    )

    op.create_table(
        "user_research_alert_settings",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("minimum_attention", sa.String(24), server_default="important", nullable=False),
        sa.Column("fundamental_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("peer_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "corporate_event_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("settings_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute(
        "INSERT INTO user_research_alert_settings (user_id) "
        "SELECT id FROM users ON CONFLICT DO NOTHING"
    )

    op.create_table(
        "user_research_alert_deliveries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "signal_id",
            UUID,
            sa.ForeignKey("research_signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delivery_reason", sa.String(120), nullable=False),
        sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_user_research_alert_delivery"),
    )
    op.create_index(
        "ix_user_research_alert_unread",
        "user_research_alert_deliveries",
        ["user_id", "read_at", "created_at"],
    )

    op.create_table(
        "research_alert_dispatch_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "signal_id",
            UUID,
            sa.ForeignKey("research_signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matcher_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_user_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivery_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("signal_id", "matcher_version", name="uq_research_alert_dispatch_run"),
    )


def downgrade() -> None:
    op.drop_table("research_alert_dispatch_runs")
    op.drop_index("ix_user_research_alert_unread", table_name="user_research_alert_deliveries")
    op.drop_table("user_research_alert_deliveries")
    op.drop_table("user_research_alert_settings")
    op.drop_table("research_signal_projection_runs")
    op.drop_index("ix_research_signal_symbol_known", table_name="research_signals")
    op.drop_table("research_signals")
    op.drop_index(
        "ix_peer_position_observation_symbol_known", table_name="peer_position_observations"
    )
    op.drop_table("peer_position_observations")
    op.drop_column("user_sessions", "csrf_token_hash")
