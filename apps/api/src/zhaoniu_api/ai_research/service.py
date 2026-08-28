import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from zhaoniu_api.ai_research.context import build_context, digest
from zhaoniu_api.ai_research.litellm_gateway import provider_name
from zhaoniu_api.ai_research.models import (
    AIResearchBuildResult,
    AIResearchEnvelope,
    AIResearchOutputDocument,
    AIResearchReason,
    AIResearchStatus,
    LLMCallAudit,
    StockHealthResearchV1,
)
from zhaoniu_api.ai_research.prompt import (
    MODEL_ROUTE_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_HASH,
    PROMPT_VERSION,
    REPAIR_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from zhaoniu_api.ai_research.validation import (
    AIOutputValidationError,
    validate_repair_preserves_structure,
    validate_stock_health_output,
)
from zhaoniu_api.domain.models import IssuerType, resolve_symbol
from zhaoniu_api.ports.providers import LLMGateway, LLMGatewayError
from zhaoniu_api.ports.repositories import (
    AIResearchRepository,
    ResearchRepository,
    StockRepository,
)


@dataclass(frozen=True, slots=True)
class AIResearchOptions:
    enabled: bool
    model_chain: tuple[str, ...]
    max_attempts: int = 4
    per_model_timeout_seconds: float = 75
    run_deadline_seconds: float = 240
    max_output_tokens: int = 1200
    configuration_revision: int | None = None

    @property
    def active_models(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for configured in self.model_chain:
            model = configured.strip()
            if model and model not in ordered:
                ordered.append(model)
        return tuple(ordered[: self.max_attempts])


class AIResearchService:
    def __init__(
        self,
        *,
        stocks: StockRepository,
        research: ResearchRepository,
        ai_research: AIResearchRepository,
        gateway: LLMGateway,
        options: AIResearchOptions,
        options_resolver: Callable[[], Awaitable[AIResearchOptions]] | None = None,
    ) -> None:
        self._stocks = stocks
        self._research = research
        self._ai_research = ai_research
        self._gateway = gateway
        self._options = options
        self._options_resolver = options_resolver

    async def _refresh_options(self) -> None:
        if self._options_resolver is not None:
            self._options = await self._options_resolver()

    @property
    def generation_enabled(self) -> bool:
        return self._options.enabled and bool(self._options.active_models)

    async def generate_stock_health(
        self, symbol: str, *, retry_failed: bool = False
    ) -> AIResearchBuildResult:
        await self._refresh_options()
        canonical = resolve_symbol(symbol).canonical
        stock = await self._stocks.get(canonical)
        if stock is None:
            raise ValueError("stock not found")
        if stock.issuer_type != IssuerType.GENERAL:
            return AIResearchBuildResult("unsupported", None, None, None)
        snapshot = await self._research.latest_research_snapshot(canonical)
        if snapshot is None:
            return AIResearchBuildResult("not_built", None, None, None)
        if not self.generation_enabled:
            return AIResearchBuildResult("disabled", None, None, None)

        context = build_context(snapshot)
        route_hash = digest(
            [
                MODEL_ROUTE_VERSION,
                self._options.configuration_revision,
                list(self._options.active_models),
            ]
        )
        idempotency_key = digest(
            [
                str(snapshot.id),
                "stock_health",
                context.context_version,
                context.context_hash,
                PROMPT_VERSION,
                PROMPT_HASH,
                OUTPUT_SCHEMA_VERSION,
                MODEL_ROUTE_VERSION,
                route_hash,
            ]
        )
        existing = await self._ai_research.find_output_by_key(idempotency_key)
        if existing is not None:
            return AIResearchBuildResult(
                "skipped",
                existing.run_id,
                existing.output_id,
                idempotency_key,
                existing.provider_display_name,
                existing.model_display_name,
            )

        lease = await self._ai_research.acquire_run(
            canonical_symbol=canonical,
            snapshot_id=snapshot.id,
            idempotency_key=idempotency_key,
            context_version=context.context_version,
            context_hash=context.context_hash,
            prompt_version=PROMPT_VERSION,
            prompt_hash=PROMPT_HASH,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            model_route_version=MODEL_ROUTE_VERSION,
            route_hash=route_hash,
            retry_failed=retry_failed,
        )
        if not lease.acquired:
            return AIResearchBuildResult(
                "skipped" if lease.status == "succeeded" else lease.status,
                lease.run_id,
                None,
                idempotency_key,
            )

        deadline = time.monotonic() + self._options.run_deadline_seconds
        last_error_code = "provider_chain_exhausted"
        last_error_summary = "all configured models failed"
        repairable_validation_codes = {"numeric_claim", "forbidden_language"}
        repair_used = False
        call_index = 0
        try:
            for model in self._options.active_models:
                if time.monotonic() >= deadline:
                    last_error_code = "run_deadline_exceeded"
                    last_error_summary = "AI research run exceeded its deadline"
                    break
                provider = provider_name(model)
                if not self._gateway.supports_structured_output(model):
                    call_index += 1
                    last_error_code = "structured_output_unsupported"
                    last_error_summary = f"{provider} model does not support response schema"
                    await self._record_failure(
                        lease.run_id,
                        call_index,
                        provider,
                        model,
                        last_error_code,
                        0,
                    )
                    continue

                request_prompt = SYSTEM_PROMPT
                request_input = context.model_dump(mode="json")
                repair_source: dict[str, object] | None = None
                while True:
                    call_index += 1
                    started = time.perf_counter()
                    response = None
                    try:
                        timeout_seconds = min(
                            self._options.per_model_timeout_seconds,
                            max(1, deadline - time.monotonic()),
                        )
                        async with asyncio.timeout(timeout_seconds):
                            response = await self._gateway.generate_structured(
                                model=model,
                                task_type="stock_health",
                                system_prompt=request_prompt,
                                input_data=request_input,
                                response_schema=StockHealthResearchV1.model_json_schema(),
                                timeout_seconds=timeout_seconds,
                                max_output_tokens=self._options.max_output_tokens,
                                thinking_enabled=False,
                            )
                        content = validate_stock_health_output(response.data, context)
                        if repair_source is not None:
                            validate_repair_preserves_structure(repair_source, content)
                    except TimeoutError:
                        last_error_code = "provider_timeout"
                        last_error_summary = "provider attempt exceeded its timeout"
                        await self._record_failure(
                            lease.run_id,
                            call_index,
                            provider,
                            model,
                            last_error_code,
                            int((time.perf_counter() - started) * 1000),
                        )
                        break
                    except LLMGatewayError as error:
                        last_error_code = error.code
                        last_error_summary = str(error)[:300]
                        await self._record_failure(
                            lease.run_id,
                            call_index,
                            provider,
                            model,
                            error.code,
                            int((time.perf_counter() - started) * 1000),
                        )
                        break
                    except AIOutputValidationError as error:
                        last_error_code = error.code
                        last_error_summary = str(error)[:300]
                        assert response is not None
                        await self._ai_research.record_call(
                            LLMCallAudit(
                                run_id=lease.run_id,
                                attempt_index=call_index,
                                task_type="stock_health",
                                provider=response.usage.provider,
                                model=response.usage.model,
                                requested_model=response.usage.requested_model,
                                actual_model=response.usage.model,
                                capability_mode=response.usage.capability_mode,
                                input_tokens=response.usage.input_tokens,
                                output_tokens=response.usage.output_tokens,
                                latency_ms=response.usage.latency_ms,
                                cost_microunits=response.usage.cost_microunits,
                                status="rejected",
                                finish_reason=response.finish_reason,
                                error_code=error.code,
                            )
                        )
                        if (
                            not repair_used
                            and error.code in repairable_validation_codes
                            and time.monotonic() < deadline
                        ):
                            repair_used = True
                            repair_source = response.data
                            request_prompt = REPAIR_SYSTEM_PROMPT
                            request_input = {
                                "validation_error": error.code,
                                "allowed_evidence_ids": [
                                    item.evidence_id for item in context.evidence_index
                                ],
                                "invalid_output": response.data,
                            }
                            continue
                        break
                    else:
                        assert response is not None
                        await self._ai_research.record_call(
                            LLMCallAudit(
                                run_id=lease.run_id,
                                attempt_index=call_index,
                                task_type="stock_health",
                                provider=response.usage.provider,
                                model=response.usage.model,
                                requested_model=response.usage.requested_model,
                                actual_model=response.usage.model,
                                capability_mode=response.usage.capability_mode,
                                input_tokens=response.usage.input_tokens,
                                output_tokens=response.usage.output_tokens,
                                latency_ms=response.usage.latency_ms,
                                cost_microunits=response.usage.cost_microunits,
                                status="succeeded",
                                finish_reason=response.finish_reason,
                            )
                        )
                        generated_at = datetime.now(UTC)
                        output = AIResearchOutputDocument(
                            output_id=uuid5(NAMESPACE_URL, f"zhaoniu:ai-output:{idempotency_key}"),
                            run_id=lease.run_id,
                            symbol=canonical,
                            snapshot_id=snapshot.id,
                            knowledge_cutoff=snapshot.knowledge_cutoff,
                            provider_display_name=response.usage.provider,
                            model_display_name=response.usage.model,
                            context_version=context.context_version,
                            context_hash=context.context_hash,
                            prompt_version=PROMPT_VERSION,
                            prompt_hash=PROMPT_HASH,
                            output_schema_version=OUTPUT_SCHEMA_VERSION,
                            model_route_version=MODEL_ROUTE_VERSION,
                            route_hash=route_hash,
                            content=content,
                            evidence_index=context.evidence_index,
                            coverage=context.coverage,
                            generated_at=generated_at,
                        )
                        await self._ai_research.complete_run(
                            output, idempotency_key=idempotency_key
                        )
                        return AIResearchBuildResult(
                            "succeeded",
                            lease.run_id,
                            output.output_id,
                            idempotency_key,
                            output.provider_display_name,
                            output.model_display_name,
                        )

            await self._ai_research.fail_run(
                lease.run_id,
                error_code=last_error_code,
                error_summary=last_error_summary,
                finished_at=datetime.now(UTC),
            )
            return AIResearchBuildResult("failed", lease.run_id, None, idempotency_key)
        except Exception as error:
            await self._ai_research.fail_run(
                lease.run_id,
                error_code="application_error",
                error_summary=type(error).__name__,
                finished_at=datetime.now(UTC),
            )
            raise

    async def get_stock_health(self, symbol: str) -> AIResearchEnvelope:
        await self._refresh_options()
        canonical = resolve_symbol(symbol).canonical
        stock = await self._stocks.get(canonical)
        if stock is None:
            raise ValueError("stock not found")
        snapshot = await self._research.latest_research_snapshot(canonical)
        output = await self._ai_research.latest_output(canonical)
        if output is not None:
            freshness: Literal["current", "stale"] = (
                "current" if snapshot and output.snapshot_id == snapshot.id else "stale"
            )
            return AIResearchEnvelope(
                status=AIResearchStatus.READY,
                freshness=freshness,
                output=output,
            )
        run = await self._ai_research.latest_run(canonical)
        if run and run.status == "running":
            return AIResearchEnvelope(status=AIResearchStatus.BUILDING)
        if run and run.status == "failed":
            return AIResearchEnvelope(
                status=AIResearchStatus.FAILED,
                reason=AIResearchReason.GENERATION_FAILED,
            )
        if stock.issuer_type != IssuerType.GENERAL:
            return AIResearchEnvelope(
                status=AIResearchStatus.UNSUPPORTED,
                reason=AIResearchReason.UNSUPPORTED_ISSUER_TYPE,
            )
        if snapshot is None:
            return AIResearchEnvelope(
                status=AIResearchStatus.NOT_BUILT,
                reason=AIResearchReason.DETERMINISTIC_SNAPSHOT_MISSING,
            )
        if not self.generation_enabled:
            return AIResearchEnvelope(
                status=AIResearchStatus.DISABLED,
                reason=AIResearchReason.LLM_DISABLED,
            )
        return AIResearchEnvelope(status=AIResearchStatus.NOT_BUILT)

    async def _record_failure(
        self,
        run_id: UUID,
        attempt: int,
        provider: str,
        model: str,
        error_code: str,
        latency_ms: int,
    ) -> None:
        await self._ai_research.record_call(
            LLMCallAudit(
                run_id=run_id,
                attempt_index=attempt,
                task_type="stock_health",
                provider=provider,
                model=model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                cost_microunits=None,
                status="failed",
                error_code=error_code,
            )
        )
