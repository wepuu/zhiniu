from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from time import perf_counter
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.coverage.models import (
    BackfillItemResponse,
    BackfillRunResponse,
    BetaFeedbackCreate,
    BetaFeedbackOperatorView,
    BetaFeedbackResponse,
    BetaLearningReport,
    CoverageDimension,
    CoverageDimensionKey,
    CoverageSnapshotResult,
    StockCoverageResponse,
    UniverseMemberResponse,
    UniverseSnapshotResponse,
)
from zhaoniu_api.coverage.policy import DatasetPolicyRegistry
from zhaoniu_api.db import (
    AccessActivationRedemptionRecord,
    AIResearchOutputRecord,
    BetaFeedbackItemRecord,
    BetaResearchUniverseMemberRecord,
    BetaResearchUniverseSnapshotRecord,
    CompanyPeerMetricPositionRecord,
    CorporateEventBuildRunRecord,
    CoverageBackfillItemRecord,
    CoverageBackfillRunRecord,
    DataSyncRunRecord,
    EventRadarSnapshotItemRecord,
    EventRadarSnapshotRecord,
    FinancialReportRevisionRecord,
    IndustryMembershipRecord,
    NaturalLanguageScreenParseRunRecord,
    RegistrationInviteRecord,
    ResearchCoverageMemberRecord,
    ResearchCoverageSnapshotRecord,
    ResearchSnapshotRecord,
    SavedScreenRecord,
    ScreenExecutionRecord,
    ScreeningSnapshotFactRecord,
    ScreeningSnapshotMemberRecord,
    ScreeningSnapshotRecord,
    StockDailyBarRecord,
    StockRecord,
    User,
    WatchlistItemRecord,
    WatchlistRecord,
)
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.provider_configuration.models import (
    DeepSeekConfiguration,
    deepseek_route_available,
)
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService

COVERAGE_SCHEMA_VERSION = "research-coverage-v1"
EVALUATOR_VERSION = "coverage-evaluator-v1"
UNIVERSE_SCHEMA_VERSION = "beta-universe-v1"
PLANNER_VERSION = "coverage-planner-v1"
TARGET_PROFILE_VERSION = "beta-priority-v1"

DIMENSIONS = (
    "market",
    "financial",
    "fundamental_research",
    "industry",
    "peer_research",
    "event_radar",
    "screening",
    "ai_research",
)


def stable_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


def plan_actions(dimensions: list[CoverageDimension]) -> list[tuple[str, str, int, str]]:
    """Return minimal allow-listed actions as (dimension, action, order, reason)."""
    result: list[tuple[str, str, int, str]] = []
    by_key: dict[CoverageDimensionKey, CoverageDimension] = {
        item.dimension: item for item in dimensions
    }

    def add(dimension: str, action: str, order: int) -> None:
        item = by_key[cast(CoverageDimensionKey, dimension)]
        if item.availability == "ready" and item.freshness != "stale":
            return
        reason = item.reason_codes[0] if item.reason_codes else f"{dimension}_not_ready"
        result.append((dimension, action, order, reason))

    add("market", "sync_market", 10)
    add("financial", "sync_financial_statements", 20)
    if by_key["financial"].availability != "ready":
        result.append(("financial", "sync_valuations", 21, "financial_valuation_gap"))
    add("fundamental_research", "compute_fundamentals", 30)
    add("fundamental_research", "build_research_snapshot", 40)
    add("industry", "import_industry_membership", 50)
    add("peer_research", "build_peer_research", 60)
    add("event_radar", "sync_event_pipeline", 70)
    add("screening", "rebuild_screening_snapshot", 80)
    return list(dict.fromkeys(result))


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.combine(value, time.min, tzinfo=UTC)


