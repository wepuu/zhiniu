from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from zhaoniu_api.corporate_events.engine import attention_for, classify_title, extract_candidate
from zhaoniu_api.corporate_events.models import (
    ATTENTION_RULE_VERSION,
    CLASSIFIER_VERSION,
    EXTRACTOR_VERSION,
    RADAR_SCHEMA_VERSION,
    CorporateEventListResponse,
    CorporateEventResponse,
    DisclosureDocument,
    EventBuildResult,
    EventRadarEnvelope,
    EventThreadResponse,
    EventType,
    SourceFact,
)
from zhaoniu_api.corporate_events.normalizer import AKShareDisclosureNormalizer
from zhaoniu_api.corporate_events.provider import AKShareDisclosureProvider
from zhaoniu_api.corporate_events.sql_repository import SQLAlchemyCorporateEventRepository
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.ports.repositories import StockRepository


class CorporateEventService:
    def __init__(
        self,
        *,
        provider: AKShareDisclosureProvider,
        normalizer: AKShareDisclosureNormalizer,
        stocks: StockRepository,
        events: SQLAlchemyCorporateEventRepository,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._stocks = stocks
        self._events = events

    async def sync_disclosures(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> EventBuildResult:
        canonical = await self._known_symbol(symbol)
        final_end = end or date.today()
        final_start = start or final_end - timedelta(days=730)
        key = _hash(("sync-disclosures", self._provider.name, canonical, final_start, final_end))
        if await self._events.has_run(key):
            return EventBuildResult("skipped", canonical, 0, 0, key)
        try:
            raw_documents = await self._provider.get_disclosures(
                canonical.split(".")[0], final_start, final_end
            )
            raw_facts = await self._provider.get_source_facts(canonical.split(".")[0])
        except Exception as exc:
            await self._events.record_run(
                symbol=canonical,
                key=key,
                run_type="disclosure_sync",
                fingerprint=_hash((canonical, final_start, final_end)),
                status="failed",
                source_health="unavailable",
                written=0,
                error=type(exc).__name__,
            )
            raise
        documents = self._normalizer.disclosures(raw_documents)
        facts = self._normalizer.source_facts(raw_facts)
        written = await self._events.upsert_documents(documents)
        written += await self._events.upsert_source_facts(facts)
        await self._events.record_run(
            symbol=canonical,
            key=key,
            run_type="disclosure_sync",
            fingerprint=_hash([item.content_fingerprint for item in documents]),
            status="succeeded",
            source_health=self._provider.last_source_health,
            written=written,
        )
        return EventBuildResult("succeeded", canonical, len(documents) + len(facts), written, key)

    async def build_corporate_events(self, symbol: str) -> EventBuildResult:
        canonical = await self._known_symbol(symbol)
        documents = await self._events.documents(canonical)
        facts = await self._events.source_facts(canonical)
        fingerprint = _hash(
            {
                "documents": [item.content_fingerprint for item in documents],
                "facts": [item.source_fact_id for item in facts],
                "classifier": CLASSIFIER_VERSION,
                "extractor": EXTRACTOR_VERSION,
            }
        )
        key = _hash(("build-corporate-events", canonical, fingerprint))
        if await self._events.has_run(key):
            return EventBuildResult("skipped", canonical, len(documents), 0, key)
        candidates = []
        for document in documents:
            classification = classify_title(document.title)
            await self._events.save_classification(
                document.id,
                family=classification.event_family.value if classification.event_family else None,
                event_type=classification.event_type.value if classification.event_type else None,
                status=classification.status,
                version=CLASSIFIER_VERSION,
                matched_rule=classification.matched_rule,
            )
            matching_fact = _match_fact(
                document,
                facts,
                classification.event_family.value if classification.event_family else None,
            )
            candidate = extract_candidate(document, classification, matching_fact)
            if candidate:
                candidates.append(candidate)
        written = await self._events.save_events(candidates)
        await self._events.record_run(
            symbol=canonical,
            key=key,
            run_type="event_build",
            fingerprint=fingerprint,
            status="succeeded",
            source_health=await self._events.latest_source_health(canonical),
            written=written,
        )
        return EventBuildResult("succeeded", canonical, len(documents), written, key)

    async def build_event_radar(
        self, symbol: str, *, as_of: datetime | None = None
    ) -> EventBuildResult:
        canonical = await self._known_symbol(symbol)
        cutoff = as_of or datetime.now(UTC)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        events = [
            item for item in await self._events.latest_events(canonical) if item.known_at <= cutoff
        ]
        fingerprint = _hash([item.event_version_fingerprint for item in events])
        key = _hash(
            ("event-radar", canonical, fingerprint, ATTENTION_RULE_VERSION, RADAR_SCHEMA_VERSION)
        )
        if await self._events.has_run(key):
            return EventBuildResult("skipped", canonical, len(events), 0, key)
        items = []
        for event in sorted(events, key=lambda row: (row.known_at, row.id.hex), reverse=True):
            level, rule_id, reason = attention_for(EventType(event.event_type))
            section = (
                "upcoming"
                if event.event_effective_from and event.event_effective_from > cutoff.date()
                else "recent"
            )
            items.append((event.id, section, level, rule_id, reason))
        coverage = (
            "partial"
            if any(item.extraction_status != "complete" for item in events)
            else "complete"
        )
        source_health = await self._events.latest_source_health(canonical)
        await self._events.save_radar(
            symbol=canonical,
            key=key,
            fingerprint=fingerprint,
            cutoff=cutoff,
            source_health=source_health,
            coverage_status=coverage,
            items=items,
        )
        await self._events.record_run(
            symbol=canonical,
            key=key,
            run_type="radar_build",
            fingerprint=fingerprint,
            status="succeeded",
            source_health=source_health,
            written=len(items),
        )
        return EventBuildResult("succeeded", canonical, len(events), len(items), key)

    async def build_event_research(self, symbol: str) -> EventBuildResult:
        await self.build_corporate_events(symbol)
        return await self.build_event_radar(symbol)

    async def list_events(self, symbol: str, *, limit: int = 100) -> CorporateEventListResponse:
        canonical = await self._known_symbol(symbol)
        return await self._events.list_response(canonical, limit=limit)

    async def get_event(self, symbol: str, event_id: UUID) -> CorporateEventResponse | None:
        canonical = await self._known_symbol(symbol)
        return await self._events.detail_response(canonical, event_id)

    async def get_event_thread(self, symbol: str, event_id: UUID) -> EventThreadResponse | None:
        canonical = await self._known_symbol(symbol)
        return await self._events.thread_response(canonical, event_id)

    async def get_radar(self, symbol: str) -> EventRadarEnvelope:
        canonical = await self._known_symbol(symbol)
        return await self._events.radar_response(canonical)

    async def _known_symbol(self, symbol: str) -> str:
        canonical = resolve_symbol(symbol).canonical
        if await self._stocks.get(canonical) is None:
            raise ValueError(f"stock not found: {canonical}")
        return canonical


def _match_fact(
    document: DisclosureDocument,
    facts: list[SourceFact],
    family: str | None,
) -> SourceFact | None:
    if not family:
        return None
    identity_keys = (
        "source_document_id",
        "document_id",
        "announcement_id",
        "公告ID",
        "公告编号",
    )
    for fact in facts:
        if fact.event_family.value != family:
            continue
        identities = {
            str(fact.raw_payload[key]).strip()
            for key in identity_keys
            if fact.raw_payload.get(key) not in (None, "")
        }
        if document.source_document_id in identities:
            return fact
    return None


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()
