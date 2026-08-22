import hashlib
import json
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_explanations.models import (
    ExplanationContext,
    ExplanationEvidence,
    QuestionKey,
)
from zhaoniu_api.db import ResearchSignalRecord, ResearchSnapshotRecord

SOURCE_KIND: dict[str, Literal["fundamental", "corporate_event", "peer"]] = {
    "research_observation": "fundamental",
    "corporate_event": "corporate_event",
    "peer_position": "peer",
}
QUESTION_SOURCES = {
    "recent_research_changes": frozenset(SOURCE_KIND),
    "fundamental_changes": frozenset({"research_observation"}),
    "corporate_event_context": frozenset({"corporate_event"}),
    "peer_position_context": frozenset({"peer_position"}),
}
ATTENTION_RANK = {"important": 0, "notice": 1, "info": 2}


def evidence_id(signal: ResearchSignalRecord) -> str:
    identity = f"{signal.source_kind}:{signal.id}:{signal.semantic_fingerprint}"
    return f"EV-{hashlib.sha256(identity.encode()).hexdigest()[:12].upper()}"


def context_hash(context: ExplanationContext) -> str:
    payload = context.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def select_signals(rows: list[ResearchSignalRecord]) -> list[ResearchSignalRecord]:
    """Apply stable attention, diversity, time and semantic-dedup selection."""
    rows.sort(
        key=lambda row: (
            ATTENTION_RANK.get(row.attention_level, 9),
            -row.known_at.timestamp(),
            row.dedup_group_key,
            str(row.id),
        )
    )
    candidates: list[ResearchSignalRecord] = []
    seen: set[str] = set()
    for row in rows:
        dedup = f"{row.source_kind}:{row.dedup_group_key}:{row.signal_type}:{row.effective_on}"
        if dedup in seen:
            continue
        seen.add(dedup)
        candidates.append(row)
    selected: list[ResearchSignalRecord] = []
    selected_ids: set[UUID] = set()
    seen_sources: set[str] = set()
    attention_ranks = {ATTENTION_RANK.get(row.attention_level, 9) for row in candidates}
    for attention_rank in sorted(attention_ranks):
        group = [
            row
            for row in candidates
            if ATTENTION_RANK.get(row.attention_level, 9) == attention_rank
        ]
        for row in group:
            if row.source_kind not in seen_sources:
                selected.append(row)
                selected_ids.add(row.id)
                seen_sources.add(row.source_kind)
                if len(selected) == 12:
                    break
        for row in group:
            if row.id not in selected_ids:
                selected.append(row)
                selected_ids.add(row.id)
                if len(selected) == 12:
                    break
        if len(selected) == 12:
            break
    return selected


async def latest_snapshot(session: AsyncSession, symbol: str) -> ResearchSnapshotRecord | None:
    return cast(
        ResearchSnapshotRecord | None,
        await session.scalar(
            select(ResearchSnapshotRecord)
            .where(ResearchSnapshotRecord.symbol == symbol)
            .order_by(
                ResearchSnapshotRecord.knowledge_cutoff.desc(),
                ResearchSnapshotRecord.id.desc(),
            )
            .limit(1)
        ),
    )


async def build_context(
    session: AsyncSession,
    *,
    symbol: str,
    question_key: QuestionKey,
    snapshot_id: UUID,
    knowledge_cutoff: datetime,
) -> ExplanationContext:
    source_kinds = QUESTION_SOURCES[question_key]
    rows = list(
        (
            await session.scalars(
                select(ResearchSignalRecord).where(
                    ResearchSignalRecord.symbol == symbol,
                    ResearchSignalRecord.known_at <= knowledge_cutoff,
                    ResearchSignalRecord.source_kind.in_(source_kinds),
                )
            )
        ).all()
    )
    selected = select_signals(rows)
    facts = [
        ExplanationEvidence(
            evidence_id=evidence_id(row),
            source_kind=SOURCE_KIND[row.source_kind],
            source_id=row.id,
            title=row.title,
            summary=row.summary,
            attention_level=row.attention_level,
            known_at=row.known_at,
        )
        for row in selected
    ]
    return ExplanationContext(
        context_version="research-explanation-context-v1",
        symbol=symbol,
        question_key=question_key,
        snapshot_id=snapshot_id,
        knowledge_cutoff=knowledge_cutoff,
        facts=facts,
    )
