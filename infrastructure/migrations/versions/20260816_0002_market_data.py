"""Add canonical A-share market data foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0002"
down_revision: str | None = "20260816_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("ticker", sa.String(6), nullable=True))
    op.add_column("stocks", sa.Column("asset_type", sa.String(24), nullable=True))
    op.add_column("stocks", sa.Column("board", sa.String(24), nullable=True))
    op.add_column("stocks", sa.Column("list_date", sa.Date(), nullable=True))
    op.add_column("stocks", sa.Column("status", sa.String(24), nullable=True))
    op.add_column("stocks", sa.Column("source", sa.String(40), nullable=True))
    op.add_column("stocks", sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE stocks SET
          ticker = split_part(symbol, '.', 1),
          asset_type = 'stock',
          board = CASE
            WHEN split_part(symbol, '.', 1) LIKE '688%' THEN 'star'
            WHEN split_part(symbol, '.', 1) LIKE '300%' THEN 'chinext'
            WHEN split_part(symbol, '.', 1) LIKE '002%' THEN 'sme'
            WHEN split_part(symbol, '.', 1) LIKE '4%'
              OR split_part(symbol, '.', 1) LIKE '8%'
              OR split_part(symbol, '.', 1) LIKE '92%' THEN 'beijing'
            ELSE 'main' END,
          status = 'listed', source = 'phase0', collected_at = now()
        """
    )
    op.execute(
        """
        INSERT INTO stocks (
          symbol, ticker, name, exchange, industry_code, asset_type, board,
          list_date, status, source, collected_at, created_at, updated_at
        )
        SELECT
          ticker || CASE WHEN exchange = 'SSE' THEN '.SH'
                         WHEN exchange = 'BSE' THEN '.BJ' ELSE '.SZ' END,
          ticker, name, exchange, industry_code, asset_type, board,
          list_date, status, source, collected_at, created_at, updated_at
        FROM stocks WHERE symbol !~ '\\.'
        ON CONFLICT (symbol) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE watchlist_items w SET symbol = s.ticker ||
          CASE WHEN s.exchange = 'SSE' THEN '.SH'
               WHEN s.exchange = 'BSE' THEN '.BJ' ELSE '.SZ' END
        FROM stocks s WHERE w.symbol = s.symbol AND s.symbol !~ '\\.'
        """
    )
    op.execute(
        """
        UPDATE research_snapshots r SET symbol = s.ticker ||
          CASE WHEN s.exchange = 'SSE' THEN '.SH'
               WHEN s.exchange = 'BSE' THEN '.BJ' ELSE '.SZ' END
        FROM stocks s WHERE r.symbol = s.symbol AND s.symbol !~ '\\.'
        """
    )
    op.execute("DELETE FROM stocks WHERE symbol !~ '\\.'")
    for column in ("ticker", "asset_type", "board", "status", "source", "collected_at"):
        op.alter_column("stocks", column, nullable=False)
    op.create_unique_constraint("uq_stocks_ticker_exchange", "stocks", ["ticker", "exchange"])

    op.create_table(
        "stock_daily_bars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("adjust_type", sa.String(16), nullable=False),
        sa.Column("open", sa.Numeric(20, 6), nullable=False),
        sa.Column("high", sa.Numeric(20, 6), nullable=False),
        sa.Column("low", sa.Numeric(20, 6), nullable=False),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("pre_close", sa.Numeric(20, 6)),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(30, 4), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "symbol", "trade_date", "adjust_type", name="uq_stock_daily_bar_identity"
        ),
    )
    op.create_index("ix_stock_daily_bars_symbol_date", "stock_daily_bars", ["symbol", "trade_date"])
    op.create_table(
        "data_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("symbol", sa.String(16)),
        sa.Column("requested_start", sa.Date()),
        sa.Column("requested_end", sa.Date()),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("written_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_summary", sa.String(500)),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in ("dataset", "provider", "symbol", "idempotency_key", "status"):
        op.create_index(f"ix_data_sync_runs_{column}", "data_sync_runs", [column])


def downgrade() -> None:
    op.drop_table("data_sync_runs")
    op.drop_table("stock_daily_bars")
    op.drop_constraint("uq_stocks_ticker_exchange", "stocks", type_="unique")
    for column in (
        "collected_at",
        "source",
        "status",
        "list_date",
        "board",
        "asset_type",
        "ticker",
    ):
        op.drop_column("stocks", column)
