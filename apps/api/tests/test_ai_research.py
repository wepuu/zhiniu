import asyncio
from datetime import UTC, date, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi.testclient import TestClient
from zhaoniu_api.ai_research.context import build_context
from zhaoniu_api.ai_research.litellm_gateway import provider_name
from zhaoniu_api.ai_research.models import StockHealthResearchV1
from zhaoniu_api.ai_research.service import AIResearchOptions, AIResearchService
from zhaoniu_api.ai_research.validation import (
    AIOutputValidationError,
    validate_stock_health_output,
)
from zhaoniu_api.dependencies import get_ai_research_service, get_stock_repository
from zhaoniu_api.infrastructure.mock_repositories import (
    InMemoryAIResearchRepository,
    InMemoryResearchRepository,
    InMemoryStockRepository,
)
from zhaoniu_api.main import create_app
from zhaoniu_api.ports.providers import (
    LLMGatewayError,
    LLMStructuredResponse,
    LLMUsage,
)
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


def _observation(
    dimension: ObservationDimension,
    attention: AttentionLevel,
    *,
    ordinal: int,
) -> ResearchObservation:
    observation_id = uuid5(NAMESPACE_URL, f"ai-observation-{dimension}-{ordinal}")
    return ResearchObservation(
        id=observation_id,
        symbol="600519.SH",
        dimension=dimension,
        observation_family="fixture",
        observation_type="fixture",
        attention_level=attention,
        movement=Movement.NEUTRAL,
        title=f"{dimension.value} observation",
        summary="deterministic fixture summary",
        current_period=date(2026, 6, 30 - min(ordinal, 29)),
        comparison_periods=[],
        rule_id=f"fixture.{dimension.value}.{ordinal}",
        rule_version="v1",
        observation_key=f"fixture-{ordinal:02}",
        content_fingerprint=f"{ordinal:064x}",
        evidence_metrics=[],
        evidence_sources=[],
        calculation=CalculationTrace(method="fixture", expression="fixture"),
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


def _snapshot() -> ResearchSnapshotDocument:
    observations = [
        _observation(ObservationDimension.GROWTH, AttentionLevel.IMPORTANT, ordinal=1),
        _observation(ObservationDimension.QUALITY, AttentionLevel.NOTICE, ordinal=2),
    ]
    coverage = [
        ResearchCoverage(
            dimension=dimension,
            status=(
                CoverageStatus.AVAILABLE
                if dimension in {ObservationDimension.GROWTH, ObservationDimension.QUALITY}
                else CoverageStatus.MISSING
            ),
            reason=None,
        )
        for dimension in ObservationDimension
    ]
    return ResearchSnapshotDocument(
        id=uuid5(NAMESPACE_URL, "ai-snapshot"),
        symbol="600519.SH",
        knowledge_cutoff=datetime(2026, 8, 16, tzinfo=UTC),
        data_version="data-v1",
        metric_version="fundamentals-v1",
        rule_set_version="rules-v1",
        research_template_version="fundamental_general:v1",
        snapshot_schema_version="research-snapshot-v1",
        producer_version="change-engine-v1",
        latest_financial_period=date(2026, 6, 30),
        latest_valuation_date=date(2026, 8, 15),
        input_manifest={},
        coverage=coverage,
        observations=observations,
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


def _valid_payload(evidence: dict[str, str]) -> dict[str, object]:
    dimensions: list[dict[str, object]] = []
    for dimension in ObservationDimension:
        reference = evidence.get(dimension.value)
        dimensions.append(
            {
                "dimension": dimension.value,
                "interpretation": (
                    {
                        "text": "相关经营表现呈现阶段性变化",
                        "evidence_refs": [reference],
                    }
                    if reference
                    else None
                ),
            }
        )
    first = next(iter(evidence.values()))
    return {
        "schema_version": "stock-health-v1",
        "headline": {"text": "公开信息呈现阶段性变化", "evidence_refs": [first]},
        "executive_summary": [
            {"text": "经营表现需要结合后续披露持续观察", "evidence_refs": [first]},
            {"text": "现有结论仅覆盖已收录的公开证据", "evidence_refs": [first]},
        ],
        "dimensions": dimensions,
        "attention_items": [],
    }


class FakeGateway:
    def __init__(self, outcomes: list[dict[str, object] | Exception]) -> None:
        self.outcomes = outcomes
        self.models: list[str] = []

    def supports_structured_output(self, model: str) -> bool:
        return True

    async def generate_structured(
        self,
        *,
        model: str,
        task_type: str,
        system_prompt: str,
        input_data: dict[str, object],
        response_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> LLMStructuredResponse:
        self.models.append(model)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return LLMStructuredResponse(
            data=outcome,
            usage=LLMUsage(
                task_type=task_type,
                provider=model.split("/", 1)[0],
                model=model,
                input_tokens=100,
                output_tokens=50,
                latency_ms=25,
                status="succeeded",
            ),
            finish_reason="stop",
        )


class SlowGateway(FakeGateway):
    async def generate_structured(self, **kwargs: Any) -> LLMStructuredResponse:
        self.models.append(str(kwargs["model"]))
        await asyncio.sleep(0.05)
        raise AssertionError("attempt should have been cancelled by the service timeout")


def test_context_is_stable_and_output_validation_is_fail_closed() -> None:
    context = build_context(_snapshot())
    repeated = build_context(_snapshot())
    assert context.context_hash == repeated.context_hash
    assert [item.evidence_id for item in context.evidence_index] == [
        item.evidence_id for item in repeated.evidence_index
    ]
    evidence = {item.dimension.value: item.evidence_id for item in context.evidence_index}
    valid = validate_stock_health_output(_valid_payload(evidence), context)
    assert isinstance(valid, StockHealthResearchV1)

    numeric = _valid_payload(evidence)
    numeric["headline"] = {
        "text": "收入增长达到百分之十",
        "evidence_refs": [next(iter(evidence.values()))],
    }
    with pytest.raises(AIOutputValidationError, match="numbers"):
        validate_stock_health_output(numeric, context)

    invalid_citation = _valid_payload(evidence)
    invalid_citation["headline"] = {
        "text": "经营表现需要观察",
        "evidence_refs": ["EV-000000000000"],
    }
    with pytest.raises(AIOutputValidationError, match="unknown evidence"):
        validate_stock_health_output(invalid_citation, context)


async def test_multi_provider_fallback_is_idempotent_and_bank_is_unsupported() -> None:
    stocks = InMemoryStockRepository()
    research = InMemoryResearchRepository()
    snapshot = _snapshot()
    await research.save_research_snapshot(snapshot, snapshot.observations)
    context = build_context(snapshot)
    evidence = {item.dimension.value: item.evidence_id for item in context.evidence_index}
    gateway = FakeGateway(
        [LLMGatewayError("provider_timeout", "timeout"), _valid_payload(evidence)]
    )
    repository = InMemoryAIResearchRepository()
    service = AIResearchService(
        stocks=stocks,
        research=research,
        ai_research=repository,
        gateway=gateway,
        options=AIResearchOptions(
            enabled=True,
            model_chain=("deepseek/fixture", "dashscope/fixture"),
        ),
    )

    first = await service.generate_stock_health("600519")
    assert first.status == "succeeded"
    assert gateway.models == ["deepseek/fixture", "dashscope/fixture"]
    assert [item.status for item in repository.calls] == ["failed", "succeeded"]
    second = await service.generate_stock_health("600519")
    assert second.status == "skipped"
    assert len(repository.outputs) == 1

    before = len(repository.calls)
    unsupported = await service.generate_stock_health("000001")
    assert unsupported.status == "unsupported"
    assert len(repository.calls) == before

    envelope = await service.get_stock_health("600519")
    assert envelope.status == "ready"
    assert envelope.freshness == "current"
    assert envelope.output and envelope.output.ai_generated


async def test_schema_failure_and_hard_timeout_advance_the_route() -> None:
    stocks = InMemoryStockRepository()
    research = InMemoryResearchRepository()
    snapshot = _snapshot()
    await research.save_research_snapshot(snapshot, snapshot.observations)
    context = build_context(snapshot)
    evidence = {item.dimension.value: item.evidence_id for item in context.evidence_index}
    invalid_schema = {"headline": "not a cited text"}
    gateway = FakeGateway([invalid_schema, _valid_payload(evidence)])
    repository = InMemoryAIResearchRepository()
    service = AIResearchService(
        stocks=stocks,
        research=research,
        ai_research=repository,
        gateway=gateway,
        options=AIResearchOptions(
            enabled=True,
            model_chain=("openai/invalid", "gemini/valid"),
        ),
    )
    result = await service.generate_stock_health("600519")
    assert result.status == "succeeded"
    assert [item.status for item in repository.calls] == ["rejected", "succeeded"]
    assert repository.calls[0].error_code == "schema_invalid"

    timeout_repository = InMemoryAIResearchRepository()
    timeout_service = AIResearchService(
        stocks=stocks,
        research=research,
        ai_research=timeout_repository,
        gateway=SlowGateway([]),
        options=AIResearchOptions(
            enabled=True,
            model_chain=("deepseek/slow",),
            per_model_timeout_seconds=0.01,
        ),
    )
    timeout_result = await timeout_service.generate_stock_health("600519")
    assert timeout_result.status == "failed"
    assert timeout_repository.calls[0].error_code == "provider_timeout"


def test_four_provider_route_names_are_stable() -> None:
    assert {
        model: provider_name(model)
        for model in (
            "deepseek/model",
            "dashscope/model",
            "openai/model",
            "gemini/model",
        )
    } == {
        "deepseek/model": "DeepSeek",
        "dashscope/model": "Qwen",
        "openai/model": "OpenAI",
        "gemini/model": "Gemini",
    }
    assert AIResearchOptions(
        enabled=True,
        model_chain=("deepseek/model", "deepseek/model", "openai/model"),
    ).active_models == ("deepseek/model", "openai/model")


async def test_ai_read_api_is_read_only_and_returns_disabled_state() -> None:
    stocks = InMemoryStockRepository()
    research = InMemoryResearchRepository()
    snapshot = _snapshot()
    await research.save_research_snapshot(snapshot, snapshot.observations)
    service = AIResearchService(
        stocks=stocks,
        research=research,
        ai_research=InMemoryAIResearchRepository(),
        gateway=FakeGateway([]),
        options=AIResearchOptions(enabled=False, model_chain=()),
    )
    app = create_app()
    app.dependency_overrides[get_stock_repository] = lambda: stocks
    app.dependency_overrides[get_ai_research_service] = lambda: service
    client = TestClient(app)
    response = client.get("/api/v1/stocks/600519/ai-research")
    assert response.status_code == 200
    assert response.json() == {
        "status": "disabled",
        "reason": "llm_disabled",
        "freshness": None,
        "output": None,
    }
    assert client.get("/api/v1/stocks/999999/ai-research").status_code == 404
