import os
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.config import Settings
from zhaoniu_api.coverage.service import ResearchCoverageService
from zhaoniu_api.db import StockRecord

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_universe_coverage_and_backfill_plan_are_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    cutoff = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        coverage_operator_pinned_symbols="603998",
        coverage_acceptance_symbols="603998",
    )
    async with sessions() as session:
        if await session.get(StockRecord, "603998.SH") is None:
            session.add(
                StockRecord(
                    symbol="603998.SH",
                    ticker="603998",
                    name="覆盖集成测试",
                    exchange="SSE",
                    asset_type="stock",
                    board="main",
                    status="listed",
                    issuer_type="general",
                    source="fixture",
                    collected_at=cutoff,
                )
            )
            await session.commit()
        service = ResearchCoverageService(session, settings)

        universe = await service.build_universe(as_of=cutoff)
        repeated_universe = await service.build_universe(as_of=cutoff)
        assert repeated_universe.id == universe.id
        assert "603998.SH" in {item.symbol for item in universe.items}

        coverage = await service.build_coverage_snapshot(universe.id, as_of=cutoff)
        repeated_coverage = await service.build_coverage_snapshot(universe.id, as_of=cutoff)
        assert repeated_coverage.id == coverage.id
        assert repeated_coverage.status == "skipped"

        plan = await service.plan_backfill(coverage.id)
        repeated_plan = await service.plan_backfill(coverage.id)
        assert repeated_plan.id == plan.id
        assert plan.planned_items > 0
        assert all(item.action_key != "generate_ai_research" for item in plan.items)
    await engine.dispose()
