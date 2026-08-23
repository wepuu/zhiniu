import hashlib
import json
import time
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.service import AccessControlService
from zhaoniu_api.ai_explanations.context import (
    QUESTION_SOURCES,
    build_context,
    context_hash,
    latest_snapshot,
)
from zhaoniu_api.ai_explanations.models import (
    ExplanationOutput,
    ExplanationQuestion,
    ExplanationQuestionCatalog,
    ExplanationRequestResponse,
    QuestionKey,
    ResearchExplanationV1,
)
from zhaoniu_api.ai_explanations.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from zhaoniu_api.ai_explanations.validation import validate_explanation
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    AIExplanationDailyUsageRecord,
    AIExplanationRequestRecord,
    AIResearchOutputRecord,
    AIResearchRunRecord,
    LLMCallRecord,
    ResearchSignalRecord,
    StockRecord,
)
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.ports.providers import LLMGatewayError, LLMUsage
from zhaoniu_api.provider_configuration.gateway import ManagedLiteLLMGateway
from zhaoniu_api.provider_configuration.models import (
    DeepSeekConfiguration,
    DeepSeekRouteConfiguration,
)
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService

RESEARCH_TYPE = "stock_explanation"
SCHEMA_VERSION = "research-explanation-v1"
ROUTE_VERSION = "deepseek-production-v1"
QUESTION_COPY: dict[QuestionKey, tuple[str, str]] = {
    "recent_research_changes": (
        "最近有哪些研究变化？",
        "综合基本面、公司事件与同行位置的最新证据。",
    ),
    "fundamental_changes": ("基本面发生了什么变化？", "只解释确定性财务研究观察。"),
    "corporate_event_context": ("近期公司事件意味着什么？", "基于已保留公告证据解释事件背景。"),
    "peer_position_context": ("同行位置应如何理解？", "基于可比口径解释同行位置，不作排名。"),
}


class ExplanationServiceError(ValueError):
    pass


