from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.corporate_events.models import (
    ATTENTION_RULE_VERSION,
    RADAR_SCHEMA_VERSION,
    CorporateEventListResponse,
    CorporateEventResponse,
    DisclosureDocument,
    EventCandidate,
    EventFamily,
    EventRadarEnvelope,
    EventRadarItemResponse,
    EventSourceResponse,
    EventType,
    SourceFact,
)
from zhaoniu_api.db import (
    CorporateEventBuildRunRecord,
    CorporateEventInputRecord,
    CorporateEventRecord,
    CorporateEventSourceFactRecord,
    DisclosureClassificationRecord,
    DisclosureDocumentRecord,
    EventRadarSnapshotItemRecord,
    EventRadarSnapshotRecord,
)


class SQLAlchemyCorporateEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_documents(self, documents: list[DisclosureDocument]) -> int:
        written = 0
        for item in documents:
            statement = (
                insert(DisclosureDocumentRecord)
                .values(
                    id=item.id,
                    symbol=item.symbol,
                    source_owner=item.source_owner,
                    source_document_id=item.source_document_id,
                    title=item.title,
                    source_url=item.source_url,
                    source_published_at=item.source_published_at,
                    source_published_precision=item.source_published_precision,
                    known_at=item.known_at,
                    ingested_at=item.ingested_at,
                    content_fingerprint=item.content_fingerprint,
                )
                .on_conflict_do_nothing(constraint="uq_disclosure_source_identity")
                .returning(DisclosureDocumentRecord.id)
            )
            inserted = (await self._session.execute(statement)).scalar_one_or_none()
            written += int(inserted is not None)
        await self._session.commit()
        return written

    async def upsert_source_facts(self, facts: list[SourceFact]) -> int:
        written = 0
        for item in facts:
            result = await self._session.execute(
                insert(CorporateEventSourceFactRecord)
                .values(
                    id=item.id,
                    symbol=item.symbol,
                    source_owner=item.source_owner,
                    source_fact_id=item.source_fact_id,
                    event_family=item.event_family.value,
                    raw_payload=item.raw_payload,
                    source_published_at=item.source_published_at,
                    known_at=item.known_at,
                    ingested_at=item.ingested_at,
                    match_status="staged",
                )
                .on_conflict_do_nothing(constraint="uq_corporate_event_source_fact")
                .returning(CorporateEventSourceFactRecord.id)
            )
            written += int(result.scalar_one_or_none() is not None)
        await self._session.commit()
        return written

    async def documents(self, symbol: str) -> list[DisclosureDocument]:
        rows = (
            await self._session.execute(
                select(DisclosureDocumentRecord)
                .where(DisclosureDocumentRecord.symbol == symbol)
                .order_by(DisclosureDocumentRecord.source_published_at)
            )
        ).scalars()
        return [
            DisclosureDocument(
                id=row.id,
                symbol=row.symbol,
                source_owner=row.source_owner,
                source_document_id=row.source_document_id,
                title=row.title,
                source_url=row.source_url,
                source_published_at=row.source_published_at,
                source_published_precision=row.source_published_precision,
                known_at=row.known_at,
                ingested_at=row.ingested_at,
                content_fingerprint=row.content_fingerprint,
            )
            for row in rows
        ]

    async def source_facts(self, symbol: str) -> list[SourceFact]:
        rows = (
            await self._session.execute(
                select(CorporateEventSourceFactRecord).where(
                    CorporateEventSourceFactRecord.symbol == symbol
                )
            )
        ).scalars()
        return [
            SourceFact(
                id=row.id,
                symbol=row.symbol,
                source_owner=row.source_owner,
                source_fact_id=row.source_fact_id,
                event_family=EventFamily(row.event_family),
                raw_payload=row.raw_payload,
                source_published_at=row.source_published_at,
                known_at=row.known_at,
                ingested_at=row.ingested_at,
            )
            for row in rows
        ]

    async def save_classification(
        self,
        document_id: UUID,
        *,
        family: str | None,
        event_type: str | None,
        status: str,
        version: str,
        matched_rule: str | None,
    ) -> None:
        await self._session.execute(
            insert(DisclosureClassificationRecord)
            .values(
                document_id=document_id,
                event_family=family,
                event_type=event_type,
                status=status,
                classifier_version=version,
                matched_rule=matched_rule,
                classified_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                constraint="uq_disclosure_classification",
                set_={
                    "event_family": family,
                    "event_type": event_type,
                    "status": status,
                    "matched_rule": matched_rule,
                    "classified_at": datetime.now(UTC),
                },
            )
        )

    async def save_events(self, candidates: list[EventCandidate]) -> int:
        written = 0
        for item in candidates:
            previous_id = (
                await self._session.execute(
                    select(CorporateEventRecord.id)
                    .where(CorporateEventRecord.event_thread_key == item.event_thread_key)
                    .order_by(CorporateEventRecord.known_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            event_id = (
                await self._session.execute(
                    insert(CorporateEventRecord)
                    .values(
                        symbol=item.symbol,
                        event_family=item.event_family.value,
                        event_type=item.event_type.value,
                        title=item.title,
                        event_thread_key=item.event_thread_key,
                        event_version_fingerprint=item.event_version_fingerprint,
                        identity_basis=item.identity_basis,
                        previous_event_id=previous_id,
                        source_published_at=item.source_published_at,
                        source_published_precision=item.source_published_precision,
                        known_at=item.known_at,
                        event_effective_from=item.event_effective_from,
                        event_effective_to=item.event_effective_to,
                        event_time_precision=item.event_time_precision,
                        extraction_status=item.extraction_status,
                        typed_payload=item.typed_payload,
                        field_lineage=item.field_lineage,
                    )
                    .on_conflict_do_nothing(constraint="uq_corporate_event_version")
                    .returning(CorporateEventRecord.id)
                )
            ).scalar_one_or_none()
            if event_id is None:
                continue
            await self._session.execute(
                insert(CorporateEventInputRecord).values(
                    event_id=event_id,
                    document_id=item.document_id,
                    source_fact_id=item.source_fact_id,
                    role="primary",
                )
            )
            if item.source_fact_id:
                await self._session.execute(
                    update(CorporateEventSourceFactRecord)
                    .where(CorporateEventSourceFactRecord.id == item.source_fact_id)
                    .values(matched_document_id=item.document_id, match_status="matched")
                )
            written += 1
        await self._session.commit()
        return written

    async def has_run(self, key: str) -> bool:
        return (
            await self._session.execute(
                select(CorporateEventBuildRunRecord.id).where(
                    CorporateEventBuildRunRecord.idempotency_key == key,
                    CorporateEventBuildRunRecord.status == "succeeded",
                )
            )
        ).scalar_one_or_none() is not None

    async def record_run(
        self,
        *,
        symbol: str,
        key: str,
        run_type: str,
        fingerprint: str,
        status: str,
        source_health: str,
        written: int,
        error: str | None = None,
    ) -> None:
        await self._session.execute(
            insert(CorporateEventBuildRunRecord)
            .values(
                symbol=symbol,
                idempotency_key=key,
                run_type=run_type,
                status=status,
                source_health=source_health,
                input_fingerprint=fingerprint,
                written_count=written,
                error_summary=error,
                finished_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                constraint="uq_corporate_event_build_run",
                set_={
                    "status": status,
                    "source_health": source_health,
                    "written_count": written,
                    "error_summary": error,
                    "finished_at": datetime.now(UTC),
                },
            )
        )
        await self._session.commit()

    async def latest_source_health(self, symbol: str) -> str:
        value = (
            await self._session.execute(
                select(CorporateEventBuildRunRecord.source_health)
                .where(
                    CorporateEventBuildRunRecord.symbol == symbol,
                    CorporateEventBuildRunRecord.run_type == "disclosure_sync",
                )
                .order_by(CorporateEventBuildRunRecord.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return value or "unavailable"

    async def latest_events(self, symbol: str) -> list[CorporateEventRecord]:
        rows = (
            await self._session.execute(
                select(CorporateEventRecord)
                .where(CorporateEventRecord.symbol == symbol)
                .order_by(CorporateEventRecord.known_at.desc())
            )
        ).scalars()
        latest: dict[str, CorporateEventRecord] = {}
        for row in rows:
            latest.setdefault(row.event_thread_key, row)
        return list(latest.values())

    async def save_radar(
        self,
        *,
        symbol: str,
        key: str,
        fingerprint: str,
        cutoff: datetime,
        source_health: str,
        coverage_status: str,
        items: list[tuple[UUID, str, str, str, str]],
    ) -> UUID:
        existing = (
            await self._session.execute(
                select(EventRadarSnapshotRecord.id).where(
                    EventRadarSnapshotRecord.idempotency_key == key
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        snapshot_id = (
            await self._session.execute(
                insert(EventRadarSnapshotRecord)
                .values(
                    symbol=symbol,
                    idempotency_key=key,
                    knowledge_cutoff=cutoff,
                    input_fingerprint=fingerprint,
                    rule_version=ATTENTION_RULE_VERSION,
                    schema_version=RADAR_SCHEMA_VERSION,
                    source_health=source_health,
                    coverage_status=coverage_status,
                    generated_at=datetime.now(UTC),
                )
                .returning(EventRadarSnapshotRecord.id)
            )
        ).scalar_one()
        for ordinal, (event_id, section, level, rule_id, reason) in enumerate(items):
            await self._session.execute(
                insert(EventRadarSnapshotItemRecord).values(
                    snapshot_id=snapshot_id,
                    event_id=event_id,
                    section=section,
                    attention_level=level,
                    attention_rule_id=rule_id,
                    attention_rule_version=ATTENTION_RULE_VERSION,
                    attention_reason=reason,
                    ordinal=ordinal,
                )
            )
        await self._session.commit()
        return snapshot_id

    async def list_response(self, symbol: str, *, limit: int = 100) -> CorporateEventListResponse:
        rows = (await self.latest_events(symbol))[:limit]
        items = [await self._event_response(row) for row in rows]
        return CorporateEventListResponse(
            symbol=symbol.split(".")[0], canonical_symbol=symbol, items=items, total=len(items)
        )

    async def detail_response(self, symbol: str, event_id: UUID) -> CorporateEventResponse | None:
        row = (
            await self._session.execute(
                select(CorporateEventRecord).where(
                    CorporateEventRecord.id == event_id,
                    CorporateEventRecord.symbol == symbol,
                )
            )
        ).scalar_one_or_none()
        return await self._event_response(row) if row else None

    async def radar_response(self, symbol: str) -> EventRadarEnvelope:
        snapshot = (
            await self._session.execute(
                select(EventRadarSnapshotRecord)
                .where(EventRadarSnapshotRecord.symbol == symbol)
                .order_by(EventRadarSnapshotRecord.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snapshot is None:
            run = (
                await self._session.execute(
                    select(CorporateEventBuildRunRecord.status)
                    .where(CorporateEventBuildRunRecord.symbol == symbol)
                    .order_by(CorporateEventBuildRunRecord.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            status: Literal["not_built", "building", "failed"] = (
                "building" if run == "running" else "failed" if run == "failed" else "not_built"
            )
            return EventRadarEnvelope(
                status=status,
                coverage_status="unknown",
                symbol=symbol.split(".")[0],
                canonical_symbol=symbol,
            )
        rows = (
            await self._session.execute(
                select(EventRadarSnapshotItemRecord, CorporateEventRecord)
                .join(
                    CorporateEventRecord,
                    CorporateEventRecord.id == EventRadarSnapshotItemRecord.event_id,
                )
                .where(EventRadarSnapshotItemRecord.snapshot_id == snapshot.id)
                .order_by(EventRadarSnapshotItemRecord.ordinal)
            )
        ).all()
        recent: list[EventRadarItemResponse] = []
        upcoming: list[EventRadarItemResponse] = []
        for item, event in rows:
            response = EventRadarItemResponse(
                event=await self._event_response(event),
                section=item.section,
                attention_level=item.attention_level,
                attention_rule_id=item.attention_rule_id,
                attention_rule_version=item.attention_rule_version,
                attention_reason=item.attention_reason,
            )
            (upcoming if item.section == "upcoming" else recent).append(response)
        latest_known = await self._session.scalar(
            select(func.max(CorporateEventRecord.known_at)).where(
                CorporateEventRecord.symbol == symbol
            )
        )
        freshness: Literal["current", "stale"] = (
            "stale" if latest_known and latest_known > snapshot.knowledge_cutoff else "current"
        )
        return EventRadarEnvelope(
            status="ready" if rows else "no_events",
            freshness=freshness,
            source_health=cast(
                Literal["healthy", "degraded", "unavailable"], snapshot.source_health
            ),
            coverage_status=cast(
                Literal["complete", "partial", "unknown"], snapshot.coverage_status
            ),
            symbol=symbol.split(".")[0],
            canonical_symbol=symbol,
            snapshot_id=snapshot.id,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            generated_at=snapshot.generated_at,
            recent_items=recent,
            upcoming_items=upcoming,
        )

    async def _event_response(self, row: CorporateEventRecord) -> CorporateEventResponse:
        sources = (
            await self._session.execute(
                select(DisclosureDocumentRecord)
                .join(
                    CorporateEventInputRecord,
                    CorporateEventInputRecord.document_id == DisclosureDocumentRecord.id,
                )
                .where(CorporateEventInputRecord.event_id == row.id)
            )
        ).scalars()
        return CorporateEventResponse(
            id=row.id,
            symbol=row.symbol.split(".")[0],
            canonical_symbol=row.symbol,
            event_family=EventFamily(row.event_family),
            event_type=EventType(row.event_type),
            title=row.title,
            event_thread_key=row.event_thread_key,
            identity_basis=row.identity_basis,
            previous_event_id=row.previous_event_id,
            source_published_at=row.source_published_at,
            known_at=row.known_at,
            event_effective_from=row.event_effective_from,
            event_effective_to=row.event_effective_to,
            event_time_precision=row.event_time_precision,
            extraction_status=cast(
                Literal["complete", "partial", "invalid"], row.extraction_status
            ),
            typed_payload=row.typed_payload,
            field_lineage=row.field_lineage,
            sources=[
                EventSourceResponse(
                    document_id=source.id,
                    source_owner=source.source_owner,
                    source_document_id=source.source_document_id,
                    title=source.title,
                    source_url=source.source_url,
                    source_published_at=source.source_published_at,
                    source_published_precision=source.source_published_precision,
                )
                for source in sources
            ],
        )
