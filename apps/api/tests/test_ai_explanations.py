import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zhaoniu_api.ai_explanations.context import context_hash, evidence_id
from zhaoniu_api.ai_explanations.models import (
    CitedExplanationText,
    ExplanationContext,
    ExplanationEvidence,
    ExplanationInterpretation,
    ExplanationRequestCreate,
    ResearchExplanationV1,
)
from zhaoniu_api.ai_explanations.validation import validate_explanation
from zhaoniu_api.ai_research import litellm_gateway
from zhaoniu_api.ai_research.litellm_gateway import LiteLLMGateway, _error_code
from zhaoniu_api.config import Settings
from zhaoniu_api.db import ResearchSignalRecord


def _signal() -> ResearchSignalRecord:
    return ResearchSignalRecord(
        id=uuid4(),
        symbol="600519.SH",
        source_kind="research_observation",
        signal_family="profitability",
        signal_type="margin_change",
        attention_level="notice",
        known_at=datetime(2026, 8, 1, tzinfo=UTC),
        dedup_group_key="profitability:margin",
        semantic_fingerprint="a" * 64,
        projection_version="v1",
        schema_version="v1",
        projection_mode="historical_backfill",
        alert_eligible=False,
        title="盈利能力变化",
        summary="毛利结构出现变化，需要结合后续披露继续核对。",
        display_payload={},
    )


def _document(text: str, evidence: str) -> ResearchExplanationV1:
    cited = CitedExplanationText(text=text, evidence_refs=[evidence])
    return ResearchExplanationV1(
        schema_version="research-explanation-v1",
        question_key="fundamental_changes",
        headline=cited,
        summary=[cited, cited],
        interpretations=[
            ExplanationInterpretation(focus_key="fundamental", explanation=cited)
        ],
        attention_items=[],
    )


def test_evidence_identity_and_context_hash_are_stable() -> None:
    signal = _signal()
    reference = evidence_id(signal)
    fact = ExplanationEvidence(
        evidence_id=reference,
        source_kind="fundamental",
        source_id=signal.id,
        title=signal.title,
        summary=signal.summary,
        attention_level=signal.attention_level,
        known_at=signal.known_at,
    )
    context = ExplanationContext(
        context_version="research-explanation-context-v1",
        symbol=signal.symbol,
        question_key="fundamental_changes",
        snapshot_id=uuid4(),
        knowledge_cutoff=signal.known_at,
        facts=[fact],
    )
    assert reference.startswith("EV-") and len(reference) == 15
    assert evidence_id(signal) == reference
    assert context_hash(context) == context_hash(context.model_copy(deep=True))


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("利润增长百分之十", "numeric_claim_not_allowed"),
        ("建议买入并设置目标价", "investment_advice_language_not_allowed"),
    ],
)
def test_validation_rejects_numeric_and_advice_language(text: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        validate_explanation(_document(text, "EV-AAAAAAAAAAAA"), {"EV-AAAAAAAAAAAA"})


def test_validation_rejects_unknown_citation() -> None:
    with pytest.raises(ValueError, match="invalid_evidence_reference"):
        validate_explanation(_document("盈利结构出现变化", "EV-UNKNOWN00000"), set())


def test_question_contract_rejects_free_text_and_unknown_key() -> None:
    with pytest.raises(ValidationError):
        ExplanationRequestCreate.model_validate(
            {"question_key": "这只股票值得买吗", "client_request_id": str(uuid4())}
        )


def test_deepseek_production_profile_is_fail_closed() -> None:
    settings = Settings(
        app_env="production",
        auth_cookie_secure=True,
        allowed_origins="https://research.example.com",
        public_base_url="https://research.example.com",
        trusted_hosts="research.example.com",
        database_url="postgresql+asyncpg://db/zhaoniu",
        redis_url="redis://redis/0",
        registration_invite_hmac_secret="x" * 32,
        access_activation_hmac_secret="y" * 32,
        llm_enabled=True,
        ai_explanation_enabled=True,
        deepseek_api_key="test-only-key",
        llm_structured_output_mode="json_object",
        legal_review_status="approved",
        data_use_status="approved",
    )
    settings.validate_runtime_security()
    assert settings.ai_explanation_models == ("deepseek/deepseek-v4-flash",)
    with pytest.raises(ValueError, match="model_not_approved"):
        settings.model_copy(
            update={"ai_explanation_model_chain": "deepseek/deepseek-v3"}
        ).validate_runtime_security()


def test_provider_balance_error_is_classified() -> None:
    class ProviderError(Exception):
        status_code = 402

    assert _error_code(ProviderError("insufficient balance")) == "provider_balance"


@pytest.mark.asyncio
async def test_deepseek_gateway_disables_thinking_and_bounds_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Usage:
        prompt_tokens = 11
        completion_tokens = 17

    class Message:
        content = '{"ok":true}'

    class Choice:
        message = Message()
        finish_reason = "stop"

    class Response:
        choices = [Choice()]
        usage = Usage()
        model = "deepseek-v4-flash"
        _hidden_params: dict[str, object] = {}

    class FakeLiteLLM:
        async def acompletion(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return Response()

    monkeypatch.setattr(litellm_gateway, "_litellm", lambda: FakeLiteLLM())
    response = await LiteLLMGateway("json_object").generate_structured(
        model="deepseek/deepseek-v4-flash",
        task_type="research_explanation",
        system_prompt="return JSON",
        input_data={"fact": "data"},
        response_schema={"type": "object"},
        timeout_seconds=60,
        max_output_tokens=1200,
        thinking_enabled=False,
    )

    assert response.data == {"ok": True}
    assert captured["max_tokens"] == 1200
    assert captured["max_retries"] == 0
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.external
@pytest.mark.asyncio
async def test_real_deepseek_json_object_smoke() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured")
    response = await LiteLLMGateway("json_object").generate_structured(
        model="deepseek/deepseek-v4-flash",
        task_type="research_explanation_external_smoke",
        system_prompt="Return a JSON object with ok set to true. Do not include any other field.",
        input_data={"probe": "structured-output"},
        response_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        timeout_seconds=60,
        max_output_tokens=128,
        thinking_enabled=False,
    )
    assert response.data == {"ok": True}
