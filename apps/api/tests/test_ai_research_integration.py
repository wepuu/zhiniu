import asyncio
import os
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.ai_research.context import build_context
from zhaoniu_api.ai_research.models import (
    AIResearchDimension,
    AIResearchOutputDocument,
    AIResearchRunLease,
    CitedText,
    LLMCallAudit,
    StockHealthResearchV1,
)
from zhaoniu_api.ai_research.sql_repository import SQLAlchemyAIResearchRepository
from zhaoniu_api.config import get_settings
from zhaoniu_api.db import (
    AIResearchOutputRecord,
    AIResearchRunRecord,
    LLMCallRecord,
    ResearchObservationInputRecord,
    ResearchObservationRecord,
    ResearchSnapshotRecord,
    StockRecord,
)
from zhaoniu_api.domain.models import Stock
from zhaoniu_api.infrastructure.sql_repositories import SQLAlchemyStockRepository
from zhaoniu_api.research.models import (
    AttentionLevel,
    CalculationTrace,
    CoverageStatus,
    Movement,
    ObservationDimension,
    ResearchCoverage,
    ResearchObservation,
    ResearchSnapshotDocument,
)
from zhaoniu_api.research.sql_repository import SQLAlchemyResearchRepository

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _snapshot(symbol: str) -> ResearchSnapshotDocument:
    timestamp = datetime(2026, 8, 17, tzinfo=UTC)
    observation = ResearchObservation(
        id=uuid5(NAMESPACE_URL, f"ai-integration-observation-{symbol}"),
        symbol=symbol,
        dimension=ObservationDimension.GROWTH,
        observation_family="fixture",
        observation_type="fixture",
        attention_level=AttentionLevel.NOTICE,
        movement=Movement.NEUTRAL,
        title="收入动能出现阶段性变化",
        summary="现有公开信息触发确定性变化规则。",
        current_period=date(2026, 6, 30),
        comparison_periods=[],
        rule_id="fixture.growth",
        rule_version="v1",
        observation_key="fixture-growth",
        content_fingerprint="a" * 64,
        evidence_metrics=[],
        evidence_sources=[],
        calculation=CalculationTrace(method="fixture", expression="fixture"),
        generated_at=timestamp,
    )
    return ResearchSnapshotDocument(
        id=uuid5(NAMESPACE_URL, f"ai-integration-snapshot-{symbol}"),
        symbol=symbol,
        knowledge_cutoff=timestamp,
        data_version="fixture-data-v1",
        metric_version="fundamentals-v1",
        rule_set_version="fixture-rules-v1",
        research_template_version="fundamental_general:v1",
        snapshot_schema_version="research-snapshot-v1",
        producer_version="change-engine-v1",
        latest_financial_period=date(2026, 6, 30),
        latest_valuation_date=None,
        input_manifest={},
        coverage=[
            ResearchCoverage(
                dimension=dimension,
                status=(
                    CoverageStatus.AVAILABLE
                    if dimension == ObservationDimension.GROWTH
                    else CoverageStatus.MISSING
                ),
                reason=None,
            )
            for dimension in ObservationDimension
        ],
        observations=[observation],
        generated_at=timestamp,
    )


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_ai_run_claim_output_and_call_audit_are_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    assert TEST_DATABASE_URL != get_settings().database_url
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    symbol = "603998.SH"
    snapshot = _snapshot(symbol)
    context = build_context(snapshot)
    evidence_id = context.evidence_index[0].evidence_id
    idempotency_key = "b" * 64

    async def clean_up() -> None:
        async with sessions() as session:
            run_ids = select(AIResearchRunRecord.id).where(
                AIResearchRunRecord.symbol == symbol
            )
            await session.execute(
                delete(LLMCallRecord).where(LLMCallRecord.ai_run_id.in_(run_ids))
            )
            await session.execute(
                delete(AIResearchOutputRecord).where(
                    AIResearchOutputRecord.symbol == symbol
                )
            )
            await session.execute(
                delete(AIResearchRunRecord).where(AIResearchRunRecord.symbol == symbol)
            )
            await session.execute(
                delete(ResearchObservationInputRecord).where(
                    ResearchObservationInputRecord.observation_id
                    == snapshot.observations[0].id
                )
            )
            await session.execute(
                delete(ResearchObservationRecord).where(
                    ResearchObservationRecord.symbol == symbol
                )
            )
            await session.execute(
                delete(ResearchSnapshotRecord).where(
                    ResearchSnapshotRecord.symbol == symbol
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
                        symbol="603998",
                        canonical_symbol=symbol,
                        name="AI 集成测试股份",
                        exchange="SSE",
                        source="fixture",
                        collected_at=snapshot.generated_at,
                    )
                ]
            )
            await SQLAlchemyResearchRepository(session).save_research_snapshot(
                snapshot, snapshot.observations
            )

        async def acquire() -> AIResearchRunLease:
            async with sessions() as session:
                return await SQLAlchemyAIResearchRepository(session).acquire_run(
                    canonical_symbol=symbol,
                    snapshot_id=snapshot.id,
                    idempotency_key=idempotency_key,
                    context_version=context.context_version,
                    context_hash=context.context_hash,
                    prompt_version="prompt-v1",
                    prompt_hash="c" * 64,
                    output_schema_version="stock-health-v1",
                    model_route_version="route-v1",
                    route_hash="d" * 64,
                    retry_failed=False,
                )

        leases = await asyncio.gather(acquire(), acquire())
        assert sum(lease.acquired for lease in leases) == 1
        lease = next(lease for lease in leases if lease.acquired)
        content = StockHealthResearchV1(
            headline=CitedText(text="经营表现呈现阶段性变化", evidence_refs=[evidence_id]),
            executive_summary=[
                CitedText(text="现有证据需要持续核对", evidence_refs=[evidence_id]),
                CitedText(text="研究结论限于公开证据", evidence_refs=[evidence_id]),
            ],
            dimensions=[
                AIResearchDimension(
                    dimension=dimension,
                    interpretation=(
                        CitedText(
                            text="成长表现呈现阶段性变化",
                            evidence_refs=[evidence_id],
                        )
                        if dimension == ObservationDimension.GROWTH
                        else None
                    ),
                )
                for dimension in ObservationDimension
            ],
        )
        output = AIResearchOutputDocument(
            output_id=uuid5(NAMESPACE_URL, idempotency_key),
            run_id=lease.run_id,
            symbol=symbol,
            snapshot_id=snapshot.id,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            provider_display_name="Qwen",
            model_display_name="dashscope/fixture",
            context_version=context.context_version,
            context_hash=context.context_hash,
            prompt_version="prompt-v1",
            prompt_hash="c" * 64,
            output_schema_version="stock-health-v1",
            model_route_version="route-v1",
            route_hash="d" * 64,
            content=content,
            evidence_index=context.evidence_index,
            coverage=context.coverage,
            generated_at=snapshot.generated_at,
        )
        async with sessions() as session:
            repository = SQLAlchemyAIResearchRepository(session)
            await repository.record_call(
                LLMCallAudit(
                    run_id=output.run_id,
                    attempt_index=1,
                    task_type="stock_health",
                    provider="DeepSeek",
                    model="deepseek/fixture",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=10,
                    cost_microunits=None,
                    status="failed",
                    error_code="provider_timeout",
                )
            )
            await repository.record_call(
                LLMCallAudit(
                    run_id=output.run_id,
                    attempt_index=2,
                    task_type="stock_health",
                    provider="Qwen",
                    model="dashscope/fixture",
                    input_tokens=20,
                    output_tokens=10,
                    latency_ms=20,
                    cost_microunits=None,
                    status="succeeded",
                )
            )
            await repository.complete_run(output, idempotency_key=idempotency_key)
            await repository.complete_run(output, idempotency_key=idempotency_key)
            assert await repository.find_output_by_key(idempotency_key) == output
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AIResearchOutputRecord)
                    .where(AIResearchOutputRecord.symbol == symbol)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(LLMCallRecord)
                    .where(LLMCallRecord.ai_run_id == output.run_id)
                )
                == 2
            )
    finally:
        await clean_up()
        await engine.dispose()
