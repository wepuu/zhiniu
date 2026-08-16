"""Version financial canonicalization independently from provider payloads."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0005"
down_revision: str | None = "20260816_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_report_revisions",
        sa.Column(
            "normalizer_version",
            sa.String(40),
            nullable=False,
            server_default="financial-akshare-v1",
        ),
    )
    op.drop_constraint(
        "uq_financial_report_revision_identity",
        "financial_report_revisions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_financial_report_revision_identity",
        "financial_report_revisions",
        [
            "symbol",
            "provider",
            "period_end",
            "statement_scope",
            "normalizer_version",
            "payload_checksum",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_financial_report_revision_identity",
        "financial_report_revisions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_financial_report_revision_identity",
        "financial_report_revisions",
        ["symbol", "provider", "period_end", "statement_scope", "payload_checksum"],
    )
    op.drop_column("financial_report_revisions", "normalizer_version")