class ResearchCoverageService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._policy = DatasetPolicyRegistry(settings)
        self._ai_stock_health_enabled: bool | None = None

    async def _stock_health_enabled(self) -> bool:
        if self._ai_stock_health_enabled is None:
            runtime = await ProviderConfigurationService(
                self._session, self._settings
            ).runtime("deepseek")
            configuration = DeepSeekConfiguration.model_validate(runtime.configuration)
            self._ai_stock_health_enabled = deepseek_route_available(
                configuration, runtime.credentials, "stock_health"
            )
        return self._ai_stock_health_enabled

    async def build_universe(
        self, *, operator_pinned: tuple[str, ...] | None = None, as_of: datetime | None = None
    ) -> UniverseSnapshotResponse:
        cutoff = as_of or datetime.now(UTC)
        pinned = operator_pinned or self._settings.coverage_pinned_symbols
        references = self._settings.coverage_reference_symbols
        watchlist_symbols = set(
            (
                await self._session.scalars(
                    select(distinct(WatchlistItemRecord.symbol))
                    .join(WatchlistRecord, WatchlistRecord.id == WatchlistItemRecord.watchlist_id)
                    .join(User, User.id == WatchlistRecord.user_id)
                    .where(User.status == "active")
                )
            ).all()
        )
        reasons: dict[str, set[str]] = {}
        for source, symbols in (
            ("operator_pinned", pinned),
            ("current_beta_watchlist", tuple(watchlist_symbols)),
            ("acceptance_reference", references),
        ):
            for raw in symbols:
                try:
                    canonical = resolve_symbol(raw).canonical
                except ValueError:
                    continue
                if await self._session.get(StockRecord, canonical) is not None:
                    reasons.setdefault(canonical, set()).add(source)
        ordered = sorted(
            reasons,
            key=lambda symbol: (
                0 if "operator_pinned" in reasons[symbol] else 1,
                0 if "current_beta_watchlist" in reasons[symbol] else 1,
                symbol,
            ),
        )
        manifest = {
            "operator_pinned_count": sum("operator_pinned" in reasons[s] for s in ordered),
            "watchlist_count": sum("current_beta_watchlist" in reasons[s] for s in ordered),
            "acceptance_count": sum("acceptance_reference" in reasons[s] for s in ordered),
            "symbols": ordered,
        }
        fingerprint = stable_hash({"schema": UNIVERSE_SCHEMA_VERSION, "manifest": manifest})
        existing = await self._session.scalar(
            select(BetaResearchUniverseSnapshotRecord).where(
                BetaResearchUniverseSnapshotRecord.universe_fingerprint == fingerprint
            )
        )
        if existing is None:
            existing = BetaResearchUniverseSnapshotRecord(
                id=uuid4(),
                knowledge_cutoff=cutoff,
                universe_fingerprint=fingerprint,
                source_manifest=manifest,
                schema_version=UNIVERSE_SCHEMA_VERSION,
            )
            self._session.add(existing)
            await self._session.flush()
            for rank, symbol in enumerate(ordered, start=1):
                self._session.add(
                    BetaResearchUniverseMemberRecord(
                        id=uuid4(),
                        snapshot_id=existing.id,
                        symbol=symbol,
                        priority_rank=rank,
                        reason_flags={
                            key: key in reasons[symbol]
                            for key in (
                                "operator_pinned",
                                "current_beta_watchlist",
                                "acceptance_reference",
                            )
                        },
                    )
                )
            await self._session.commit()
        return await self._universe_response(existing)

    async def _universe_response(
        self, snapshot: BetaResearchUniverseSnapshotRecord
    ) -> UniverseSnapshotResponse:
        rows = (
            await self._session.scalars(
                select(BetaResearchUniverseMemberRecord)
                .where(BetaResearchUniverseMemberRecord.snapshot_id == snapshot.id)
                .order_by(
                    BetaResearchUniverseMemberRecord.priority_rank,
                    BetaResearchUniverseMemberRecord.symbol,
                )
            )
        ).all()
        items = [
            UniverseMemberResponse(
                symbol=row.symbol,
                priority_rank=row.priority_rank,
                reason_flags=sorted(key for key, enabled in row.reason_flags.items() if enabled),
            )
            for row in rows
        ]
        return UniverseSnapshotResponse(
            id=snapshot.id,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            universe_fingerprint=snapshot.universe_fingerprint,
            schema_version=snapshot.schema_version,
            items=items,
            total=len(items),
        )

    async def build_coverage_snapshot(
        self, universe_snapshot_id: UUID | None = None, *, as_of: datetime | None = None
    ) -> CoverageSnapshotResult:
        universe = (
            await self._session.get(BetaResearchUniverseSnapshotRecord, universe_snapshot_id)
            if universe_snapshot_id
            else await self._session.scalar(
                select(BetaResearchUniverseSnapshotRecord)
                .order_by(BetaResearchUniverseSnapshotRecord.created_at.desc())
                .limit(1)
            )
        )
        if universe is None:
            raise ValueError("beta_universe_not_built")
        cutoff = as_of or datetime.now(UTC)
        evaluated_at = datetime.now(UTC)
        members = (
            await self._session.scalars(
                select(BetaResearchUniverseMemberRecord)
                .where(BetaResearchUniverseMemberRecord.snapshot_id == universe.id)
                .order_by(BetaResearchUniverseMemberRecord.priority_rank)
            )
        ).all()
        evaluated: list[tuple[str, list[CoverageDimension], list[str], str]] = []
        for member in members:
            dimensions, limitations = await self._evaluate_symbol(member.symbol, cutoff)
            manifest = [item.model_dump(mode="json") for item in dimensions]
            evaluated.append(
                (
                    member.symbol,
                    dimensions,
                    limitations,
                    stable_hash({"dimensions": manifest, "limitations": limitations}),
                )
            )
        fingerprint = stable_hash(
            {
                "universe": universe.universe_fingerprint,
                "cutoff": cutoff.isoformat(),
                "schema": COVERAGE_SCHEMA_VERSION,
                "evaluator": EVALUATOR_VERSION,
                "policy": self._policy.version,
                "members": [(symbol, item_hash) for symbol, _, _, item_hash in evaluated],
            }
        )
        existing = await self._session.scalar(
            select(ResearchCoverageSnapshotRecord).where(
                ResearchCoverageSnapshotRecord.content_fingerprint == fingerprint
            )
        )
        if existing is not None:
            return CoverageSnapshotResult(
                id=existing.id,
                universe_snapshot_id=existing.universe_snapshot_id,
                knowledge_cutoff=existing.knowledge_cutoff,
                evaluated_at=existing.evaluated_at,
                member_count=len(evaluated),
                content_fingerprint=fingerprint,
                status="skipped",
            )
        snapshot = ResearchCoverageSnapshotRecord(
            id=uuid4(),
            universe_snapshot_id=universe.id,
            knowledge_cutoff=cutoff,
            evaluated_at=evaluated_at,
            coverage_schema_version=COVERAGE_SCHEMA_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            policy_version=self._policy.version,
            content_fingerprint=fingerprint,
        )
        self._session.add(snapshot)
        await self._session.flush()
        for symbol, dimensions, limitations, item_hash in evaluated:
            self._session.add(
                ResearchCoverageMemberRecord(
                    id=uuid4(),
                    snapshot_id=snapshot.id,
                    symbol=symbol,
                    dimension_manifest={
                        "items": [item.model_dump(mode="json") for item in dimensions]
                    },
                    limitations={"items": limitations},
                    content_fingerprint=item_hash,
                )
            )
        await self._session.commit()
        return CoverageSnapshotResult(
            id=snapshot.id,
            universe_snapshot_id=universe.id,
            knowledge_cutoff=cutoff,
            evaluated_at=evaluated_at,
            member_count=len(evaluated),
            content_fingerprint=fingerprint,
            status="succeeded",
        )

    async def stock_coverage(self, symbol: str) -> StockCoverageResponse:
        canonical = resolve_symbol(symbol).canonical
        stock = await self._session.get(StockRecord, canonical)
        if stock is None:
            raise ValueError("stock_not_found")
        row = (
            await self._session.execute(
                select(ResearchCoverageMemberRecord, ResearchCoverageSnapshotRecord)
                .join(
                    ResearchCoverageSnapshotRecord,
                    ResearchCoverageSnapshotRecord.id == ResearchCoverageMemberRecord.snapshot_id,
                )
                .where(ResearchCoverageMemberRecord.symbol == canonical)
                .order_by(ResearchCoverageSnapshotRecord.evaluated_at.desc())
                .limit(1)
            )
        ).first()
        if row is not None:
            member, snapshot = row
            dimensions = [
                CoverageDimension.model_validate(item)
                for item in member.dimension_manifest.get("items", [])
            ]
            return StockCoverageResponse(
                symbol=stock.ticker,
                canonical_symbol=stock.symbol,
                snapshot_id=snapshot.id,
                knowledge_cutoff=snapshot.knowledge_cutoff,
                evaluated_at=snapshot.evaluated_at,
                coverage_schema_version=snapshot.coverage_schema_version,
                evaluator_version=snapshot.evaluator_version,
                policy_version=snapshot.policy_version,
                dimensions=dimensions,
                limitations=list(member.limitations.get("items", [])),
            )
        now = datetime.now(UTC)
        dimensions, limitations = await self._evaluate_symbol(canonical, now)
        return StockCoverageResponse(
            symbol=stock.ticker,
            canonical_symbol=stock.symbol,
            knowledge_cutoff=now,
            evaluated_at=now,
            coverage_schema_version=COVERAGE_SCHEMA_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            policy_version=self._policy.version,
            dimensions=dimensions,
            limitations=limitations + ["该股票尚未进入最新 Beta Coverage Snapshot。"],
        )

    async def _evaluate_symbol(
        self, symbol: str, cutoff: datetime
    ) -> tuple[list[CoverageDimension], list[str]]:
        stock = await self._session.get(StockRecord, symbol)
        if stock is None:
            raise ValueError("stock_not_found")
        dimensions: list[CoverageDimension] = []
        limitations: list[str] = []
        policy_blocked = self._policy.decide("market").allowed is False
        if policy_blocked:
            limitations.append("当前数据源仅允许开发与技术评估，外部展示需完成数据使用审查。")

        bars_count, latest_bar = (
            await self._session.execute(
                select(
                    func.count(StockDailyBarRecord.id), func.max(StockDailyBarRecord.trade_date)
                ).where(StockDailyBarRecord.symbol == symbol)
            )
        ).one()
        dimensions.append(
            await self._dimension(
                "market",
                bool(bars_count),
                latest_bar,
                cutoff,
                ready="ready",
                missing="missing_source_data",
                missing_reason="market_daily_bars_missing",
                policy_blocked=policy_blocked,
                symbol=symbol,
            )
        )

        report_count, latest_report = (
            await self._session.execute(
                select(
                    func.count(FinancialReportRevisionRecord.id),
                    func.max(FinancialReportRevisionRecord.known_at),
                ).where(
                    FinancialReportRevisionRecord.symbol == symbol,
                    FinancialReportRevisionRecord.known_at <= cutoff,
                )
            )
        ).one()
        financial_availability = (
            "ready" if report_count >= 4 else "partial" if report_count else "missing_source_data"
        )
        dimensions.append(
            await self._dimension(
                "financial",
                bool(report_count),
                latest_report,
                cutoff,
                ready=financial_availability,
                missing="missing_source_data",
                missing_reason="financial_missing_report"
                if not report_count
                else "financial_insufficient_history",
                policy_blocked=policy_blocked,
                symbol=symbol,
            )
        )

        latest_research = await self._session.scalar(
            select(ResearchSnapshotRecord)
            .where(
                ResearchSnapshotRecord.symbol == symbol,
                ResearchSnapshotRecord.knowledge_cutoff <= cutoff,
            )
            .order_by(ResearchSnapshotRecord.knowledge_cutoff.desc())
            .limit(1)
        )
        if stock.issuer_type != "general":
            dimensions.append(
                self._unsupported("fundamental_research", "unsupported_issuer_template")
            )
        else:
            dimensions.append(
                await self._dimension(
                    "fundamental_research",
                    latest_research is not None,
                    latest_research.knowledge_cutoff if latest_research else None,
                    cutoff,
                    ready="ready",
                    missing="not_built",
                    missing_reason="fundamental_snapshot_not_built",
                    policy_blocked=policy_blocked,
                    symbol=symbol,
                )
            )

        latest_industry = await self._session.scalar(
            select(IndustryMembershipRecord)
            .where(
                IndustryMembershipRecord.symbol == symbol,
                IndustryMembershipRecord.known_at <= cutoff,
            )
            .order_by(IndustryMembershipRecord.known_at.desc())
            .limit(1)
        )
        dimensions.append(
            await self._dimension(
                "industry",
                latest_industry is not None,
                latest_industry.known_at if latest_industry else None,
                cutoff,
                ready="ready",
                missing="missing_source_data",
                missing_reason="industry_missing_membership",
                policy_blocked=policy_blocked,
                symbol=symbol,
            )
        )

        peer_count, latest_peer = (
            await self._session.execute(
                select(
                    func.count(CompanyPeerMetricPositionRecord.id),
                    func.max(CompanyPeerMetricPositionRecord.created_at),
                ).where(CompanyPeerMetricPositionRecord.symbol == symbol)
            )
        ).one()
        if stock.issuer_type != "general":
            dimensions.append(self._unsupported("peer_research", "peer_unsupported_issuer_type"))
        else:
            dimensions.append(
                await self._dimension(
                    "peer_research",
                    bool(peer_count),
                    latest_peer,
                    cutoff,
                    ready="ready",
                    missing="not_built",
                    missing_reason="peer_not_built" if latest_industry else "peer_missing_industry",
                    policy_blocked=policy_blocked,
                    symbol=symbol,
                )
            )

        latest_event = await self._session.scalar(
            select(EventRadarSnapshotRecord)
            .where(
                EventRadarSnapshotRecord.symbol == symbol,
                EventRadarSnapshotRecord.knowledge_cutoff <= cutoff,
            )
            .order_by(EventRadarSnapshotRecord.knowledge_cutoff.desc())
            .limit(1)
        )
        event_reasons: list[str] = []
        if latest_event is not None:
            item_count = await self._session.scalar(
                select(func.count(EventRadarSnapshotItemRecord.id)).where(
                    EventRadarSnapshotItemRecord.snapshot_id == latest_event.id
                )
            )
            if not item_count:
                event_reasons.append("event_no_supported_events")
        event_dimension = await self._dimension(
            "event_radar",
            latest_event is not None,
            latest_event.knowledge_cutoff if latest_event else None,
            cutoff,
            ready="ready",
            missing="not_built",
            missing_reason="event_not_built",
            policy_blocked=policy_blocked,
            symbol=symbol,
        )
        if event_reasons and event_dimension.availability == "ready":
            event_dimension.reason_codes = event_reasons
        if latest_event is not None:
            event_dimension.source_health = cast(Any, latest_event.source_health)
            if latest_event.coverage_status == "partial":
                event_dimension.availability = "partial"
                event_dimension.reason_codes.append("event_source_degraded")
        dimensions.append(event_dimension)

        screening_member = (
            await self._session.execute(
                select(ScreeningSnapshotMemberRecord, ScreeningSnapshotRecord)
                .join(
                    ScreeningSnapshotRecord,
                    ScreeningSnapshotRecord.id == ScreeningSnapshotMemberRecord.snapshot_id,
                )
                .where(
                    ScreeningSnapshotMemberRecord.symbol == symbol,
                    ScreeningSnapshotRecord.knowledge_cutoff <= cutoff,
                )
                .order_by(ScreeningSnapshotRecord.knowledge_cutoff.desc())
                .limit(1)
            )
        ).first()
        if screening_member is None:
            dimensions.append(
                CoverageDimension(
                    dimension="screening",
                    availability="not_built",
                    reason_codes=["screening_snapshot_not_built"],
                )
            )
        else:
            screen_member, screen_snapshot = screening_member
            fact_count = await self._session.scalar(
                select(func.count(ScreeningSnapshotFactRecord.id)).where(
                    ScreeningSnapshotFactRecord.snapshot_id == screen_snapshot.id,
                    ScreeningSnapshotFactRecord.symbol == symbol,
                )
            )
            availability = (
                "ready"
                if screen_member.eligibility_status == "eligible" and fact_count
                else "partial"
            )
            dimensions.append(
                CoverageDimension(
                    dimension="screening",
                    availability=cast(Any, availability),
                    freshness="current",
                    source_health="healthy",
                    reason_codes=[]
                    if availability == "ready"
                    else [screen_member.exclusion_reason or "screening_no_available_facts"],
                    latest_artifact_at=screen_snapshot.knowledge_cutoff,
                )
            )

        latest_ai = await self._session.scalar(
            select(AIResearchOutputRecord)
            .where(
                AIResearchOutputRecord.symbol == symbol,
                AIResearchOutputRecord.research_type == "stock_health",
                AIResearchOutputRecord.knowledge_cutoff <= cutoff,
            )
            .order_by(AIResearchOutputRecord.generated_at.desc())
            .limit(1)
        )
        if stock.issuer_type != "general":
            dimensions.append(self._unsupported("ai_research", "ai_unsupported_issuer_type"))
        elif not await self._stock_health_enabled():
            dimensions.append(
                CoverageDimension(
                    dimension="ai_research", availability="disabled", reason_codes=["ai_disabled"]
                )
            )
        elif latest_ai is None:
            dimensions.append(
                CoverageDimension(
                    dimension="ai_research", availability="not_built", reason_codes=["ai_not_built"]
                )
            )
        else:
            dimensions.append(
                CoverageDimension(
                    dimension="ai_research",
                    availability="ready",
                    freshness="current"
                    if latest_research and latest_ai.snapshot_id == latest_research.id
                    else "stale",
                    source_health="healthy",
                    latest_artifact_at=latest_ai.generated_at,
                    reason_codes=[]
                    if latest_research and latest_ai.snapshot_id == latest_research.id
                    else ["ai_snapshot_stale"],
                )
            )
        return dimensions, limitations

    async def _dimension(
        self,
        dimension: str,
        present: bool,
        latest: date | datetime | None,
        cutoff: datetime,
        *,
        ready: str,
        missing: str,
        missing_reason: str,
        policy_blocked: bool,
        symbol: str,
    ) -> CoverageDimension:
        if policy_blocked:
            return CoverageDimension(
                dimension=cast(Any, dimension),
                availability="blocked_by_policy",
                reason_codes=["policy_development_source_only"],
            )
        latest_at = _as_datetime(latest)
        freshness = "unknown"
        if latest_at is not None:
            freshness_days = {
                "market": 7,
                "financial": 550,
                "fundamental_research": 550,
                "industry": 550,
                "peer_research": 550,
                "event_radar": 45,
            }.get(dimension, 30)
            freshness = (
                "current" if cutoff - latest_at <= timedelta(days=freshness_days) else "stale"
            )
        source_health = await self._source_health(dimension, present, symbol)
        reasons = [] if present else [missing_reason]
        if present and ready == "partial":
            reasons = [missing_reason]
        if source_health in {"degraded", "unavailable"}:
            reasons.append("provider_unavailable")
        return CoverageDimension(
            dimension=cast(Any, dimension),
            availability=cast(Any, ready if present else missing),
            freshness=cast(Any, freshness),
            source_health=cast(Any, source_health),
            reason_codes=reasons,
            latest_artifact_at=latest_at,
        )

    async def _source_health(self, dimension: str, retained: bool, symbol: str) -> str:
        datasets = {
            "market": ("daily_bars",),
            "financial": ("financial_statements", "valuations"),
            "fundamental_research": ("financial_statements", "valuations"),
            "industry": (),
            "peer_research": (),
        }.get(dimension, ())
        if datasets:
            latest = await self._session.scalar(
                select(DataSyncRunRecord)
                .where(DataSyncRunRecord.dataset.in_(datasets), DataSyncRunRecord.symbol == symbol)
                .order_by(DataSyncRunRecord.started_at.desc())
                .limit(1)
            )
            if latest is not None and latest.status == "failed":
                return "degraded" if retained else "unavailable"
        if dimension == "event_radar":
            latest_event_run = await self._session.scalar(
                select(CorporateEventBuildRunRecord)
                .where(CorporateEventBuildRunRecord.symbol == symbol)
                .order_by(CorporateEventBuildRunRecord.started_at.desc())
                .limit(1)
            )
            if latest_event_run is not None:
                return latest_event_run.source_health
        return "healthy" if retained else "unknown"

    @staticmethod
    def _unsupported(dimension: str, reason: str) -> CoverageDimension:
        return CoverageDimension(
            dimension=cast(Any, dimension),
            availability="unsupported",
            source_health="healthy",
            reason_codes=[reason],
        )

    async def plan_backfill(self, coverage_snapshot_id: UUID | None = None) -> BackfillRunResponse:
        snapshot = (
            await self._session.get(ResearchCoverageSnapshotRecord, coverage_snapshot_id)
            if coverage_snapshot_id
            else await self._session.scalar(
                select(ResearchCoverageSnapshotRecord)
                .order_by(ResearchCoverageSnapshotRecord.evaluated_at.desc())
                .limit(1)
            )
        )
        if snapshot is None:
            raise ValueError("coverage_snapshot_not_built")
        idempotency = stable_hash(
            {
                "universe": str(snapshot.universe_snapshot_id),
                "coverage": str(snapshot.id),
                "planner": PLANNER_VERSION,
                "policy": self._policy.version,
                "target": TARGET_PROFILE_VERSION,
            }
        )
        existing = await self._session.scalar(
            select(CoverageBackfillRunRecord).where(
                CoverageBackfillRunRecord.idempotency_key == idempotency
            )
        )
        if existing is not None:
            return await self.backfill_status(existing.id)
        members = (
            await self._session.scalars(
                select(ResearchCoverageMemberRecord)
                .where(ResearchCoverageMemberRecord.snapshot_id == snapshot.id)
                .order_by(ResearchCoverageMemberRecord.symbol)
            )
        ).all()
        run = CoverageBackfillRunRecord(
            id=uuid4(),
            universe_snapshot_id=snapshot.universe_snapshot_id,
            coverage_snapshot_id=snapshot.id,
            idempotency_key=idempotency,
            planner_version=PLANNER_VERSION,
            policy_version=self._policy.version,
            target_profile_version=TARGET_PROFILE_VERSION,
            status="pending",
        )
        self._session.add(run)
        await self._session.flush()
        screening_planned = False
        planned = 0
        blocked = 0
        for member in members:
            dimensions = [
                CoverageDimension.model_validate(item)
                for item in member.dimension_manifest.get("items", [])
            ]
            for dimension, action, order, reason in plan_actions(dimensions):
                if action == "rebuild_screening_snapshot":
                    if screening_planned:
                        continue
                    screening_planned = True
                item_status = (
                    "blocked"
                    if any(
                        item.dimension == dimension and item.availability == "blocked_by_policy"
                        for item in dimensions
                    )
                    else "pending"
                )
                blocked += int(item_status == "blocked")
                planned += 1
                self._session.add(
                    CoverageBackfillItemRecord(
                        id=uuid4(),
                        run_id=run.id,
                        symbol=member.symbol,
                        action_key=action,
                        reason_code=reason,
                        dependency_order=order,
                        status=item_status,
                    )
                )
        run.planned_items = planned
        run.blocked_items = blocked
        await self._session.commit()
        return await self.backfill_status(run.id)

    async def run_backfill(self, run_id: UUID) -> BackfillRunResponse:
        run = await self._session.get(CoverageBackfillRunRecord, run_id, with_for_update=True)
        if run is None:
            raise ValueError("backfill_run_not_found")
        if run.status in {"succeeded", "partial", "failed"}:
            return await self.backfill_status(run.id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await self._session.execute(
            update(CoverageBackfillItemRecord)
            .where(
                CoverageBackfillItemRecord.run_id == run.id,
                CoverageBackfillItemRecord.status == "running",
                CoverageBackfillItemRecord.lease_expires_at < datetime.now(UTC),
            )
            .values(
                status="pending",
                lease_expires_at=None,
                error_code="expired_lease_recovered",
            )
        )
        await self._session.commit()
        items = (
            await self._session.scalars(
                select(CoverageBackfillItemRecord)
                .where(
                    CoverageBackfillItemRecord.run_id == run.id,
                    CoverageBackfillItemRecord.status == "pending",
                )
                .order_by(
                    CoverageBackfillItemRecord.dependency_order, CoverageBackfillItemRecord.symbol
                )
                .limit(self._settings.coverage_backfill_batch_size)
            )
        ).all()
        for item in items:
            await self._execute_item(item)
        counts = Counter(
            (
                await self._session.scalars(
                    select(CoverageBackfillItemRecord.status).where(
                        CoverageBackfillItemRecord.run_id == run.id
                    )
                )
            ).all()
        )
        run = await self._session.get(CoverageBackfillRunRecord, run.id)
        assert run is not None
        run.succeeded_items = counts["succeeded"]
        run.failed_items = counts["failed"]
        run.skipped_items = counts["skipped"]
        run.blocked_items = counts["blocked"]
        pending = counts["pending"] + counts["running"]
        if pending:
            run.status = "running"
        elif counts["failed"] and counts["succeeded"]:
            run.status = "partial"
        elif counts["failed"]:
            run.status = "failed"
        else:
            run.status = "succeeded"
        if not pending:
            run.finished_at = datetime.now(UTC)
        await self._session.commit()
        if not pending:
            await self.build_coverage_snapshot(run.universe_snapshot_id)
        return await self.backfill_status(run.id)

    async def recover_interrupted_backfill(self, run_id: UUID) -> BackfillRunResponse:
        """Operator recovery for a confirmed-dead worker; never runs work itself."""
        run = await self._session.get(CoverageBackfillRunRecord, run_id, with_for_update=True)
        if run is None:
            raise ValueError("backfill_run_not_found")
        await self._session.execute(
            update(CoverageBackfillItemRecord)
            .where(
                CoverageBackfillItemRecord.run_id == run.id,
                CoverageBackfillItemRecord.status == "running",
            )
            .values(
                status="pending",
                lease_expires_at=None,
                error_code="operator_recovered_interruption",
            )
        )
        run.status = "pending"
        await self._session.commit()
        return await self.backfill_status(run.id)

    async def _execute_item(self, item: CoverageBackfillItemRecord) -> None:
        from zhaoniu_api.composition import (
            build_corporate_event_service,
            build_fundamental_service,
            build_market_data_service,
            build_peer_research_service,
            build_research_feed_service,
            build_research_service,
            build_screening_service,
        )

        item_id = item.id
        item.status = "running"
        item.attempt_count += 1
        attempt_count = item.attempt_count
        item.started_at = datetime.now(UTC)
        item.lease_expires_at = item.started_at + timedelta(minutes=30)
        item.before_fingerprint = await self._artifact_fingerprint(item.symbol)
        await self._session.commit()
        started = perf_counter()
        provider_calls = int(item.action_key.startswith(("sync_", "import_")))
        try:
            result: Any
            if item.action_key == "sync_market":
                result = await build_market_data_service(self._session).sync_daily_bars(item.symbol)
            elif item.action_key == "sync_financial_statements":
                result = await build_fundamental_service(self._session).sync_financial_statements(
                    item.symbol, start_year=date.today().year - 6
                )
            elif item.action_key == "sync_valuations":
                result = await build_fundamental_service(self._session).sync_valuations(item.symbol)
            elif item.action_key == "compute_fundamentals":
                result = await build_fundamental_service(self._session).compute_snapshot(
                    item.symbol
                )
            elif item.action_key == "build_research_snapshot":
                result = await build_research_service(self._session).build_snapshot(item.symbol)
            elif item.action_key == "import_industry_membership":
                result = await build_peer_research_service(self._session).sync_industries()
            elif item.action_key == "build_peer_research":
                result = await build_peer_research_service(self._session).build_peer_research(
                    item.symbol
                )
            elif item.action_key == "sync_event_pipeline":
                events = build_corporate_event_service(self._session)
                sync_result = await events.sync_disclosures(item.symbol)
                await events.build_corporate_events(item.symbol)
                result = await events.build_event_radar(item.symbol)
                item.rows_received = getattr(sync_result, "received_count", 0)
            elif item.action_key == "rebuild_screening_snapshot":
                result = await build_screening_service(self._session).build_snapshot()
            else:
                raise ValueError("unsupported_backfill_action")
            item.after_fingerprint = await self._artifact_fingerprint(item.symbol)
            item.changed = item.before_fingerprint != item.after_fingerprint
            result_status = str(getattr(result, "status", "succeeded"))
            item.status = (
                "skipped" if result_status == "skipped" or not item.changed else "succeeded"
            )
            item.provider_call_count = provider_calls
            item.rows_received = item.rows_received or int(getattr(result, "received_count", 0))
            item.rows_written = int(getattr(result, "written_count", 0))
            item.rows_skipped = max(0, item.rows_received - item.rows_written)
            if item.changed and item.action_key in {
                "build_research_snapshot",
                "build_peer_research",
                "sync_event_pipeline",
            }:
                await build_research_feed_service(self._session).project_symbol(item.symbol)
        except Exception as error:
            error_code = type(error).__name__[:120]
            await self._session.rollback()
            persisted = await self._session.get(CoverageBackfillItemRecord, item_id)
            if persisted is not None:
                persisted.status = "failed"
                persisted.attempt_count = attempt_count
                persisted.error_code = error_code
                persisted.finished_at = datetime.now(UTC)
        finally:
            persisted = await self._session.get(CoverageBackfillItemRecord, item_id)
            if persisted is not None:
                persisted.duration_ms = round((perf_counter() - started) * 1000)
                persisted.finished_at = persisted.finished_at or datetime.now(UTC)
                persisted.lease_expires_at = None
            await self._session.commit()

    async def _artifact_fingerprint(self, symbol: str) -> str:
        values = []
        for model in (
            StockDailyBarRecord,
            FinancialReportRevisionRecord,
            ResearchSnapshotRecord,
            CompanyPeerMetricPositionRecord,
            EventRadarSnapshotRecord,
        ):
            count = await self._session.scalar(
                select(func.count(model.id)).where(model.symbol == symbol)
            )
            values.append((model.__tablename__, int(count or 0)))
        return stable_hash(values)

    async def backfill_status(self, run_id: UUID) -> BackfillRunResponse:
        run = await self._session.get(CoverageBackfillRunRecord, run_id)
        if run is None:
            raise ValueError("backfill_run_not_found")
        rows = (
            await self._session.scalars(
                select(CoverageBackfillItemRecord)
                .where(CoverageBackfillItemRecord.run_id == run.id)
                .order_by(
                    CoverageBackfillItemRecord.dependency_order, CoverageBackfillItemRecord.symbol
                )
            )
        ).all()
        return BackfillRunResponse(
            id=run.id,
            universe_snapshot_id=run.universe_snapshot_id,
            coverage_snapshot_id=run.coverage_snapshot_id,
            status=cast(Any, run.status),
            planned_items=run.planned_items,
            succeeded_items=run.succeeded_items,
            failed_items=run.failed_items,
            skipped_items=run.skipped_items,
            blocked_items=run.blocked_items,
            items=[
                BackfillItemResponse(
                    id=row.id,
                    symbol=row.symbol,
                    action_key=row.action_key,
                    reason_code=row.reason_code,
                    status=cast(Any, row.status),
                    dependency_order=row.dependency_order,
                    changed=row.changed,
                    error_code=row.error_code,
                )
                for row in rows
            ],
        )

    async def create_feedback(
        self, user_id: UUID, payload: BetaFeedbackCreate
    ) -> BetaFeedbackResponse:
        message = " ".join(payload.message.strip().split())
        row = BetaFeedbackItemRecord(
            id=uuid4(),
            user_id=user_id,
            feature_key=payload.feature_key,
            category=payload.category,
            message=message,
            status="new",
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return BetaFeedbackResponse(
            id=row.id,
            feature_key=cast(Any, row.feature_key),
            category=cast(Any, row.category),
            status=cast(Any, row.status),
            created_at=row.created_at,
        )

    async def list_feedback(self, limit: int = 100) -> list[BetaFeedbackOperatorView]:
        rows = (
            await self._session.scalars(
                select(BetaFeedbackItemRecord)
                .order_by(BetaFeedbackItemRecord.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            BetaFeedbackOperatorView(
                id=row.id,
                user_id=row.user_id,
                feature_key=cast(Any, row.feature_key),
                category=cast(Any, row.category),
                message=row.message,
                status=cast(Any, row.status),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def update_feedback_status(
        self, feedback_id: UUID, status: str
    ) -> BetaFeedbackOperatorView:
        if status not in {"triaged", "resolved"}:
            raise ValueError("invalid_feedback_status")
        row = await self._session.get(BetaFeedbackItemRecord, feedback_id)
        if row is None:
            raise ValueError("feedback_not_found")
        row.status = status
        await self._session.commit()
        await self._session.refresh(row)
        return BetaFeedbackOperatorView(
            id=row.id,
            user_id=row.user_id,
            feature_key=cast(Any, row.feature_key),
            category=cast(Any, row.category),
            message=row.message,
            status=cast(Any, row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def learning_report(self, days: int) -> BetaLearningReport:
        if days not in {7, 30}:
            raise ValueError("report_days_must_be_7_or_30")
        since = datetime.now(UTC) - timedelta(days=days)

        async def scalar_count(statement: Any) -> int:
            return int((await self._session.scalar(statement)) or 0)

        adoption: dict[str, int | str] = {
            "invites_consumed": await scalar_count(
                select(func.count(RegistrationInviteRecord.id)).where(
                    RegistrationInviteRecord.consumed_at >= since
                )
            ),
            "verified_accounts": await scalar_count(
                select(func.count(User.id)).where(User.email_verified_at.is_not(None))
            ),
            "users_with_watchlist": await scalar_count(
                select(func.count(distinct(WatchlistRecord.user_id))).join(
                    WatchlistItemRecord, WatchlistItemRecord.watchlist_id == WatchlistRecord.id
                )
            ),
            "screen_users": await scalar_count(
                select(func.count(distinct(ScreenExecutionRecord.user_id))).where(
                    ScreenExecutionRecord.created_at >= since
                )
            ),
            "saved_screen_users": await scalar_count(
                select(func.count(distinct(SavedScreenRecord.user_id))).where(
                    SavedScreenRecord.created_at >= since
                )
            ),
            "natural_language_parser_users": await scalar_count(
                select(func.count(distinct(NaturalLanguageScreenParseRunRecord.user_id))).where(
                    NaturalLanguageScreenParseRunRecord.created_at >= since
                )
            ),
            "activation_redemptions": await scalar_count(
                select(func.count(AccessActivationRedemptionRecord.id)).where(
                    AccessActivationRedemptionRecord.redeemed_at >= since
                )
            ),
        }
        snapshot = await self._session.scalar(
            select(ResearchCoverageSnapshotRecord)
            .order_by(ResearchCoverageSnapshotRecord.evaluated_at.desc())
            .limit(1)
        )
        coverage: dict[str, dict[str, int]] = {}
        gaps: Counter[str] = Counter()
        if snapshot is not None:
            members = (
                await self._session.scalars(
                    select(ResearchCoverageMemberRecord).where(
                        ResearchCoverageMemberRecord.snapshot_id == snapshot.id
                    )
                )
            ).all()
            for member in members:
                for raw in member.dimension_manifest.get("items", []):
                    item = CoverageDimension.model_validate(raw)
                    coverage.setdefault(item.dimension, {})[item.availability] = (
                        coverage.setdefault(item.dimension, {}).get(item.availability, 0) + 1
                    )
                    gaps.update(item.reason_codes)
        run_counts = Counter(
            (
                await self._session.scalars(
                    select(CoverageBackfillItemRecord.status)
                    .join(
                        CoverageBackfillRunRecord,
                        CoverageBackfillRunRecord.id == CoverageBackfillItemRecord.run_id,
                    )
                    .where(CoverageBackfillRunRecord.created_at >= since)
                )
            ).all()
        )
        feedback_counts = Counter(
            (
                await self._session.scalars(
                    select(BetaFeedbackItemRecord.category).where(
                        BetaFeedbackItemRecord.created_at >= since
                    )
                )
            ).all()
        )

        def suppress_small_cell(value: int) -> int | str:
            if 0 < value < self._settings.beta_learning_min_group_size:
                return f"<{self._settings.beta_learning_min_group_size}"
            return value

        adoption = {key: suppress_small_cell(int(value)) for key, value in adoption.items()}
        return BetaLearningReport(
            generated_at=datetime.now(UTC),
            period_days=days,
            adoption=adoption,
            coverage=coverage,
            top_gaps=[
                {"reason_code": reason, "affected_members": count}
                for reason, count in gaps.most_common(5)
            ],
            backfill={
                key: int(run_counts[key]) for key in ("succeeded", "skipped", "failed", "blocked")
            },
            feedback={
                key: suppress_small_cell(int(value))
                for key, value in sorted(feedback_counts.items())
            },
            unavailable_metrics=[
                "research_feed_opened",
                "peer_research_opened",
                "event_radar_opened",
                "ai_research_opened",
            ],
        )
