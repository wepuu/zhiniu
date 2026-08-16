"""Add immutable financial reports, deterministic metrics, and valuation observations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("issuer_type", sa.String(32), nullable=False, server_default="general"),
    )
    op.create_table(
        "financial_report_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(4), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("statement_scope", sa.String(24), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_record_id", sa.String(160), nullable=False),
        sa.Column("provider_revision", sa.String(80), nullable=False),
        sa.Column("payload_checksum", sa.String(64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at_precision", sa.String(16), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("is_audited", sa.Boolean()),
        sa.Column("issuer_type", sa.String(32), nullable=False),
        sa.Column("quality_warnings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "symbol",
            "provider",
            "period_end",
            "statement_scope",
            "payload_checksum",
            name="uq_financial_report_revision_identity",
        ),
    )
    op.create_index(
        "ix_financial_report_symbol_period",
        "financial_report_revisions",
        ["symbol", "period_end"],
    )
    op.create_index(
        "ix_financial_report_symbol_known_at",
        "financial_report_revisions",
        ["symbol", "known_at"],
    )

    money_columns = {
        "income_statement_facts": (
            "total_revenue",
            "revenue",
            "operating_cost",
            "selling_expenses",
            "administrative_expenses",
            "research_expenses",
            "finance_expenses",
            "operating_profit",
            "total_profit",
            "income_tax_expense",
            "net_profit",
            "parent_net_profit",
        ),
        "balance_sheet_facts": (
            "cash",
            "accounts_receivable",
            "inventory",
            "contract_assets",
            "current_assets",
            "total_assets",
            "short_term_borrowings",
            "current_portion_noncurrent_liabilities",
            "long_term_borrowings",
            "bonds_payable",
            "lease_liabilities",
            "contract_liabilities",
            "current_liabilities",
            "total_liabilities",
            "parent_equity",
            "total_equity",
            "goodwill",
        ),
        "cash_flow_statement_facts": (
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
            "cash_paid_for_long_term_assets",
            "ending_cash",
        ),
    }
    for table_name, columns in money_columns.items():
        op.create_table(
            table_name,
            sa.Column(
                "report_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("financial_report_revisions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            *(sa.Column(column, sa.Numeric(30, 4)) for column in columns),
        )

    op.create_table(
        "fundamental_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_version", sa.String(64), nullable=False),
        sa.Column("metric_version", sa.String(40), nullable=False),
        sa.Column("latest_period_end", sa.Date()),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "symbol",
            "data_version",
            "metric_version",
            name="uq_fundamental_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_fundamental_snapshot_symbol_as_of", "fundamental_snapshots", ["symbol", "as_of"]
    )
    op.create_table(
        "fundamental_metric_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fundamental_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("value", sa.Numeric(30, 8)),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("period_end", sa.Date()),
        sa.Column("basis", sa.String(24), nullable=False),
        sa.Column("input_report_ids", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("detail", sa.String(240)),
        sa.UniqueConstraint("snapshot_id", "code", name="uq_fundamental_metric_snapshot_code"),
    )
    op.create_index(
        "ix_fundamental_metric_values_snapshot_id",
        "fundamental_metric_values",
        ["snapshot_id"],
    )
    op.create_table(
        "valuation_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("metric_code", sa.String(40), nullable=False),
        sa.Column("value", sa.Numeric(30, 8), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "symbol",
            "trade_date",
            "metric_code",
            "provider",
            name="uq_valuation_observation_identity",
        ),
    )
    op.create_index(
        "ix_valuation_symbol_metric_date",
        "valuation_observations",
        ["symbol", "metric_code", "trade_date"],
    )


def downgrade() -> None:
    op.drop_table("valuation_observations")
    op.drop_table("fundamental_metric_values")
    op.drop_table("fundamental_snapshots")
    op.drop_table("cash_flow_statement_facts")
    op.drop_table("balance_sheet_facts")
    op.drop_table("income_statement_facts")
    op.drop_table("financial_report_revisions")
    op.drop_column("stocks", "issuer_type")
