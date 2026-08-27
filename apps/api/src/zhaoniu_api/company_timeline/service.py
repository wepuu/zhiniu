from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.company_timeline.models import (
    CompanyTimelineCoverage,
    CompanyTimelineEnvelope,
    CompanyTimelineItem,
    CompanyTimelineSummary,
    EventThreadSummary,
    TimelineDisplayValue,
    TimelineSourceArtifact,
    TimelineUpcomingEvent,
)
from zhaoniu_api.db import (
    CorporateEventRecord,
    EventRadarSnapshotItemRecord,
    EventRadarSnapshotRecord,
    PeerPositionObservationRecord,
    ResearchSignalRecord,
    ResearchSnapshotRecord,
    StockRecord,
)
from zhaoniu_api.domain.models import resolve_symbol

ATTENTION_RANK = {"info": 1, "notice": 2, "important": 3}


def _filter_hash(source_kind: str | None, minimum_attention: str | None) -> str:
    return sha256(f"{source_kind or 'all'}|{minimum_attention or 'all'}".encode()).hexdigest()


def _latest_signal_ids(*conditions: Any) -> Any:
    ranked = (
        select(
            ResearchSignalRecord.id.label("signal_id"),
            func.row_number()
            .over(
                partition_by=(
                    ResearchSignalRecord.symbol,
                    ResearchSignalRecord.source_kind,
                    ResearchSignalRecord.dedup_group_key,
                ),
                order_by=(
                    ResearchSignalRecord.known_at.desc(),
                    ResearchSignalRecord.id.desc(),
                ),
            )
            .label("dedup_rank"),
        )
        .where(*conditions)
        .subquery()
    )
    return select(ranked.c.signal_id).where(ranked.c.dedup_rank == 1)


