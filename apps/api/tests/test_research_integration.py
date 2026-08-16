import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.config import get_settings
from zhaoniu_api.db import (
    FundamentalMetricPointRecord,
    ResearchBuildRunRecord,
    ResearchObservationInputRecord,
    ResearchObservationRecord,
    ResearchSnapshotRecord,
    StockRecord,
)
from zhaoniu_api.domain.models import Stock
from zhaoniu_api.infrastructure.sql_repositories import SQLAlchemyStockRepository
from zhaoniu_api.research.models import (
    FundamentalMetricPoint,
    ResearchSnapshotDocument,
)
from zhaoniu_api.research.rules import evaluate_rules, rule_set_version
from zhaoniu_api.research.sql_repository import SQLAlchemyResearchRepository

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _point(symbol: str, period_end: date, value: str, fiscal_period: str) -> FundamentalMetricPoint:
    fingerprint = f"fixture-{symbol}-{period_end}-{value}"
    return FundamentalMetricPoint(
        id=uuid5(NAMESPACE_URL, fingerprint),
        canonical_symbol=symbol,
        code="revenue_single_quarter_yoy",
        value=Decimal(value),
        unit="percent",
        status="available",
        period_end=period_end,
        fiscal_period=fiscal_period,
        basis="standalone",
        known_at=datetime(2026, 8, 16, tzinfo=UTC),
        metric_version="fundamentals-v1",
        input_fingerprint=fingerprint,
    )


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_research_snapshot_inputs_and_build_run_are_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    assert TEST_DATABASE_URL != get_settings().database_url
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    symbol = "603999.SH"
    timestamp = datetime(2026, 8, 16, tzinfo=UTC)
    points = [
        _point(symbol, date(2025, 12, 31), "5", "FY"),
        _point(symbol, date(2026, 3, 31), "8", "Q1"),
        _point(symbol, date(2026, 6, 30), "12", "H1"),
    ]
    observations = list(
        evaluate_rules(
            symbol=symbol,
            issuer_type="general",
            template_version="fundamental_general:v1",
            points=points,
            reports=[],
            generated_at=timestamp,
        )
    )
    assert len(observations) == 1
    snapshot_id = uuid5(NAMESPACE_URL, f"fixture-snapshot-{symbol}")
    snapshot = ResearchSnapshotDocument(
        id=snapshot_id,
        symbol=symbol,
        knowledge_cutoff=timestamp,
        data_version="fixture-data-v1",
        metric_version="fundamentals-v1",
        rule_set_version=rule_set_version(),
        research_template_version="fundamental_general:v1",
        snapshot_schema_version="research-snapshot-v1",
        producer_version="change-engine-v1",
        latest_financial_period=date(2026, 6, 30),
        latest_valuation_date=None,
        input_manifest={},
        coverage=[],
        observations=observations,
        generated_at=timestamp,
    )

    async def clean_up() -> None:
        async with sessions() as session:
            await session.execute(
                delete(ResearchBuildRunRecord).where(ResearchBuildRunRecord.symbol == symbol)
            )
            await session.execute(
                delete(ResearchObservationInputRecord).where(
                    ResearchObservationInputRecord.observation_id == observations[0].id
                )
            )
            await session.execute(
                delete(ResearchObservationRecord).where(ResearchObservationRecord.symbol == symbol)
            )
            await session.execute(
                delete(ResearchSnapshotRecord).where(ResearchSnapshotRecord.symbol == symbol)
            )
            await session.execute(
                delete(FundamentalMetricPointRecord).where(
                    FundamentalMetricPointRecord.symbol == symbol
                )
            )
            await session.execute(delete(StockRecord).where(StockRecord.symbol == symbol))
            await session.commit()

    await clean_up()
    try:
        async with sessions() as session:
            await SQLAlchemyStockRepository(session).upsert_many(
                [
                    Stock(
                        symbol="603999",
                        canonical_symbol=symbol,
                        name="研究集成测试股份",
                        exchange="SSE",
                        source="fixture",
                        collected_at=timestamp,
                    )
                ]
            )
            repository = SQLAlchemyResearchRepository(session)
            assert await repository.upsert_metric_points(points) == 3
            assert await repository.upsert_metric_points(points) == 0
            await repository.save_research_snapshot(snapshot, observations)
            await repository.save_research_snapshot(snapshot, observations)
            lease = await repository.acquire_research_run(
                canonical_symbol=symbol,
                idempotency_key="f" * 64,
                data_version=snapshot.data_version,
                metric_version=snapshot.metric_version,
                rule_set_version=snapshot.rule_set_version,
                template_version=snapshot.research_template_version,
            )
            assert lease.acquired
            await repository.finish_research_run(
                lease.run_id,
                status="succeeded",
                snapshot_id=snapshot.id,
                observation_count=1,
                error_summary=None,
                finished_at=timestamp,
            )
            repeated = await repository.acquire_research_run(
                canonical_symbol=symbol,
                idempotency_key="f" * 64,
                data_version=snapshot.data_version,
                metric_version=snapshot.metric_version,
                rule_set_version=snapshot.rule_set_version,
                template_version=snapshot.research_template_version,
            )
            assert not repeated.acquired
            assert repeated.status == "succeeded"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchSnapshotRecord)
                    .where(ResearchSnapshotRecord.symbol == symbol)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchObservationRecord)
                    .where(ResearchObservationRecord.symbol == symbol)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchObservationInputRecord)
                    .where(ResearchObservationInputRecord.observation_id == observations[0].id)
                )
                == 3
            )
    finally:
        await clean_up()
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(FundamentalMetricPointRecord)
                    .where(FundamentalMetricPointRecord.symbol == symbol)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ResearchBuildRunRecord)
                    .where(ResearchBuildRunRecord.symbol == symbol)
                )
                == 0
            )
        await engine.dispose()
