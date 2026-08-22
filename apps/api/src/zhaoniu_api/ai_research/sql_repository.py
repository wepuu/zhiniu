from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_research.models import (
    AIResearchOutputDocument,
    AIResearchRunLease,
    AIResearchRunView,
    LLMCallAudit,
    StockHealthResearchV1,
)
from zhaoniu_api.db import AIResearchOutputRecord, AIResearchRunRecord, LLMCallRecord


class SQLAlchemyAIResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _output(row: AIResearchOutputRecord) -> AIResearchOutputDocument:
        return AIResearchOutputDocument(
            output_id=row.id,
            run_id=row.run_id,
            symbol=row.symbol,
            snapshot_id=row.snapshot_id,
            knowledge_cutoff=row.knowledge_cutoff,
            provider_display_name=row.provider,
            model_display_name=row.model,
            context_version=row.context_version,
            context_hash=row.context_hash,
            prompt_version=row.prompt_version,
            prompt_hash=row.prompt_hash,
            output_schema_version=row.output_schema_version,
            model_route_version=row.model_route_version,
            route_hash=row.route_hash,
            content=StockHealthResearchV1.model_validate(row.structured_result),
            evidence_index=row.evidence_manifest.get("items", []),
            coverage=row.coverage_manifest.get("items", []),
            generated_at=row.generated_at,
        )

    async def find_output_by_key(self, idempotency_key: str) -> AIResearchOutputDocument | None:
        row = await self._session.scalar(
            select(AIResearchOutputRecord).where(
                AIResearchOutputRecord.idempotency_key == idempotency_key
            )
        )
        return self._output(row) if row else None

    async def latest_output(self, canonical_symbol: str) -> AIResearchOutputDocument | None:
        row = await self._session.scalar(
            select(AIResearchOutputRecord)
            .where(
                AIResearchOutputRecord.symbol == canonical_symbol,
                AIResearchOutputRecord.research_type == "stock_health",
            )
            .order_by(AIResearchOutputRecord.generated_at.desc())
            .limit(1)
        )
        return self._output(row) if row else None

    async def latest_run(self, canonical_symbol: str) -> AIResearchRunView | None:
        row = await self._session.scalar(
            select(AIResearchRunRecord)
            .where(
                AIResearchRunRecord.symbol == canonical_symbol,
                AIResearchRunRecord.research_type == "stock_health",
            )
            .order_by(AIResearchRunRecord.started_at.desc())
            .limit(1)
        )
        return (
            AIResearchRunView(row.id, row.status, row.snapshot_id, row.error_code) if row else None
        )

    async def acquire_run(
        self,
        *,
        canonical_symbol: str,
        snapshot_id: UUID,
        idempotency_key: str,
        context_version: str,
        context_hash: str,
        prompt_version: str,
        prompt_hash: str,
        output_schema_version: str,
        model_route_version: str,
        route_hash: str,
        retry_failed: bool,
    ) -> AIResearchRunLease:
        now = datetime.now(UTC)
        run_id = uuid4()
        values = {
            "id": run_id,
            "symbol": canonical_symbol,
            "snapshot_id": snapshot_id,
            "idempotency_key": idempotency_key,
            "research_type": "stock_health",
            "status": "running",
            "context_version": context_version,
            "context_hash": context_hash,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "output_schema_version": output_schema_version,
            "model_route_version": model_route_version,
            "route_hash": route_hash,
            "lease_expires_at": now + timedelta(minutes=30),
        }
        try:
            inserted = await self._session.scalar(
                insert(AIResearchRunRecord)
                .values(**values)
                .on_conflict_do_nothing(constraint="uq_ai_research_run_idempotency")
                .returning(AIResearchRunRecord.id)
            )
            if inserted is not None:
                await self._session.commit()
                return AIResearchRunLease(inserted, True, "running")
            row = await self._session.scalar(
                select(AIResearchRunRecord).where(
                    AIResearchRunRecord.idempotency_key == idempotency_key
                )
            )
            if row is None:
                raise RuntimeError("AI research run disappeared")
            can_reacquire = (row.status == "failed" and retry_failed) or (
                row.status == "running" and row.lease_expires_at < now
            )
            if can_reacquire:
                reacquired = await self._session.scalar(
                    update(AIResearchRunRecord)
                    .where(
                        AIResearchRunRecord.id == row.id,
                        or_(
                            AIResearchRunRecord.status == "failed",
                            and_(
                                AIResearchRunRecord.status == "running",
                                AIResearchRunRecord.lease_expires_at < now,
                            ),
                        ),
                    )
                    .values(
                        status="running",
                        current_attempt=0,
                        retry_count=row.retry_count + (1 if row.status == "failed" else 0),
                        error_code=None,
                        error_summary=None,
                        started_at=now,
                        lease_expires_at=now + timedelta(minutes=30),
                        finished_at=None,
                    )
                    .returning(AIResearchRunRecord.id)
                )
                await self._session.commit()
                if reacquired is not None:
                    return AIResearchRunLease(reacquired, True, "running")
            existing_id = row.id
            existing_status = row.status
            await self._session.rollback()
            return AIResearchRunLease(existing_id, False, existing_status)
        except Exception:
            await self._session.rollback()
            raise

    async def record_call(self, audit: LLMCallAudit) -> None:
        try:
            await self._session.execute(
                insert(LLMCallRecord).values(
                    id=uuid4(),
                    ai_run_id=audit.run_id,
                    attempt_index=audit.attempt_index,
                    task_type=audit.task_type,
                    provider=audit.provider,
                    model=audit.model,
                    requested_model=audit.requested_model,
                    actual_model=audit.actual_model,
                    capability_mode=audit.capability_mode,
                    input_tokens=audit.input_tokens,
                    output_tokens=audit.output_tokens,
                    latency_ms=audit.latency_ms,
                    cost_microunits=audit.cost_microunits,
                    status=audit.status,
                    finish_reason=audit.finish_reason,
                    error_code=audit.error_code,
                )
            )
            await self._session.execute(
                update(AIResearchRunRecord)
                .where(AIResearchRunRecord.id == audit.run_id)
                .values(current_attempt=audit.attempt_index)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def complete_run(self, output: AIResearchOutputDocument, *, idempotency_key: str) -> None:
        try:
            await self._session.execute(
                insert(AIResearchOutputRecord)
                .values(
                    id=output.output_id,
                    run_id=output.run_id,
                    symbol=output.symbol,
                    snapshot_id=output.snapshot_id,
                    idempotency_key=idempotency_key,
                    research_type=output.research_type,
                    provider=output.provider_display_name,
                    model=output.model_display_name,
                    context_version=output.context_version,
                    context_hash=output.context_hash,
                    prompt_version=output.prompt_version,
                    prompt_hash=output.prompt_hash,
                    output_schema_version=output.output_schema_version,
                    model_route_version=output.model_route_version,
                    route_hash=output.route_hash,
                    structured_result=output.content.model_dump(mode="json"),
                    evidence_manifest={
                        "items": [item.model_dump(mode="json") for item in output.evidence_index]
                    },
                    coverage_manifest={
                        "items": [item.model_dump(mode="json") for item in output.coverage]
                    },
                    knowledge_cutoff=output.knowledge_cutoff,
                    generated_at=output.generated_at,
                )
                .on_conflict_do_nothing(constraint="uq_ai_research_output_idempotency")
            )
            await self._session.execute(
                update(AIResearchRunRecord)
                .where(AIResearchRunRecord.id == output.run_id)
                .values(
                    status="succeeded",
                    error_code=None,
                    error_summary=None,
                    finished_at=output.generated_at,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def fail_run(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_summary: str,
        finished_at: datetime,
    ) -> None:
        try:
            await self._session.execute(
                update(AIResearchRunRecord)
                .where(AIResearchRunRecord.id == run_id)
                .values(
                    status="failed",
                    error_code=error_code,
                    error_summary=error_summary[:500],
                    finished_at=finished_at,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
