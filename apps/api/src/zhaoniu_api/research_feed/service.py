from __future__ import annotations

import base64
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    AIResearchOutputRecord,
    CompanyPeerMetricPositionRecord,
    CorporateEventRecord,
    EventRadarSnapshotItemRecord,
    EventRadarSnapshotRecord,
    PeerBenchmarkSnapshotRecord,
    PeerPositionObservationRecord,
    ResearchAlertDispatchRunRecord,
    ResearchObservationRecord,
    ResearchSignalProjectionRunRecord,
    ResearchSignalRecord,
    ResearchSnapshotRecord,
    StockRecord,
    UserResearchAlertDeliveryRecord,
    UserResearchAlertSettingsRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.research_feed.models import (
    AlertDeliveryResponse,
    AlertListResponse,
    AlertSettingsResponse,
    AlertSettingsUpdate,
    AlertSummaryResponse,
    DispatchResult,
    FeedSection,
    FeedSignalResponse,
    ProjectionResult,
    ResearchFeedResponse,
    SourceCoverage,
    WatchlistCoverageItem,
    WatchlistCoverageResponse,
)

PROJECTION_VERSION = "research-signal-v1"
SIGNAL_SCHEMA_VERSION = "research-signal-schema-v1"
PEER_RULE_VERSION = "peer-position-band-v1"
MATCHER_VERSION = "watchlist-alert-v1"
ATTENTION_RANK = {"info": 1, "notice": 2, "important": 3}


def should_deliver_alert(
    *,
    signal_known_at: datetime,
    membership_added_at: datetime,
    signal_attention: str,
    minimum_attention: str,
    enabled: bool,
    source_enabled: bool,
) -> bool:
    """Pure deterministic matcher; historical signals are intentionally never backfilled."""
    return (
        enabled
        and source_enabled
        and membership_added_at < signal_known_at
        and ATTENTION_RANK[signal_attention] >= ATTENTION_RANK[minimum_attention]
    )


