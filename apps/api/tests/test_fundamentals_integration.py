import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.config import get_settings
from zhaoniu_api.db import (
    FinancialReportRevisionRecord,
    FundamentalMetricRecord,
    FundamentalSnapshotRecord,
    IncomeStatementRecord,
    StockRecord,
    ValuationObservationRecord,
)
from zhaoniu_api.domain.models import Stock
from zhaoniu_api.fundamentals.metrics import (
    METRIC_VERSION,
    compute_fundamental_metrics,
    make_data_version,
)
from zhaoniu_api.fundamentals.models import (
    BalanceSheet,
    FinancialReport,
    FiscalPeriod,
    FundamentalSnapshot,
    IncomeStatement,
    PublishedAtPrecision,
    StatementScope,
    ValuationObservation,
)
from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyFundamentalRepository,
    SQLAlchemyStockRepository,
)

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_financial_report_snapshot_and_valuation_upserts_are_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    assert TEST_DATABASE_URL != get_settings().database_url
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    symbol = "601997.SH"
    timestamp = datetime(2025, 4, 1, tzinfo=UTC)
    report = FinancialReport(
        canonical_symbol=symbol,
        fiscal_year=2024,
        fiscal_period=FiscalPeriod.FY,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        statement_scope=StatementScope.CONSOLIDATED,
        currency="CNY",
        provider="fixture",
        provider_record_id="fixture-601997-2024",
        provider_revision="1",
        payload_checksum="a" * 64,
        published_at=timestamp,
        published_at_precision=PublishedAtPrecision.DATE,
        known_at=timestamp,
        first_observed_at=timestamp,
        source_updated_at=timestamp,
        is_audited=True,
        issuer_type="general",
        income=IncomeStatement(
            revenue=Decimal("1000"),
            operating_cost=Decimal("800"),
            net_profit=Decimal("100"),
            parent_net_profit=Decimal("90"),
        ),
        balance=BalanceSheet(
            cash=Decimal("200"),
            current_assets=Decimal("600"),
            total_assets=Decimal("1200"),
            current_liabilities=Decimal("300"),
            total_liabilities=Decimal("500"),
            parent_equity=Decimal("700"),
            total_equity=Decimal("700"),
        ),
        cash_flow=None,
    )
    valuation = ValuationObservation(
        canonical_symbol=symbol,
        trade_date=date(2025, 4, 1),
        metric_code="pe_ttm",
        value=Decimal("12.5"),
        unit="multiple",
        provider="fixture",
        collected_at=timestamp,
    )
    try:
        async with sessions() as session:
            await SQLAlchemyStockRepository(session).upsert_many(
                [
                    Stock(
                        symbol="601997",
                        canonical_symbol=symbol,
                        name="集成测试股份",
                        exchange="SSE",
                        source="fixture",
                        collected_at=timestamp,
                    )
                ]
            )
            repository = SQLAlchemyFundamentalRepository(session)
            assert await repository.upsert_reports([report]) == 1
            assert await repository.upsert_reports([report]) == 0
            assert await repository.upsert_valuations([valuation]) == 1
            assert await repository.upsert_valuations([valuation]) == 1
            snapshot = FundamentalSnapshot(
                canonical_symbol=symbol,
                as_of=timestamp,
                data_version=make_data_version([report]),
                metric_version=METRIC_VERSION,
                latest_period_end=report.period_end,
                metrics=compute_fundamental_metrics([report]),
            )
            await repository.save_snapshot(snapshot)
            await repository.save_snapshot(snapshot)
            assert len(await repository.list_reports(symbol, as_of=None, limit=10)) == 1
            assert (
                len(
                    await repository.list_valuations(
                        symbol, start=None, end=None, metric_codes=None, limit=10
                    )
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(FinancialReportRevisionRecord)
                    .where(FinancialReportRevisionRecord.symbol == symbol)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(FundamentalSnapshotRecord)
                    .where(FundamentalSnapshotRecord.symbol == symbol)
                )
                == 1
            )
    finally:
        async with sessions() as session:
            snapshot_ids = select(FundamentalSnapshotRecord.id).where(
                FundamentalSnapshotRecord.symbol == symbol
            )
            await session.execute(
                delete(FundamentalMetricRecord).where(
                    FundamentalMetricRecord.snapshot_id.in_(snapshot_ids)
                )
            )
            await session.execute(
                delete(FundamentalSnapshotRecord).where(FundamentalSnapshotRecord.symbol == symbol)
            )
            report_ids = select(FinancialReportRevisionRecord.id).where(
                FinancialReportRevisionRecord.symbol == symbol
            )
            await session.execute(
                delete(IncomeStatementRecord).where(IncomeStatementRecord.report_id.in_(report_ids))
            )
            await session.execute(
                delete(ValuationObservationRecord).where(
                    ValuationObservationRecord.symbol == symbol
                )
            )
            await session.execute(
                delete(FinancialReportRevisionRecord).where(
                    FinancialReportRevisionRecord.symbol == symbol
                )
            )
            await session.execute(delete(StockRecord).where(StockRecord.symbol == symbol))
            await session.commit()
        await engine.dispose()