def _digest(value: object) -> str:
    raw = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class AIExplanationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._access = AccessControlService(session, settings)
        self._gateway = ManagedLiteLLMGateway(session, settings)

    async def _managed_route(self) -> tuple[DeepSeekRouteConfiguration, int | None]:
        runtime = await ProviderConfigurationService(self._session, self._settings).runtime(
            "deepseek"
        )
        configuration = DeepSeekConfiguration.model_validate(runtime.configuration)
        route = configuration.research_assistant
        if not configuration.enabled:
            route = route.model_copy(update={"enabled": False})
        return route, runtime.revision

    async def question_catalog(self, user_id: UUID, symbol: str) -> ExplanationQuestionCatalog:
        canonical = await self._stock_symbol(symbol)
        entitlements = await self._access.effective_entitlements(user_id)
        allowed = entitlements.features.get("ai_research_explanation", False)
        daily_limit = entitlements.limits.get("ai_explanations_daily", 0)
        used = await self._used_today(user_id)
        route, _revision = await self._managed_route()
        globally_enabled = route.enabled
        access: Literal["available", "contact_support", "disabled"] = (
            "disabled" if not globally_enabled else ("available" if allowed else "contact_support")
        )
        snapshot = await latest_snapshot(self._session, canonical)
        questions: list[ExplanationQuestion] = []
        for key, (label, description) in QUESTION_COPY.items():
            count = 0
            if snapshot is not None:
                count = int(
                    await self._session.scalar(
                        select(func.count())
                        .select_from(ResearchSignalRecord)
                        .where(
                            ResearchSignalRecord.symbol == canonical,
                            ResearchSignalRecord.source_kind.in_(QUESTION_SOURCES[key]),
                        )
                    )
                    or 0
                )
            questions.append(
                ExplanationQuestion(
                    key=key,
                    label=label,
                    description=description,
                    coverage="available" if count else "insufficient",
                )
            )
        return ExplanationQuestionCatalog(
            symbol=canonical,
            enabled=access == "available",
            access=access,
            remaining_today=max(0, daily_limit - used),
            daily_limit=daily_limit,
            support_contact_url=self._settings.support_contact_url or None,
            questions=questions,
        )

    async def create_request(
        self, user_id: UUID, symbol: str, question_key: QuestionKey, client_request_id: UUID
    ) -> tuple[ExplanationRequestResponse, bool]:
        canonical = await self._stock_symbol(symbol)
        existing = await self._session.scalar(
            select(AIExplanationRequestRecord).where(
                AIExplanationRequestRecord.user_id == user_id,
                AIExplanationRequestRecord.client_request_id == client_request_id,
            )
        )
        if existing is not None:
            return await self._response(existing), False
        await self._require_access(user_id)
        snapshot = await latest_snapshot(self._session, canonical)
        if snapshot is None:
            raise ExplanationServiceError("deterministic_snapshot_missing")
        count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(ResearchSignalRecord)
                .where(
                    ResearchSignalRecord.symbol == canonical,
                    ResearchSignalRecord.source_kind.in_(QUESTION_SOURCES[question_key]),
                )
            )
            or 0
        )
        if not count:
            raise ExplanationServiceError("insufficient_evidence")
        await self._consume_quota(user_id)
        now = datetime.now(UTC)
        row = AIExplanationRequestRecord(
            id=uuid4(),
            user_id=user_id,
            symbol=canonical,
            question_key=question_key,
            client_request_id=client_request_id,
            status="pending",
            quota_day=now.date(),
            knowledge_cutoff=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return await self._response(row), True

    async def get_request(self, user_id: UUID, request_id: UUID) -> ExplanationRequestResponse:
        row = await self._session.scalar(
            select(AIExplanationRequestRecord).where(
                AIExplanationRequestRecord.id == request_id,
                AIExplanationRequestRecord.user_id == user_id,
            )
        )
        if row is None:
            raise LookupError("explanation_request_not_found")
        return await self._response(row)

    async def mark_dispatch_failed(self, user_id: UUID, request_id: UUID) -> None:
        await self._session.execute(
            update(AIExplanationRequestRecord)
            .where(
                AIExplanationRequestRecord.id == request_id,
                AIExplanationRequestRecord.user_id == user_id,
                AIExplanationRequestRecord.status == "pending",
            )
            .values(
                status="failed",
                error_code="dispatch_temporarily_unavailable",
                finished_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    async def retry(self, user_id: UUID, request_id: UUID) -> ExplanationRequestResponse:
        row = await self._session.scalar(
            select(AIExplanationRequestRecord)
            .where(
                AIExplanationRequestRecord.id == request_id,
                AIExplanationRequestRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if row is None:
            raise LookupError("explanation_request_not_found")
        if row.status != "failed":
            raise ExplanationServiceError("request_not_failed")
        await self._require_access(user_id)
        await self._consume_quota(user_id)
        row.status = "pending"
        row.error_code = None
        row.finished_at = None
        row.knowledge_cutoff = datetime.now(UTC)
        await self._session.commit()
        return await self._response(row)

    async def execute(self, request_id: UUID) -> ExplanationRequestResponse:
        request = await self._session.get(AIExplanationRequestRecord, request_id)
        if request is None:
            raise LookupError("explanation_request_not_found")
        if request.status == "ready":
            return await self._response(request)
        request.status = "building"
        await self._session.commit()
        snapshot = await latest_snapshot(self._session, request.symbol)
        if snapshot is None:
            return await self._fail_request(request, "deterministic_snapshot_missing")
        try:
            context = await build_context(
                self._session,
                symbol=request.symbol,
                question_key=cast(QuestionKey, request.question_key),
                snapshot_id=snapshot.id,
                knowledge_cutoff=request.knowledge_cutoff,
            )
        except ValueError:
            return await self._fail_request(request, "insufficient_evidence")
        c_hash = context_hash(context)
        prompt_hash = _digest(f"{PROMPT_VERSION}:{SYSTEM_PROMPT}")
        managed_route, configuration_revision = await self._managed_route()
        route = list(managed_route.models)
        route_hash = _digest([configuration_revision, route])
        idempotency_key = _digest(
            {
                "snapshot_id": str(snapshot.id),
                "question_key": request.question_key,
                "context_hash": c_hash,
                "prompt_hash": prompt_hash,
                "schema": SCHEMA_VERSION,
                "route": route_hash,
            }
        )
        run, acquired = await self._acquire_run(
            request=request,
            snapshot_id=snapshot.id,
            idempotency_key=idempotency_key,
            context_hash_value=c_hash,
            prompt_hash=prompt_hash,
            route_hash=route_hash,
        )
        request.run_id = run.id
        await self._session.commit()
        if run.status == "succeeded":
            output = await self._session.scalar(
                select(AIResearchOutputRecord).where(AIResearchOutputRecord.run_id == run.id)
            )
            if output is not None:
                await self._mark_ready(run.id, output.id)
                return await self.get_request(request.user_id, request.id)
        if run.status == "running" and not acquired:
            return await self._response(request)
        model = route[0]
        started = time.perf_counter()
        try:
            response = await self._gateway.generate_structured(
                model=model,
                task_type="research_explanation",
                system_prompt=SYSTEM_PROMPT,
                input_data=context.model_dump(mode="json"),
                response_schema=ResearchExplanationV1.model_json_schema(),
                timeout_seconds=managed_route.timeout_seconds,
                max_output_tokens=managed_route.max_output_tokens,
                thinking_enabled=False,
            )
            document = ResearchExplanationV1.model_validate(response.data)
            if document.question_key != request.question_key:
                raise ValueError("question_key_mismatch")
            validate_explanation(document, {fact.evidence_id for fact in context.facts})
            await self._record_call(run.id, response.usage, response.finish_reason or "stop", 1)
        except LLMGatewayError as error:
            await self._record_failed_call(run.id, model, error.code, started)
            await self._fail_run(run.id, error.code)
            return await self.get_request(request.user_id, request.id)
        except (ValueError, TypeError):
            await self._record_failed_call(run.id, model, "validation_failed", started)
            await self._fail_run(run.id, "validation_failed")
            return await self.get_request(request.user_id, request.id)
        now = datetime.now(UTC)
        output_id = uuid4()
        self._session.add(
            AIResearchOutputRecord(
                id=output_id,
                run_id=run.id,
                symbol=request.symbol,
                snapshot_id=snapshot.id,
                idempotency_key=idempotency_key,
                research_type=RESEARCH_TYPE,
                question_key=request.question_key,
                provider=response.usage.provider,
                model=response.usage.model,
                context_version=context.context_version,
                context_hash=c_hash,
                prompt_version=PROMPT_VERSION,
                prompt_hash=prompt_hash,
                output_schema_version=SCHEMA_VERSION,
                model_route_version=ROUTE_VERSION,
                route_hash=route_hash,
                structured_result=document.model_dump(mode="json"),
                evidence_manifest={
                    "items": [fact.model_dump(mode="json") for fact in context.facts]
                },
                coverage_manifest={"question_key": request.question_key},
                knowledge_cutoff=request.knowledge_cutoff,
                generated_at=now,
            )
        )
        run.status = "succeeded"
        run.finished_at = now
        await self._session.commit()
        await self._mark_ready(run.id, output_id)
        return await self.get_request(request.user_id, request.id)

    async def _stock_symbol(self, symbol: str) -> str:
        canonical = resolve_symbol(symbol).canonical
        if await self._session.get(StockRecord, canonical) is None:
            raise LookupError("stock_not_found")
        return canonical

    async def _require_access(self, user_id: UUID) -> None:
        route, _revision = await self._managed_route()
        if not route.enabled:
            raise ExplanationServiceError("ai_explanation_disabled")
        entitlements = await self._access.effective_entitlements(user_id)
        if not entitlements.features.get("ai_research_explanation", False):
            raise ExplanationServiceError("advanced_access_required")

    async def _used_today(self, user_id: UUID) -> int:
        return int(
            await self._session.scalar(
                select(AIExplanationDailyUsageRecord.used_count).where(
                    AIExplanationDailyUsageRecord.user_id == user_id,
                    AIExplanationDailyUsageRecord.quota_day == date.today(),
                )
            )
            or 0
        )

    async def _consume_quota(self, user_id: UUID) -> None:
        entitlements = await self._access.effective_entitlements(user_id)
        limit = entitlements.limits.get("ai_explanations_daily", 0)
        today = datetime.now(UTC).date()
        statement = (
            insert(AIExplanationDailyUsageRecord)
            .values(id=uuid4(), user_id=user_id, quota_day=today, used_count=1)
            .on_conflict_do_update(
                constraint="uq_ai_explanation_usage_day",
                set_={
                    "used_count": AIExplanationDailyUsageRecord.used_count + 1,
                    "updated_at": datetime.now(UTC),
                },
                where=AIExplanationDailyUsageRecord.used_count < limit,
            )
            .returning(AIExplanationDailyUsageRecord.used_count)
        )
        used = await self._session.scalar(statement)
        if used is None or used > limit or limit <= 0:
            await self._session.rollback()
            raise ExplanationServiceError("daily_limit_reached")

    async def _acquire_run(
        self,
        *,
        request: AIExplanationRequestRecord,
        snapshot_id: UUID,
        idempotency_key: str,
        context_hash_value: str,
        prompt_hash: str,
        route_hash: str,
    ) -> tuple[AIResearchRunRecord, bool]:
        now = datetime.now(UTC)
        run_id = uuid4()
        inserted = await self._session.scalar(
            insert(AIResearchRunRecord)
            .values(
                id=run_id,
                symbol=request.symbol,
                snapshot_id=snapshot_id,
                idempotency_key=idempotency_key,
                research_type=RESEARCH_TYPE,
                question_key=request.question_key,
                status="running",
                context_version="research-explanation-context-v1",
                context_hash=context_hash_value,
                prompt_version=PROMPT_VERSION,
                prompt_hash=prompt_hash,
                output_schema_version=SCHEMA_VERSION,
                model_route_version=ROUTE_VERSION,
                route_hash=route_hash,
                current_attempt=0,
                retry_count=0,
                started_at=now,
                lease_expires_at=now + timedelta(minutes=30),
            )
            .on_conflict_do_nothing(constraint="uq_ai_research_run_idempotency")
            .returning(AIResearchRunRecord.id)
        )
        await self._session.commit()
        run = await self._session.scalar(
            select(AIResearchRunRecord).where(
                AIResearchRunRecord.idempotency_key == idempotency_key
            )
        )
        if run is None:
            raise RuntimeError("ai_explanation_run_missing")
        if run.status == "running" and run.lease_expires_at < now:
            run.current_attempt = 0
            run.error_code = None
            run.error_summary = None
            run.started_at = now
            run.finished_at = None
            run.lease_expires_at = now + timedelta(minutes=30)
            await self._session.commit()
            return run, True
        if run.status == "failed" and request.run_id == run.id:
            run.status = "running"
            run.retry_count += 1
            run.error_code = None
            run.error_summary = None
            run.started_at = now
            run.finished_at = None
            run.lease_expires_at = now + timedelta(minutes=30)
            await self._session.commit()
            return run, True
        return run, inserted is not None

    async def _record_call(
        self, run_id: UUID, usage: LLMUsage, finish_reason: str, attempt: int
    ) -> None:
        self._session.add(
            LLMCallRecord(
                id=uuid4(),
                ai_run_id=run_id,
                attempt_index=attempt,
                task_type="research_explanation",
                provider=usage.provider,
                model=usage.model,
                requested_model=usage.requested_model,
                actual_model=usage.model,
                capability_mode=usage.capability_mode,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=usage.latency_ms,
                cost_microunits=usage.cost_microunits,
                status="succeeded",
                finish_reason=finish_reason,
            )
        )
        await self._session.commit()

    async def _record_failed_call(
        self, run_id: UUID, model: str, code: str, started: float
    ) -> None:
        self._session.add(
            LLMCallRecord(
                id=uuid4(),
                ai_run_id=run_id,
                attempt_index=1,
                task_type="research_explanation",
                provider="DeepSeek",
                model=model,
                requested_model=model,
                actual_model=None,
                capability_mode="json_object",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
                cost_microunits=None,
                status="failed",
                error_code=code,
            )
        )
        await self._session.commit()

    async def _fail_run(self, run_id: UUID, code: str) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(AIResearchRunRecord)
            .where(AIResearchRunRecord.id == run_id)
            .values(
                status="failed",
                error_code=code,
                error_summary="generation unavailable",
                finished_at=now,
            )
        )
        await self._session.execute(
            update(AIExplanationRequestRecord)
            .where(AIExplanationRequestRecord.run_id == run_id)
            .values(
                status="failed", error_code="generation_temporarily_unavailable", finished_at=now
            )
        )
        await self._session.commit()

    async def _fail_request(
        self, row: AIExplanationRequestRecord, code: str
    ) -> ExplanationRequestResponse:
        row.status = "failed"
        row.error_code = code
        row.finished_at = datetime.now(UTC)
        await self._session.commit()
        return await self._response(row)

    async def _mark_ready(self, run_id: UUID, output_id: UUID) -> None:
        await self._session.execute(
            update(AIExplanationRequestRecord)
            .where(AIExplanationRequestRecord.run_id == run_id)
            .values(
                status="ready", output_id=output_id, error_code=None, finished_at=datetime.now(UTC)
            )
        )
        await self._session.commit()

    async def _response(self, row: AIExplanationRequestRecord) -> ExplanationRequestResponse:
        output = None
        if row.output_id:
            output_row = await self._session.get(AIResearchOutputRecord, row.output_id)
            if output_row:
                latest_known = await self._session.scalar(
                    select(func.max(ResearchSignalRecord.known_at)).where(
                        ResearchSignalRecord.symbol == row.symbol,
                        ResearchSignalRecord.source_kind.in_(QUESTION_SOURCES[row.question_key]),
                    )
                )
                output = ExplanationOutput(
                    output_id=output_row.id,
                    run_id=output_row.run_id,
                    symbol=output_row.symbol,
                    question_key=cast(QuestionKey, output_row.question_key),
                    provider_display_name=output_row.provider,
                    model_display_name=output_row.model,
                    knowledge_cutoff=output_row.knowledge_cutoff,
                    generated_at=output_row.generated_at,
                    freshness="stale"
                    if latest_known and latest_known > output_row.knowledge_cutoff
                    else "current",
                    content=ResearchExplanationV1.model_validate(output_row.structured_result),
                    evidence_index=output_row.evidence_manifest.get("items", []),
                    limitations=["仅解释已保留的确定性研究证据。", "内容不构成投资建议。"],
                )
        return ExplanationRequestResponse(
            id=row.id,
            symbol=row.symbol,
            question_key=cast(QuestionKey, row.question_key),
            status=cast(Literal["pending", "building", "ready", "failed"], row.status),
            error_code=row.error_code,
            created_at=row.created_at,
            finished_at=row.finished_at,
            output=output,
        )