def _encode_cursor(cutoff: datetime, row: ResearchSignalRecord, filter_hash: str) -> str:
    payload = {
        "query_cutoff": cutoff.isoformat(),
        "known_at": row.known_at.isoformat(),
        "id": str(row.id),
        "filter_hash": filter_hash,
    }
    return (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _decode_cursor(value: str) -> dict[str, str]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
        return {str(key): str(item) for key, item in payload.items()}
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_cursor") from exc


class CompanyTimelineQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        symbol: str,
        *,
        source_kind: str | None,
        minimum_attention: str | None,
        limit: int,
        cursor: str | None,
    ) -> CompanyTimelineEnvelope:
        canonical = resolve_symbol(symbol).canonical
        if await self._session.get(StockRecord, canonical) is None:
            raise ValueError("stock_not_found")
        filter_hash = _filter_hash(source_kind, minimum_attention)
        cutoff = datetime.now(UTC)
        cursor_known: datetime | None = None
        cursor_id: UUID | None = None
        if cursor:
            decoded = _decode_cursor(cursor)
            if decoded.get("filter_hash") != filter_hash:
                raise ValueError("cursor_filter_mismatch")
            try:
                cutoff = datetime.fromisoformat(decoded["query_cutoff"])
                cursor_known = datetime.fromisoformat(decoded["known_at"])
                cursor_id = UUID(decoded["id"])
            except (KeyError, ValueError) as exc:
                raise ValueError("invalid_cursor") from exc

        base_conditions: list[Any] = [
            ResearchSignalRecord.symbol == canonical,
            ResearchSignalRecord.known_at <= cutoff,
        ]
        if source_kind:
            base_conditions.append(ResearchSignalRecord.source_kind == source_kind)
        conditions: list[Any] = [ResearchSignalRecord.id.in_(_latest_signal_ids(*base_conditions))]
        if minimum_attention:
            rank = ATTENTION_RANK[minimum_attention]
            conditions.append(
                ResearchSignalRecord.attention_level.in_(
                    [name for name, value in ATTENTION_RANK.items() if value >= rank]
                )
            )
        if cursor_known is not None and cursor_id is not None:
            conditions.append(
                or_(
                    ResearchSignalRecord.known_at < cursor_known,
                    and_(
                        ResearchSignalRecord.known_at == cursor_known,
                        ResearchSignalRecord.id < cursor_id,
                    ),
                )
            )
        rows = (
            await self._session.scalars(
                select(ResearchSignalRecord)
                .where(*conditions)
                .order_by(ResearchSignalRecord.known_at.desc(), ResearchSignalRecord.id.desc())
                .limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        page = list(rows[:limit])
        coverage = await self._coverage(canonical)
        upcoming = await self._upcoming(canonical, cutoff)
        summary = await self._summary(canonical, cutoff, len(upcoming))
        items = await self._hydrate(page)
        ready_count = sum(value == "ready" for value in coverage.model_dump().values())
        if items:
            status = "ready" if ready_count == 3 else "partial"
        elif ready_count == 0:
            status = "not_built"
        elif ready_count == 3:
            status = "empty"
        else:
            status = "partial"
        latest_known = await self._session.scalar(
            select(func.max(ResearchSignalRecord.known_at)).where(
                ResearchSignalRecord.symbol == canonical,
                ResearchSignalRecord.known_at <= cutoff,
            )
        )
        return CompanyTimelineEnvelope(
            status=cast(Any, status),
            symbol=canonical.split(".")[0],
            canonical_symbol=canonical,
            query_cutoff=cutoff,
            latest_known_at=latest_known,
            summary=summary,
            items=items,
            upcoming_events=upcoming,
            coverage=coverage,
            next_cursor=(
                _encode_cursor(cutoff, page[-1], filter_hash) if has_more and page else None
            ),
        )

    async def _coverage(self, symbol: str) -> CompanyTimelineCoverage:
        fundamental = await self._session.scalar(
            select(ResearchSnapshotRecord.id)
            .where(ResearchSnapshotRecord.symbol == symbol)
            .limit(1)
        )
        peer = await self._session.scalar(
            select(PeerPositionObservationRecord.id)
            .where(PeerPositionObservationRecord.symbol == symbol)
            .limit(1)
        )
        event = await self._session.scalar(
            select(EventRadarSnapshotRecord.id)
            .where(EventRadarSnapshotRecord.symbol == symbol)
            .limit(1)
        )
        return CompanyTimelineCoverage(
            fundamental="ready" if fundamental else "not_built",
            peer="ready" if peer else "not_built",
            corporate_event="ready" if event else "not_built",
        )

    async def _summary(
        self, symbol: str, cutoff: datetime, upcoming_count: int
    ) -> CompanyTimelineSummary:
        latest_ids = _latest_signal_ids(
            ResearchSignalRecord.symbol == symbol,
            ResearchSignalRecord.known_at <= cutoff,
        )
        row = (
            await self._session.execute(
                select(
                    func.count(ResearchSignalRecord.id),
                    func.sum(case((ResearchSignalRecord.source_kind == "fundamental", 1), else_=0)),
                    func.sum(case((ResearchSignalRecord.source_kind == "peer", 1), else_=0)),
                    func.sum(
                        case((ResearchSignalRecord.source_kind == "corporate_event", 1), else_=0)
                    ),
                    func.sum(
                        case((ResearchSignalRecord.attention_level == "important", 1), else_=0)
                    ),
                ).where(
                    ResearchSignalRecord.id.in_(latest_ids),
                    ResearchSignalRecord.known_at >= cutoff - timedelta(days=30),
                )
            )
        ).one()
        values = [int(value or 0) for value in row]
        return CompanyTimelineSummary(
            recent_30d_total=values[0],
            fundamental_count=values[1],
            peer_count=values[2],
            corporate_event_count=values[3],
            important_count=values[4],
            upcoming_count=upcoming_count,
        )

    async def _upcoming(self, symbol: str, cutoff: datetime) -> list[TimelineUpcomingEvent]:
        latest = await self._session.scalar(
            select(EventRadarSnapshotRecord)
            .where(
                EventRadarSnapshotRecord.symbol == symbol,
                EventRadarSnapshotRecord.knowledge_cutoff <= cutoff,
            )
            .order_by(EventRadarSnapshotRecord.knowledge_cutoff.desc())
            .limit(1)
        )
        if latest is None:
            return []
        rows = (
            await self._session.execute(
                select(CorporateEventRecord, EventRadarSnapshotItemRecord)
                .join(
                    EventRadarSnapshotItemRecord,
                    EventRadarSnapshotItemRecord.event_id == CorporateEventRecord.id,
                )
                .where(
                    EventRadarSnapshotItemRecord.snapshot_id == latest.id,
                    EventRadarSnapshotItemRecord.section == "upcoming",
                    CorporateEventRecord.event_effective_from.is_not(None),
                )
                .order_by(CorporateEventRecord.event_effective_from.asc())
                .limit(5)
            )
        ).all()
        return [
            TimelineUpcomingEvent(
                event_id=event.id,
                title=event.title,
                event_family=event.event_family,
                attention_level=cast(Any, item.attention_level),
                known_at=event.known_at,
                effective_on=cast(Any, event.event_effective_from),
            )
            for event, item in rows
        ]

    async def _hydrate(self, rows: list[ResearchSignalRecord]) -> list[CompanyTimelineItem]:
        event_ids = [row.corporate_event_id for row in rows if row.corporate_event_id]
        event_rows = (
            (
                await self._session.scalars(
                    select(CorporateEventRecord).where(CorporateEventRecord.id.in_(event_ids))
                )
            ).all()
            if event_ids
            else []
        )
        threads = {row.event_thread_key for row in event_rows}
        thread_rows = (
            (
                await self._session.execute(
                    select(
                        CorporateEventRecord.event_thread_key,
                        CorporateEventRecord.id,
                        func.row_number().over(
                            partition_by=CorporateEventRecord.event_thread_key,
                            order_by=(
                                CorporateEventRecord.known_at.asc(),
                                CorporateEventRecord.id.asc(),
                            ),
                        ),
                        func.count().over(partition_by=CorporateEventRecord.event_thread_key),
                    ).where(CorporateEventRecord.event_thread_key.in_(threads))
                )
            ).all()
            if threads
            else []
        )
        thread_meta = {
            event_id: (thread_key, int(index), int(total))
            for thread_key, event_id, index, total in thread_rows
        }
        items: list[CompanyTimelineItem] = []
        for row in rows:
            source_id = (
                row.research_observation_id
                or row.peer_position_observation_id
                or row.corporate_event_id
            )
            if source_id is None:
                continue
            evidence_path = {
                "fundamental": f"/api/v1/stocks/{row.symbol}/research/observations/{source_id}",
                "peer": f"/api/v1/stocks/{row.symbol}/peer-comparisons",
                "corporate_event": f"/api/v1/stocks/{row.symbol}/events/{source_id}",
            }[row.source_kind]
            display_values = [
                TimelineDisplayValue(label=str(key).replace("_", " "), value=str(value))
                for key, value in row.display_payload.items()
                if value is not None and not isinstance(value, (dict, list))
            ][:3]
            meta = thread_meta.get(source_id)
            items.append(
                CompanyTimelineItem(
                    id=row.id,
                    symbol=row.symbol.split(".")[0],
                    source_kind=cast(Any, row.source_kind),
                    signal_family=row.signal_family,
                    signal_type=row.signal_type,
                    attention_level=cast(Any, row.attention_level),
                    known_at=row.known_at,
                    effective_on=row.effective_on,
                    title=row.title,
                    summary=row.summary,
                    display_values=display_values,
                    source_artifact=TimelineSourceArtifact(
                        type=cast(Any, row.source_kind), id=source_id, evidence_path=evidence_path
                    ),
                    event_thread=(
                        EventThreadSummary(
                            thread_key=meta[0], current_index=meta[1], version_count=meta[2]
                        )
                        if meta
                        else None
                    ),
                )
            )
        return items