def _hash(*parts: object) -> str:
    return sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _encode_cursor(cutoff: datetime, row: ResearchSignalRecord, filter_key: str) -> str:
    payload = {
        "cutoff": cutoff.isoformat(),
        "known_at": row.known_at.isoformat(),
        "attention": row.attention_level,
        "id": str(row.id),
        "filter": filter_key,
    }
    return (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _decode_cursor(value: str) -> dict[str, str]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError
        return {str(key): str(item) for key, item in result.items()}
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_cursor") from exc


class ResearchFeedService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def project_symbol(self, symbol: str) -> ProjectionResult:
        canonical = resolve_symbol(symbol).canonical
        peer_count = await self._build_peer_observations(canonical)
        ids: list[UUID] = []
        ids.extend(await self._project_fundamental(canonical))
        ids.extend(await self._project_peer(canonical))
        ids.extend(await self._project_events(canonical))
        await self._session.commit()
        return ProjectionResult(
            status="succeeded" if ids or peer_count else "skipped",
            projected_signal_ids=ids,
            peer_observation_count=peer_count,
        )

    async def _build_peer_observations(self, symbol: str) -> int:
        rows = (
            await self._session.execute(
                select(CompanyPeerMetricPositionRecord, PeerBenchmarkSnapshotRecord)
                .join(
                    PeerBenchmarkSnapshotRecord,
                    PeerBenchmarkSnapshotRecord.id
                    == CompanyPeerMetricPositionRecord.benchmark_snapshot_id,
                )
                .where(
                    CompanyPeerMetricPositionRecord.symbol == symbol,
                    CompanyPeerMetricPositionRecord.status == "available",
                    CompanyPeerMetricPositionRecord.numeric_percentile.is_not(None),
                )
                .order_by(
                    CompanyPeerMetricPositionRecord.metric_code,
                    PeerBenchmarkSnapshotRecord.knowledge_cutoff,
                )
            )
        ).all()
        previous: dict[str, str] = {}
        written = 0
        for position, snapshot in rows:
            percentile = float(position.numeric_percentile or 0)
            band = "low" if percentile < 20 else "high" if percentile >= 80 else "middle"
            prior = previous.get(position.metric_code)
            previous[position.metric_code] = band
            if prior is None and band == "middle":
                continue
            if prior == band:
                continue
            observation_type = "peer_band_baseline" if prior is None else "peer_band_changed"
            attention = "info" if prior is None else "notice"
            band_label = {"low": "较低", "middle": "中间", "high": "较高"}[band]
            fingerprint = _hash(position.id, observation_type, band, PEER_RULE_VERSION)
            if await self._session.scalar(
                select(PeerPositionObservationRecord.id).where(
                    PeerPositionObservationRecord.content_fingerprint == fingerprint
                )
            ):
                continue
            self._session.add(
                PeerPositionObservationRecord(
                    id=uuid4(),
                    symbol=symbol,
                    company_peer_metric_position_id=position.id,
                    observation_family=position.metric_code,
                    observation_type=observation_type,
                    attention_level=attention,
                    title=f"{position.metric_code}处于同行{band_label}分位区间",
                    summary="该位置仅描述可比口径下的数值分布，不代表投资质量或排名结论。",
                    known_at=snapshot.knowledge_cutoff,
                    rule_id="peer_position_band",
                    rule_version=PEER_RULE_VERSION,
                    observation_key=_hash(symbol, position.metric_code)[:64],
                    content_fingerprint=fingerprint,
                    detail_payload={
                        "metric_code": position.metric_code,
                        "band": band,
                        "percentile": str(position.numeric_percentile),
                        "sample_size": position.sample_size,
                    },
                )
            )
            written += 1
        if written:
            await self._session.flush()
        return written

    async def _project_fundamental(self, symbol: str) -> list[UUID]:
        rows = (
            await self._session.execute(
                select(ResearchObservationRecord, ResearchSnapshotRecord)
                .join(
                    ResearchSnapshotRecord,
                    ResearchSnapshotRecord.id == ResearchObservationRecord.snapshot_id,
                )
                .where(ResearchObservationRecord.symbol == symbol)
            )
        ).all()
        return await self._project_rows(
            "fundamental",
            rows,
            lambda pair: pair[0].content_fingerprint,
            lambda pair: dict(
                source_id=pair[0].id,
                symbol=pair[0].symbol,
                family=pair[0].observation_family,
                signal_type=pair[0].observation_type,
                attention=pair[0].attention_level,
                known_at=pair[1].knowledge_cutoff,
                effective_on=pair[0].current_period,
                dedup=pair[0].observation_key,
                title=pair[0].title,
                summary=pair[0].summary,
                payload={"dimension": pair[0].dimension, "movement": pair[0].movement},
            ),
        )

    async def _project_peer(self, symbol: str) -> list[UUID]:
        rows = (
            await self._session.scalars(
                select(PeerPositionObservationRecord).where(
                    PeerPositionObservationRecord.symbol == symbol
                )
            )
        ).all()
        return await self._project_rows(
            "peer",
            rows,
            lambda row: row.content_fingerprint,
            lambda row: dict(
                source_id=row.id,
                symbol=row.symbol,
                family=row.observation_family,
                signal_type=row.observation_type,
                attention=row.attention_level,
                known_at=row.known_at,
                effective_on=None,
                dedup=row.observation_key,
                title=row.title,
                summary=row.summary,
                payload=row.detail_payload,
            ),
        )

    async def _project_events(self, symbol: str) -> list[UUID]:
        latest = await self._session.scalar(
            select(EventRadarSnapshotRecord)
            .where(EventRadarSnapshotRecord.symbol == symbol)
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
                .where(EventRadarSnapshotItemRecord.snapshot_id == latest.id)
            )
        ).all()
        return await self._project_rows(
            "corporate_event",
            rows,
            lambda pair: pair[0].event_version_fingerprint,
            lambda pair: dict(
                source_id=pair[0].id,
                symbol=pair[0].symbol,
                family=pair[0].event_family,
                signal_type=pair[0].event_type,
                attention=pair[1].attention_level,
                known_at=pair[0].known_at,
                effective_on=pair[0].event_effective_from,
                dedup=pair[0].event_thread_key,
                title=pair[0].title,
                summary=pair[1].attention_reason,
                payload={"section": pair[1].section, "attention_reason": pair[1].attention_reason},
            ),
        )

    async def _project_rows(
        self,
        kind: str,
        rows: Sequence[Any],
        fingerprint: Callable[[Any], str],
        adapt: Callable[[Any], dict[str, Any]],
    ) -> list[UUID]:
        written: list[UUID] = []
        for source in rows:
            semantic = fingerprint(source)
            if await self._session.scalar(
                select(ResearchSignalRecord.id).where(
                    ResearchSignalRecord.source_kind == kind,
                    ResearchSignalRecord.semantic_fingerprint == semantic,
                )
            ):
                continue
            data = adapt(source)
            signal_id = uuid4()
            foreign = {
                "research_observation_id": None,
                "peer_position_observation_id": None,
                "corporate_event_id": None,
            }
            foreign[
                {
                    "fundamental": "research_observation_id",
                    "peer": "peer_position_observation_id",
                    "corporate_event": "corporate_event_id",
                }[kind]
            ] = data["source_id"]
            self._session.add(
                ResearchSignalRecord(
                    id=signal_id,
                    symbol=data["symbol"],
                    source_kind=kind,
                    **foreign,
                    signal_family=data["family"],
                    signal_type=data["signal_type"],
                    attention_level=data["attention"],
                    known_at=data["known_at"],
                    effective_on=data["effective_on"],
                    dedup_group_key=data["dedup"],
                    semantic_fingerprint=semantic,
                    projection_version=PROJECTION_VERSION,
                    schema_version=SIGNAL_SCHEMA_VERSION,
                    title=data["title"],
                    summary=data["summary"],
                    display_payload=data["payload"],
                )
            )
            self._session.add(
                ResearchSignalProjectionRunRecord(
                    id=uuid4(),
                    source_kind=kind,
                    source_artifact_identity=str(data["source_id"]),
                    projection_version=PROJECTION_VERSION,
                    status="succeeded",
                    projected_count=1,
                    finished_at=datetime.now(UTC),
                )
            )
            written.append(signal_id)
        if written:
            await self._session.flush()
        return written

    async def feed(
        self,
        user_id: UUID,
        *,
        cursor: str | None,
        limit: int,
        source_kind: str | None,
        minimum_attention: str | None,
    ) -> ResearchFeedResponse:
        cutoff = datetime.now(UTC)
        cursor_payload = _decode_cursor(cursor) if cursor else None
        filter_key = _hash(source_kind or "all", minimum_attention or "all")
        if cursor_payload:
            if cursor_payload.get("filter") != filter_key:
                raise ValueError("cursor_filter_mismatch")
            cutoff = datetime.fromisoformat(cursor_payload["cutoff"])
        memberships = (
            select(WatchlistItemRecord.symbol)
            .join(WatchlistRecord)
            .where(WatchlistRecord.user_id == user_id)
        )
        conditions = [
            ResearchSignalRecord.symbol.in_(memberships),
            ResearchSignalRecord.known_at <= cutoff,
            ResearchSignalRecord.known_at >= cutoff - timedelta(days=14),
        ]
        if source_kind:
            conditions.append(ResearchSignalRecord.source_kind == source_kind)
        latest_signal = (
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
                        ResearchSignalRecord.id.asc(),
                    ),
                )
                .label("dedup_rank"),
            )
            .where(*conditions)
            .subquery()
        )
        conditions = [
            ResearchSignalRecord.id.in_(
                select(latest_signal.c.signal_id).where(latest_signal.c.dedup_rank == 1)
            )
        ]
        if minimum_attention:
            conditions.append(
                case(ATTENTION_RANK, value=ResearchSignalRecord.attention_level)
                >= ATTENTION_RANK[minimum_attention]
            )
        if cursor_payload:
            known = datetime.fromisoformat(cursor_payload["known_at"])
            rank = ATTENTION_RANK[cursor_payload["attention"]]
            last_id = UUID(cursor_payload["id"])
            rank_expr = case(ATTENTION_RANK, value=ResearchSignalRecord.attention_level)
            conditions.append(
                or_(
                    ResearchSignalRecord.known_at < known,
                    and_(ResearchSignalRecord.known_at == known, rank_expr < rank),
                    and_(
                        ResearchSignalRecord.known_at == known,
                        rank_expr == rank,
                        ResearchSignalRecord.id > last_id,
                    ),
                )
            )
        rank_expr = case(ATTENTION_RANK, value=ResearchSignalRecord.attention_level)
        rows = (
            await self._session.scalars(
                select(ResearchSignalRecord)
                .where(*conditions)
                .order_by(
                    ResearchSignalRecord.known_at.desc(),
                    rank_expr.desc(),
                    ResearchSignalRecord.id.asc(),
                )
                .limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        rendered = await self._render_signals(rows)
        china_tz = ZoneInfo("Asia/Shanghai")
        today_date = cutoff.astimezone(china_tz).date()
        today_items = [
            item for item in rendered if item.known_at.astimezone(china_tz).date() == today_date
        ]
        recent_items = [
            item for item in rendered if item.known_at.astimezone(china_tz).date() != today_date
        ]
        return ResearchFeedResponse(
            query_cutoff=cutoff,
            today=FeedSection(items=today_items, total=len(today_items)),
            recent=FeedSection(items=recent_items, total=len(recent_items)),
            next_cursor=_encode_cursor(cutoff, rows[-1], filter_key) if has_more and rows else None,
        )

    async def _render_signals(
        self, rows: Sequence[ResearchSignalRecord]
    ) -> list[FeedSignalResponse]:
        if not rows:
            return []
        symbols = {row.symbol for row in rows}
        name_rows = (
            await self._session.execute(
                select(StockRecord.symbol, StockRecord.name).where(StockRecord.symbol.in_(symbols))
            )
        ).all()
        names: dict[str, str] = {symbol: name for symbol, name in name_rows}
        ai_symbols = set(
            (
                await self._session.scalars(
                    select(AIResearchOutputRecord.symbol)
                    .where(AIResearchOutputRecord.symbol.in_(symbols))
                    .distinct()
                )
            ).all()
        )
        return [
            FeedSignalResponse(
                id=row.id,
                symbol=row.symbol,
                stock_name=names.get(row.symbol, row.symbol),
                source_kind=cast(Any, row.source_kind),
                signal_family=row.signal_family,
                signal_type=row.signal_type,
                attention_level=cast(Any, row.attention_level),
                known_at=row.known_at,
                effective_on=row.effective_on,
                title=row.title,
                summary=row.summary,
                display_payload=row.display_payload,
                evidence_path=f"/stock/{row.symbol}",
                ai_status="ready"
                if row.symbol in ai_symbols
                else "disabled"
                if not self._settings.llm_enabled
                else "not_built",
            )
            for row in rows
        ]

    async def coverage(self, user_id: UUID) -> WatchlistCoverageResponse:
        pairs = (
            await self._session.execute(
                select(WatchlistItemRecord.symbol, StockRecord.name)
                .join(WatchlistRecord)
                .join(StockRecord, StockRecord.symbol == WatchlistItemRecord.symbol)
                .where(WatchlistRecord.user_id == user_id)
                .distinct()
            )
        ).all()
        items: list[WatchlistCoverageItem] = []
        for symbol, name in pairs:
            issuer_type = await self._session.scalar(
                select(StockRecord.issuer_type).where(StockRecord.symbol == symbol)
            )
            unsupported = issuer_type in {"bank", "financial"}
            fundamental = (
                "unsupported"
                if unsupported
                else "ready"
                if await self._session.scalar(
                    select(ResearchSnapshotRecord.id)
                    .where(ResearchSnapshotRecord.symbol == symbol)
                    .limit(1)
                )
                else "not_built"
            )
            peer_snapshot = await self._session.scalar(
                select(PeerBenchmarkSnapshotRecord.id)
                .join(
                    CompanyPeerMetricPositionRecord,
                    CompanyPeerMetricPositionRecord.benchmark_snapshot_id
                    == PeerBenchmarkSnapshotRecord.id,
                )
                .where(CompanyPeerMetricPositionRecord.symbol == symbol)
                .limit(1)
            )
            peer_available = await self._session.scalar(
                select(CompanyPeerMetricPositionRecord.id)
                .where(
                    CompanyPeerMetricPositionRecord.symbol == symbol,
                    CompanyPeerMetricPositionRecord.status == "available",
                )
                .limit(1)
            )
            peer = (
                "unsupported"
                if unsupported
                else "ready"
                if peer_available
                else "insufficient_data"
                if peer_snapshot
                else "not_built"
            )
            event = (
                "ready"
                if await self._session.scalar(
                    select(EventRadarSnapshotRecord.id)
                    .where(EventRadarSnapshotRecord.symbol == symbol)
                    .limit(1)
                )
                else "not_built"
            )
            ai = (
                "ready"
                if await self._session.scalar(
                    select(AIResearchOutputRecord.id)
                    .where(AIResearchOutputRecord.symbol == symbol)
                    .limit(1)
                )
                else "disabled"
                if not self._settings.llm_enabled
                else "not_built"
            )
            items.append(
                WatchlistCoverageItem(
                    symbol=symbol,
                    stock_name=name,
                    coverage=SourceCoverage(
                        fundamental=fundamental, peer=peer, corporate_event=event, ai=ai
                    ),
                )
            )
        return WatchlistCoverageResponse(items=items, total=len(items))

    async def get_settings(self, user_id: UUID) -> AlertSettingsResponse:
        row = await self._session.get(UserResearchAlertSettingsRecord, user_id)
        if row is None:
            row = UserResearchAlertSettingsRecord(user_id=user_id)
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
        return self._settings_response(row)

    async def update_settings(
        self, user_id: UUID, payload: AlertSettingsUpdate
    ) -> AlertSettingsResponse:
        row = await self._session.get(UserResearchAlertSettingsRecord, user_id)
        if row is None:
            row = UserResearchAlertSettingsRecord(user_id=user_id)
            self._session.add(row)
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.settings_version = (row.settings_version or 0) + 1
        row.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(row)
        return self._settings_response(row)

    @staticmethod
    def _settings_response(row: UserResearchAlertSettingsRecord) -> AlertSettingsResponse:
        return AlertSettingsResponse(
            enabled=row.enabled,
            minimum_attention=cast(Any, row.minimum_attention),
            fundamental_enabled=row.fundamental_enabled,
            peer_enabled=row.peer_enabled,
            corporate_event_enabled=row.corporate_event_enabled,
            settings_version=row.settings_version,
            updated_at=row.updated_at,
        )

    async def dispatch(self, signal_id: UUID) -> DispatchResult:
        signal = await self._session.get(ResearchSignalRecord, signal_id)
        if signal is None:
            raise ValueError("signal_not_found")
        now = datetime.now(UTC)
        existing_run = await self._session.scalar(
            select(ResearchAlertDispatchRunRecord).where(
                ResearchAlertDispatchRunRecord.signal_id == signal_id,
                ResearchAlertDispatchRunRecord.matcher_version == MATCHER_VERSION,
            )
        )
        if existing_run is not None:
            if existing_run.status == "succeeded" or existing_run.lease_expires_at > now:
                return DispatchResult(status="skipped")
            run = existing_run
            run.status = "running"
            run.lease_expires_at = now + timedelta(minutes=10)
            run.error_summary = None
        else:
            run = ResearchAlertDispatchRunRecord(
                id=uuid4(),
                signal_id=signal_id,
                matcher_version=MATCHER_VERSION,
                status="running",
                lease_expires_at=now + timedelta(minutes=10),
            )
            self._session.add(run)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return DispatchResult(status="skipped")
        memberships = (
            await self._session.execute(
                select(WatchlistRecord.user_id, func.min(WatchlistItemRecord.created_at))
                .join(WatchlistItemRecord)
                .where(WatchlistItemRecord.symbol == signal.symbol)
                .group_by(WatchlistRecord.user_id)
            )
        ).all()
        deliveries = 0
        matched = 0
        for user_id, added_at in memberships:
            settings = await self._session.get(UserResearchAlertSettingsRecord, user_id)
            if settings is None or added_at is None:
                continue
            if not should_deliver_alert(
                signal_known_at=signal.known_at,
                membership_added_at=added_at,
                signal_attention=signal.attention_level,
                minimum_attention=settings.minimum_attention,
                enabled=settings.enabled,
                source_enabled=getattr(settings, f"{signal.source_kind}_enabled"),
            ):
                continue
            matched += 1
            self._session.add(
                UserResearchAlertDeliveryRecord(
                    id=uuid4(),
                    user_id=user_id,
                    signal_id=signal.id,
                    delivery_reason="new_signal_after_watchlist_membership",
                    settings_version=settings.settings_version,
                )
            )
            deliveries += 1
        try:
            run.status = "succeeded"
            run.matched_user_count = matched
            run.delivery_count = deliveries
            run.finished_at = datetime.now(UTC)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            return DispatchResult(status="skipped")
        return DispatchResult(
            status="succeeded", matched_user_count=matched, delivery_count=deliveries
        )

    async def alerts(self, user_id: UUID, *, limit: int) -> AlertListResponse:
        rows = (
            await self._session.execute(
                select(UserResearchAlertDeliveryRecord, ResearchSignalRecord)
                .join(ResearchSignalRecord)
                .where(UserResearchAlertDeliveryRecord.user_id == user_id)
                .order_by(UserResearchAlertDeliveryRecord.created_at.desc())
                .limit(limit)
            )
        ).all()
        rendered = await self._render_signals([row[1] for row in rows])
        by_id = {item.id: item for item in rendered}
        unread = (
            await self._session.scalar(
                select(func.count())
                .select_from(UserResearchAlertDeliveryRecord)
                .where(
                    UserResearchAlertDeliveryRecord.user_id == user_id,
                    UserResearchAlertDeliveryRecord.read_at.is_(None),
                )
            )
            or 0
        )
        return AlertListResponse(
            items=[
                AlertDeliveryResponse(
                    id=delivery.id,
                    signal=by_id[signal.id],
                    created_at=delivery.created_at,
                    read_at=delivery.read_at,
                )
                for delivery, signal in rows
            ],
            unread_count=unread,
        )

    async def alert_summary(self, user_id: UUID) -> AlertSummaryResponse:
        count = (
            await self._session.scalar(
                select(func.count())
                .select_from(UserResearchAlertDeliveryRecord)
                .where(
                    UserResearchAlertDeliveryRecord.user_id == user_id,
                    UserResearchAlertDeliveryRecord.read_at.is_(None),
                )
            )
            or 0
        )
        return AlertSummaryResponse(unread_count=count)

    async def mark_read(self, user_id: UUID, delivery_id: UUID) -> bool:
        result = await self._session.execute(
            update(UserResearchAlertDeliveryRecord)
            .where(
                UserResearchAlertDeliveryRecord.id == delivery_id,
                UserResearchAlertDeliveryRecord.user_id == user_id,
                UserResearchAlertDeliveryRecord.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        await self._session.commit()
        return bool(getattr(result, "rowcount", 0))

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self._session.execute(
            update(UserResearchAlertDeliveryRecord)
            .where(
                UserResearchAlertDeliveryRecord.user_id == user_id,
                UserResearchAlertDeliveryRecord.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        await self._session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
