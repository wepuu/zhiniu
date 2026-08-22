from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, distinct, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.service import AccessControlService
from zhaoniu_api.db import (
    CompanyPeerMetricPositionRecord,
    CorporateEventRecord,
    EventRadarSnapshotItemRecord,
    EventRadarSnapshotRecord,
    FundamentalMetricPointRecord,
    IndustryMembershipRecord,
    IndustryRecord,
    NaturalLanguageScreenParseRunRecord,
    PeerBenchmarkSnapshotRecord,
    SavedScreenRecord,
    ScreenExecutionRecord,
    ScreenExecutionRequestRecord,
    ScreeningSnapshotFactRecord,
    ScreeningSnapshotMemberRecord,
    ScreeningSnapshotRecord,
    ScreenResultRecord,
    StockRecord,
    ValuationObservationRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)
from zhaoniu_api.fundamentals.metrics import DEFINITION_BY_CODE, METRIC_VERSION
from zhaoniu_api.peer_research.models import (
    PEER_PRODUCER_VERSION,
    PRIMARY_TAXONOMY_CODE,
    PRIMARY_TAXONOMY_VERSION,
)
from zhaoniu_api.screening.models import (
    EventCriterion,
    IndustryCriterion,
    MetricCriterion,
    PeerCriterion,
    SavedScreenCreate,
    SavedScreenListResponse,
    SavedScreenResponse,
    SavedScreenUpdate,
    ScreenCatalogResponse,
    ScreenCoverageEstimateResponse,
    ScreenCoverageResponse,
    ScreenCriterionCoverage,
    ScreenExecutionListResponse,
    ScreenExecutionResponse,
    ScreenIndustryCatalogItem,
    ScreeningBuildResult,
    ScreenMatchedCondition,
    ScreenMetricCatalogItem,
    ScreenQuery,
    ScreenResultItem,
    ScreenResultListResponse,
    ScreenValidationIssue,
    ScreenValidationResponse,
)

DSL_VERSION = "screen-query-v1"
CATALOG_VERSION = "screen-catalog-v2"
ENGINE_VERSION = "screen-engine-v1"
SELECTOR_VERSION = "screen-selector-v1"
EVENT_RADAR_VERSION = "event-radar-v1"
LEASE_MINUTES = 30

METRIC_CODES = (
    "revenue_yoy",
    "parent_net_profit_yoy",
    "revenue_cagr_3y",
    "parent_net_profit_cagr_3y",
    "gross_margin",
    "parent_net_margin",
    "roe_avg_equity_fy",
    "roa_avg_assets_fy",
    "ocf_to_parent_net_profit",
    "debt_to_assets",
    "pe_ttm_percentile_3y",
    "pb_percentile_3y",
)
VALUATION_CODES = ("pe_ttm", "pb", "pcf", "market_cap")
ANNUAL_METRIC_CODES = (
    "revenue_cagr_3y",
    "parent_net_profit_cagr_3y",
    "roe_avg_equity_fy",
    "roa_avg_assets_fy",
)
PEER_METRIC_CODES = METRIC_CODES[:10] + VALUATION_CODES
EVENT_FAMILIES = (
    "share_repurchase",
    "share_pledge",
    "share_unlock",
    "regulatory_action",
    "shareholder_change",
    "litigation_arbitration",
)
DISPLAY_NAMES = {
    "revenue_yoy": "营业收入同比",
    "parent_net_profit_yoy": "归母净利润同比",
    "revenue_cagr_3y": "营业收入三年复合增速",
    "parent_net_profit_cagr_3y": "归母净利润三年复合增速",
    "gross_margin": "毛利率",
    "parent_net_margin": "归母净利率",
    "roe_avg_equity_fy": "年度平均权益 ROE",
    "roa_avg_assets_fy": "年度平均资产 ROA",
    "ocf_to_parent_net_profit": "现金利润比",
    "debt_to_assets": "资产负债率",
    "pe_ttm": "市盈率 TTM",
    "pb": "市净率",
    "pcf": "市现率",
    "market_cap": "总市值",
    "pe_ttm_percentile_3y": "市盈率三年分位",
    "pb_percentile_3y": "市净率三年分位",
}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()


def _canonical(query: ScreenQuery) -> dict[str, Any]:
    return query.model_dump(mode="json", exclude_none=True)


def _criteria_contract_hash() -> str:
    return _hash(
        {
            "dsl_version": DSL_VERSION,
            "metric_codes": METRIC_CODES,
            "valuation_codes": VALUATION_CODES,
            "annual_metric_codes": ANNUAL_METRIC_CODES,
            "peer_metric_codes": PEER_METRIC_CODES,
            "event_families": EVENT_FAMILIES,
            "operators": ("gt", "gte", "lt", "lte", "between"),
            "max_filters": 8,
            "conjunction": "and",
        }
    )


CRITERIA_CONTRACT_HASH = _criteria_contract_hash()


def _compare(value: Decimal, operator: str, lower: Decimal, upper: Decimal | None) -> bool:
    if operator == "gt":
        return value > lower
    if operator == "gte":
        return value >= lower
    if operator == "lt":
        return value < lower
    if operator == "lte":
        return value <= lower
    return upper is not None and lower <= value <= upper


def _encode_cursor(ordinal: int) -> str:
    return base64.urlsafe_b64encode(str(ordinal).encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid_cursor") from exc


class ScreeningService:
    def __init__(
        self, session: AsyncSession, access_control: AccessControlService | None = None
    ) -> None:
        self._session = session
        self._access_control = access_control

    async def catalog(self) -> ScreenCatalogResponse:
        metrics = []
        for code in METRIC_CODES + VALUATION_CODES:
            definition = DEFINITION_BY_CODE[code]
            metrics.append(
                ScreenMetricCatalogItem(
                    code=code,
                    display_name=DISPLAY_NAMES[code],
                    dimension=definition.dimension,
                    unit=definition.unit,
                    source_kind="valuation" if code in VALUATION_CODES else "metric",
                    selectors=["latest_available", "latest_fy"]
                    if code in ANNUAL_METRIC_CODES
                    else ["latest_available"],
                    operators=["gt", "gte", "lt", "lte", "between"],
                )
            )
        rows = (
            await self._session.execute(
                select(
                    IndustryRecord.taxonomy_code,
                    IndustryRecord.taxonomy_version,
                    IndustryRecord.code,
                    IndustryRecord.name,
                )
                .where(
                    IndustryRecord.taxonomy_code == PRIMARY_TAXONOMY_CODE,
                    IndustryRecord.taxonomy_version == PRIMARY_TAXONOMY_VERSION,
                )
                .order_by(IndustryRecord.name, IndustryRecord.code)
            )
        ).all()
        industries = [
            ScreenIndustryCatalogItem(
                taxonomy_code=row[0],
                taxonomy_version=row[1],
                industry_code=row[2],
                industry_name=row[3],
            )
            for row in rows
        ]
        catalog_hash = _hash(
            {
                "version": CATALOG_VERSION,
                "metrics": [item.model_dump(mode="json") for item in metrics],
                "peer_metric_codes": PEER_METRIC_CODES,
                "industries": [item.model_dump(mode="json") for item in industries],
                "event_families": EVENT_FAMILIES,
            }
        )
        return ScreenCatalogResponse(
            dsl_version=DSL_VERSION,
            catalog_version=CATALOG_VERSION,
            catalog_hash=catalog_hash,
            criteria_contract_hash=CRITERIA_CONTRACT_HASH,
            metrics=metrics,
            peer_metric_codes=list(PEER_METRIC_CODES),
            industries=industries,
            event_families=list(EVENT_FAMILIES),
            limitations=[
                "仅覆盖已构建且可追溯的数据，不代表全市场完整覆盖。",
                "行业分类与当前外部数据仅用于开发和技术评估。",
                "筛选结果描述条件匹配，不构成投资建议或证券排名。",
            ],
        )

    def validate(self, query: ScreenQuery) -> ScreenValidationResponse:
        issues: list[ScreenValidationIssue] = []
        for index, criterion in enumerate(query.filters):
            path = f"filters.{index}"
            if isinstance(criterion, MetricCriterion):
                if criterion.metric_code not in METRIC_CODES + VALUATION_CODES:
                    issues.append(
                        ScreenValidationIssue(
                            path=f"{path}.metric_code",
                            code="unsupported_metric",
                            message="该指标不在筛选目录中。",
                        )
                    )
                if (
                    criterion.metric_code not in ANNUAL_METRIC_CODES
                    and criterion.selector != "latest_available"
                ):
                    issues.append(
                        ScreenValidationIssue(
                            path=f"{path}.selector",
                            code="unsupported_selector",
                            message="该指标只支持最新可用值。",
                        )
                    )
            elif isinstance(criterion, PeerCriterion):
                if criterion.metric_code not in PEER_METRIC_CODES:
                    issues.append(
                        ScreenValidationIssue(
                            path=f"{path}.metric_code",
                            code="unsupported_peer_metric",
                            message="该指标尚未纳入同行筛选目录。",
                        )
                    )
            elif isinstance(criterion, IndustryCriterion):
                if (
                    criterion.taxonomy_code != PRIMARY_TAXONOMY_CODE
                    or criterion.taxonomy_version != PRIMARY_TAXONOMY_VERSION
                ):
                    issues.append(
                        ScreenValidationIssue(
                            path=path,
                            code="unsupported_taxonomy",
                            message="行业条件必须使用当前明确版本的分类体系。",
                        )
                    )
        if query.sort.field != "symbol" and query.sort.field not in METRIC_CODES + VALUATION_CODES:
            issues.append(
                ScreenValidationIssue(
                    path="sort.field",
                    code="unsupported_sort",
                    message="排序字段必须是股票代码或已支持指标。",
                )
            )
        canonical = _canonical(query)
        return ScreenValidationResponse(
            valid=not issues,
            canonical_query=query if not issues else None,
            query_hash=_hash(canonical) if not issues else None,
            issues=issues,
        )

    async def build_snapshot(self, as_of: datetime | None = None) -> ScreeningBuildResult:
        cutoff = as_of or datetime.now(UTC).replace(second=0, microsecond=0)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        stocks = (
            await self._session.scalars(
                select(StockRecord)
                .where(StockRecord.asset_type == "stock")
                .order_by(StockRecord.symbol)
            )
        ).all()
        universe_fingerprint = _hash([(row.symbol, row.status, row.issuer_type) for row in stocks])
        key = _hash(
            {
                "cutoff": cutoff,
                "universe": universe_fingerprint,
                "metric": METRIC_VERSION,
                "taxonomy": [PRIMARY_TAXONOMY_CODE, PRIMARY_TAXONOMY_VERSION],
                "peer": PEER_PRODUCER_VERSION,
                "event": EVENT_RADAR_VERSION,
                "selector": SELECTOR_VERSION,
            }
        )
        existing = await self._session.scalar(
            select(ScreeningSnapshotRecord).where(ScreeningSnapshotRecord.idempotency_key == key)
        )
        if existing:
            members = await self._session.scalar(
                select(func.count())
                .select_from(ScreeningSnapshotMemberRecord)
                .where(ScreeningSnapshotMemberRecord.snapshot_id == existing.id)
            )
            fact_count = await self._session.scalar(
                select(func.count())
                .select_from(ScreeningSnapshotFactRecord)
                .where(ScreeningSnapshotFactRecord.snapshot_id == existing.id)
            )
            return ScreeningBuildResult(
                status="skipped",
                snapshot_id=existing.id,
                member_count=members or 0,
                fact_count=fact_count or 0,
                idempotency_key=key,
            )

        snapshot = ScreeningSnapshotRecord(
            id=uuid4(),
            knowledge_cutoff=cutoff,
            universe_fingerprint=universe_fingerprint,
            metric_version=METRIC_VERSION,
            taxonomy_code=PRIMARY_TAXONOMY_CODE,
            taxonomy_version=PRIMARY_TAXONOMY_VERSION,
            peer_producer_version=PEER_PRODUCER_VERSION,
            event_radar_version=EVENT_RADAR_VERSION,
            selector_version=SELECTOR_VERSION,
            coverage_manifest={},
            status="building",
            idempotency_key=key,
        )
        self._session.add(snapshot)
        await self._session.flush()

        eligible_symbols: list[str] = []
        for stock in stocks:
            eligible = stock.status == "listed" and stock.issuer_type == "general"
            if eligible:
                eligible_symbols.append(stock.symbol)
            reason = None
            if stock.status != "listed":
                reason = "not_currently_listed"
            elif stock.issuer_type != "general":
                reason = "unsupported_issuer_template"
            self._session.add(
                ScreeningSnapshotMemberRecord(
                    id=uuid4(),
                    snapshot_id=snapshot.id,
                    symbol=stock.symbol,
                    issuer_type=stock.issuer_type,
                    eligibility_status="eligible" if eligible else "excluded",
                    exclusion_reason=reason,
                )
            )

        facts: list[ScreeningSnapshotFactRecord] = []
        if eligible_symbols:
            metric_ranked = (
                select(
                    FundamentalMetricPointRecord.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=(
                            FundamentalMetricPointRecord.symbol,
                            FundamentalMetricPointRecord.code,
                        ),
                        order_by=(
                            FundamentalMetricPointRecord.period_end.desc(),
                            FundamentalMetricPointRecord.known_at.desc(),
                            FundamentalMetricPointRecord.id.asc(),
                        ),
                    )
                    .label("rank"),
                )
                .where(
                    FundamentalMetricPointRecord.symbol.in_(eligible_symbols),
                    FundamentalMetricPointRecord.code.in_(METRIC_CODES),
                    FundamentalMetricPointRecord.known_at <= cutoff,
                )
                .subquery()
            )
            metric_rows = (
                await self._session.scalars(
                    select(FundamentalMetricPointRecord).where(
                        FundamentalMetricPointRecord.id.in_(
                            select(metric_ranked.c.id).where(metric_ranked.c.rank == 1)
                        )
                    )
                )
            ).all()
            for metric_row in metric_rows:
                facts.append(
                    ScreeningSnapshotFactRecord(
                        id=uuid4(),
                        snapshot_id=snapshot.id,
                        symbol=metric_row.symbol,
                        criterion_key=f"metric:{metric_row.code}",
                        source_kind="metric",
                        status=metric_row.status,
                        metric_point_id=metric_row.id,
                    )
                )

            valuation_ranked = (
                select(
                    ValuationObservationRecord.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=(
                            ValuationObservationRecord.symbol,
                            ValuationObservationRecord.metric_code,
                        ),
                        order_by=(
                            ValuationObservationRecord.trade_date.desc(),
                            ValuationObservationRecord.collected_at.desc(),
                            ValuationObservationRecord.id.asc(),
                        ),
                    )
                    .label("rank"),
                )
                .where(
                    ValuationObservationRecord.symbol.in_(eligible_symbols),
                    ValuationObservationRecord.metric_code.in_(VALUATION_CODES),
                    ValuationObservationRecord.trade_date <= cutoff.date(),
                    ValuationObservationRecord.collected_at <= cutoff,
                )
                .subquery()
            )
            valuation_rows = (
                await self._session.scalars(
                    select(ValuationObservationRecord).where(
                        ValuationObservationRecord.id.in_(
                            select(valuation_ranked.c.id).where(valuation_ranked.c.rank == 1)
                        )
                    )
                )
            ).all()
            for valuation_row in valuation_rows:
                status = (
                    "invalid_input"
                    if valuation_row.metric_code in {"pe_ttm", "pcf"} and valuation_row.value <= 0
                    else "available"
                )
                facts.append(
                    ScreeningSnapshotFactRecord(
                        id=uuid4(),
                        snapshot_id=snapshot.id,
                        symbol=valuation_row.symbol,
                        criterion_key=f"metric:{valuation_row.metric_code}",
                        source_kind="valuation",
                        status=status,
                        valuation_observation_id=valuation_row.id,
                    )
                )

            peer_ranked = (
                select(
                    CompanyPeerMetricPositionRecord.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=(
                            CompanyPeerMetricPositionRecord.symbol,
                            CompanyPeerMetricPositionRecord.metric_code,
                        ),
                        order_by=(
                            PeerBenchmarkSnapshotRecord.knowledge_cutoff.desc(),
                            CompanyPeerMetricPositionRecord.id.asc(),
                        ),
                    )
                    .label("rank"),
                )
                .join(
                    PeerBenchmarkSnapshotRecord,
                    PeerBenchmarkSnapshotRecord.id
                    == CompanyPeerMetricPositionRecord.benchmark_snapshot_id,
                )
                .where(
                    CompanyPeerMetricPositionRecord.symbol.in_(eligible_symbols),
                    CompanyPeerMetricPositionRecord.metric_code.in_(PEER_METRIC_CODES),
                    PeerBenchmarkSnapshotRecord.knowledge_cutoff <= cutoff,
                )
                .subquery()
            )
            peer_rows = (
                await self._session.scalars(
                    select(CompanyPeerMetricPositionRecord).where(
                        CompanyPeerMetricPositionRecord.id.in_(
                            select(peer_ranked.c.id).where(peer_ranked.c.rank == 1)
                        )
                    )
                )
            ).all()
            for peer_row in peer_rows:
                facts.append(
                    ScreeningSnapshotFactRecord(
                        id=uuid4(),
                        snapshot_id=snapshot.id,
                        symbol=peer_row.symbol,
                        criterion_key=f"peer:{peer_row.metric_code}",
                        source_kind="peer",
                        status=peer_row.status,
                        peer_position_id=peer_row.id,
                    )
                )

            industry_ranked = (
                select(
                    IndustryMembershipRecord.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=IndustryMembershipRecord.symbol,
                        order_by=(
                            IndustryMembershipRecord.known_at.desc(),
                            IndustryMembershipRecord.id.asc(),
                        ),
                    )
                    .label("rank"),
                )
                .where(
                    IndustryMembershipRecord.symbol.in_(eligible_symbols),
                    IndustryMembershipRecord.taxonomy_code == PRIMARY_TAXONOMY_CODE,
                    IndustryMembershipRecord.taxonomy_version == PRIMARY_TAXONOMY_VERSION,
                    IndustryMembershipRecord.known_at <= cutoff,
                    or_(
                        IndustryMembershipRecord.valid_to.is_(None),
                        IndustryMembershipRecord.valid_to >= cutoff.date(),
                    ),
                )
                .subquery()
            )
            industry_rows = (
                await self._session.scalars(
                    select(IndustryMembershipRecord).where(
                        IndustryMembershipRecord.id.in_(
                            select(industry_ranked.c.id).where(industry_ranked.c.rank == 1)
                        )
                    )
                )
            ).all()
            for industry_row in industry_rows:
                facts.append(
                    ScreeningSnapshotFactRecord(
                        id=uuid4(),
                        snapshot_id=snapshot.id,
                        symbol=industry_row.symbol,
                        criterion_key="industry",
                        source_kind="industry",
                        status="available",
                        industry_membership_id=industry_row.id,
                    )
                )

            event_ranked = (
                select(
                    EventRadarSnapshotRecord.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=EventRadarSnapshotRecord.symbol,
                        order_by=(
                            EventRadarSnapshotRecord.knowledge_cutoff.desc(),
                            EventRadarSnapshotRecord.id.asc(),
                        ),
                    )
                    .label("rank"),
                )
                .where(
                    EventRadarSnapshotRecord.symbol.in_(eligible_symbols),
                    EventRadarSnapshotRecord.knowledge_cutoff <= cutoff,
                )
                .subquery()
            )
            event_rows = (
                await self._session.scalars(
                    select(EventRadarSnapshotRecord).where(
                        EventRadarSnapshotRecord.id.in_(
                            select(event_ranked.c.id).where(event_ranked.c.rank == 1)
                        )
                    )
                )
            ).all()
            for event_row in event_rows:
                status = (
                    "available"
                    if event_row.source_health == "healthy"
                    and event_row.coverage_status == "complete"
                    else "unknown"
                )
                for family in EVENT_FAMILIES:
                    facts.append(
                        ScreeningSnapshotFactRecord(
                            id=uuid4(),
                            snapshot_id=snapshot.id,
                            symbol=event_row.symbol,
                            criterion_key=f"event:{family}",
                            source_kind="event",
                            status=status,
                            event_radar_snapshot_id=event_row.id,
                        )
                    )

        self._session.add_all(facts)
        counts: dict[str, int] = defaultdict(int)
        status_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        criterion_available_counts: dict[str, int] = defaultdict(int)
        for fact in facts:
            status_counts[fact.source_kind][fact.status] += 1
            if fact.status == "available":
                counts[fact.source_kind] += 1
                criterion_available_counts[fact.criterion_key] += 1
        catalog = await self.catalog()
        snapshot.coverage_manifest = {
            "universe_count": len(stocks),
            "eligible_count": len(eligible_symbols),
            "excluded_count": len(stocks) - len(eligible_symbols),
            "fact_counts": dict(sorted(counts.items())),
            "fact_status_counts": {
                source: dict(sorted(statuses.items()))
                for source, statuses in sorted(status_counts.items())
            },
            "criterion_available_counts": dict(sorted(criterion_available_counts.items())),
            "catalog_version": catalog.catalog_version,
            "catalog_hash": catalog.catalog_hash,
            "criteria_contract_hash": catalog.criteria_contract_hash,
        }
        snapshot.status = "ready"
        await self._session.commit()
        return ScreeningBuildResult(
            status="succeeded",
            snapshot_id=snapshot.id,
            member_count=len(stocks),
            fact_count=len(facts),
            idempotency_key=key,
        )

    async def _latest_snapshot(self) -> ScreeningSnapshotRecord | None:
        snapshot: ScreeningSnapshotRecord | None = await self._session.scalar(
            select(ScreeningSnapshotRecord)
            .where(ScreeningSnapshotRecord.status == "ready")
            .order_by(
                ScreeningSnapshotRecord.knowledge_cutoff.desc(),
                ScreeningSnapshotRecord.created_at.desc(),
            )
            .limit(1)
        )
        return snapshot

    async def coverage(self) -> ScreenCoverageResponse:
        snapshot = await self._latest_snapshot()
        if snapshot is None:
            return ScreenCoverageResponse(
                status="not_built",
                limitations=["尚未构建可查询的筛选数据快照。"],
            )
        manifest = snapshot.coverage_manifest
        eligible = int(manifest.get("eligible_count", 0))
        facts, fact_status_counts, criterion_available_counts = await self._coverage_profile(
            snapshot
        )
        core_fact_count = facts.get("metric", 0) + facts.get("valuation", 0)
        expected_core_fact_count = eligible * (len(METRIC_CODES) + len(VALUATION_CODES))
        status: Literal["ready", "partial_coverage"] = (
            "ready"
            if eligible >= 30 and core_fact_count >= expected_core_fact_count
            else "partial_coverage"
        )
        return ScreenCoverageResponse(
            status=status,
            snapshot_id=snapshot.id,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            universe_count=int(manifest.get("universe_count", 0)),
            eligible_count=eligible,
            excluded_count=int(manifest.get("excluded_count", 0)),
            fact_counts=facts,
            fact_status_counts=fact_status_counts,
            criterion_available_counts=criterion_available_counts,
            taxonomy_code=snapshot.taxonomy_code,
            taxonomy_version=snapshot.taxonomy_version,
            limitations=[
                "结果仅代表快照已覆盖的数据范围。",
                "缺失、无效、不适用和来源覆盖不足均不会默认匹配。",
            ],
        )

    async def _coverage_profile(
        self, snapshot: ScreeningSnapshotRecord
    ) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, int]]:
        manifest = snapshot.coverage_manifest
        if "fact_status_counts" in manifest and "criterion_available_counts" in manifest:
            return (
                cast(dict[str, int], manifest.get("fact_counts", {})),
                cast(dict[str, dict[str, int]], manifest["fact_status_counts"]),
                cast(dict[str, int], manifest["criterion_available_counts"]),
            )
        rows = (
            await self._session.execute(
                select(
                    ScreeningSnapshotFactRecord.source_kind,
                    ScreeningSnapshotFactRecord.status,
                    ScreeningSnapshotFactRecord.criterion_key,
                    func.count(),
                )
                .where(ScreeningSnapshotFactRecord.snapshot_id == snapshot.id)
                .group_by(
                    ScreeningSnapshotFactRecord.source_kind,
                    ScreeningSnapshotFactRecord.status,
                    ScreeningSnapshotFactRecord.criterion_key,
                )
            )
        ).all()
        available_by_source: dict[str, int] = defaultdict(int)
        by_status: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        by_criterion: dict[str, int] = defaultdict(int)
        for source, status, criterion_key, count in rows:
            by_status[source][status] += count
            if status == "available":
                available_by_source[source] += count
                by_criterion[criterion_key] += count
        return (
            dict(sorted(available_by_source.items())),
            {key: dict(sorted(value.items())) for key, value in sorted(by_status.items())},
            dict(sorted(by_criterion.items())),
        )

    async def estimate_coverage(self, query: ScreenQuery) -> ScreenCoverageEstimateResponse:
        validation = self.validate(query)
        if not validation.valid:
            raise ValueError("invalid_screen_query")
        snapshot = await self._latest_snapshot()
        if snapshot is None:
            return ScreenCoverageEstimateResponse(limitations=["尚未构建可查询的筛选数据快照。"])
        eligible = int(snapshot.coverage_manifest.get("eligible_count", 0))
        _, _, available = await self._coverage_profile(snapshot)
        criteria: list[ScreenCriterionCoverage] = []
        keys: list[str] = []
        for criterion in query.filters:
            if isinstance(criterion, MetricCriterion):
                key = f"metric:{criterion.metric_code}"
                label = DISPLAY_NAMES[criterion.metric_code]
            elif isinstance(criterion, PeerCriterion):
                key = f"peer:{criterion.metric_code}"
                label = f"{DISPLAY_NAMES[criterion.metric_code]}同行分位"
            elif isinstance(criterion, IndustryCriterion):
                key, label = "industry", "行业分类"
            else:
                key = f"event:{criterion.event_family}"
                label = "公司事件覆盖"
            keys.append(key)
            count = min(eligible, int(available.get(key, 0)))
            ratio = Decimal(count) / Decimal(eligible) if eligible else Decimal(0)
            criteria.append(
                ScreenCriterionCoverage(
                    criterion_key=key,
                    label=label,
                    eligible_count=eligible,
                    available_count=count,
                    coverage_ratio=ratio,
                    status="available"
                    if count == eligible and eligible
                    else "partial"
                    if count
                    else "unavailable",
                )
            )
        all_available = 0
        if keys:
            all_available = int(
                await self._session.scalar(
                    select(func.count()).select_from(
                        select(ScreeningSnapshotFactRecord.symbol)
                        .where(
                            ScreeningSnapshotFactRecord.snapshot_id == snapshot.id,
                            ScreeningSnapshotFactRecord.status == "available",
                            ScreeningSnapshotFactRecord.criterion_key.in_(keys),
                        )
                        .group_by(ScreeningSnapshotFactRecord.symbol)
                        .having(
                            func.count(distinct(ScreeningSnapshotFactRecord.criterion_key))
                            == len(set(keys))
                        )
                        .subquery()
                    )
                )
                or 0
            )
        return ScreenCoverageEstimateResponse(
            snapshot_id=snapshot.id,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            eligible_count=eligible,
            criteria=criteria,
            all_criteria_available_count=all_available,
            limitations=["覆盖度仅表示条件所需事实可用，不代表一定满足阈值。"],
        )

    async def create_saved_screen(
        self, user_id: UUID, payload: SavedScreenCreate
    ) -> SavedScreenResponse:
        validation = self.validate(payload.query)
        if not validation.valid or validation.query_hash is None:
            raise ValueError("invalid_screen_query")
        count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(SavedScreenRecord)
                .where(SavedScreenRecord.user_id == user_id)
            )
            or 0
        )
        if self._access_control is None:
            raise RuntimeError("access_control_service_required")
        entitlements = await self._access_control.effective_entitlements(user_id)
        if count >= entitlements.limits["saved_screens"]:
            raise ValueError("saved_screen_limit_reached")
        if payload.source_parse_run_id is not None:
            parse_run = await self._session.scalar(
                select(NaturalLanguageScreenParseRunRecord).where(
                    NaturalLanguageScreenParseRunRecord.id == payload.source_parse_run_id,
                    NaturalLanguageScreenParseRunRecord.user_id == user_id,
                    NaturalLanguageScreenParseRunRecord.status == "succeeded",
                    NaturalLanguageScreenParseRunRecord.semantic_status == "ready",
                )
            )
            if parse_run is None:
                raise LookupError("source_parse_run_not_ready")
        catalog = await self.catalog()
        name = payload.name.strip()
        row = SavedScreenRecord(
            id=uuid4(),
            user_id=user_id,
            name=name,
            normalized_name=name.casefold(),
            description=payload.description.strip() if payload.description else None,
            canonical_query=_canonical(payload.query),
            query_hash=validation.query_hash,
            dsl_version=DSL_VERSION,
            catalog_version=catalog.catalog_version,
            catalog_hash=catalog.catalog_hash,
            criteria_contract_hash=catalog.criteria_contract_hash,
            source_kind="natural_language" if payload.source_parse_run_id else "builder",
            source_parse_run_id=payload.source_parse_run_id,
            original_text=payload.original_text.strip() if payload.original_text else None,
        )
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ValueError("saved_screen_name_exists") from error
        return self._saved_response(row, catalog)

    async def list_saved_screens(self, user_id: UUID) -> SavedScreenListResponse:
        rows = (
            await self._session.scalars(
                select(SavedScreenRecord)
                .where(SavedScreenRecord.user_id == user_id)
                .order_by(SavedScreenRecord.updated_at.desc(), SavedScreenRecord.id)
            )
        ).all()
        catalog = await self.catalog()
        return SavedScreenListResponse(
            items=[self._saved_response(row, catalog) for row in rows], total=len(rows)
        )

    async def get_saved_screen(
        self, user_id: UUID, saved_screen_id: UUID
    ) -> SavedScreenResponse | None:
        row = await self._session.scalar(
            select(SavedScreenRecord).where(
                SavedScreenRecord.id == saved_screen_id, SavedScreenRecord.user_id == user_id
            )
        )
        return self._saved_response(row, await self.catalog()) if row else None

    async def update_saved_screen(
        self, user_id: UUID, saved_screen_id: UUID, payload: SavedScreenUpdate
    ) -> SavedScreenResponse | None:
        row = await self._session.scalar(
            select(SavedScreenRecord).where(
                SavedScreenRecord.id == saved_screen_id, SavedScreenRecord.user_id == user_id
            )
        )
        if row is None:
            return None
        catalog = await self.catalog()
        if payload.name is not None:
            row.name = payload.name.strip()
            row.normalized_name = row.name.casefold()
        if "description" in payload.model_fields_set:
            row.description = payload.description.strip() if payload.description else None
        if payload.query is not None:
            validation = self.validate(payload.query)
            if not validation.valid or validation.query_hash is None:
                raise ValueError("invalid_screen_query")
            row.canonical_query = _canonical(payload.query)
            row.query_hash = validation.query_hash
            row.dsl_version = DSL_VERSION
            row.catalog_version = catalog.catalog_version
            row.catalog_hash = catalog.catalog_hash
            row.criteria_contract_hash = catalog.criteria_contract_hash
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ValueError("saved_screen_name_exists") from error
        return self._saved_response(row, catalog)

    async def delete_saved_screen(self, user_id: UUID, saved_screen_id: UUID) -> bool:
        deleted = await self._session.scalar(
            delete(SavedScreenRecord)
            .where(SavedScreenRecord.id == saved_screen_id, SavedScreenRecord.user_id == user_id)
            .returning(SavedScreenRecord.id)
        )
        await self._session.commit()
        return deleted is not None

    def _saved_response(
        self, row: SavedScreenRecord, catalog: ScreenCatalogResponse
    ) -> SavedScreenResponse:
        query: ScreenQuery | None = None
        validation: ScreenValidationResponse | None = None
        try:
            query = ScreenQuery.model_validate(row.canonical_query)
            validation = self.validate(query)
        except ValueError:
            pass
        if query is None or validation is None or not validation.valid:
            compatibility: Literal["compatible", "reconfirmation_required", "unsupported"] = (
                "unsupported"
            )
            reason = "saved_query_no_longer_supported"
            query = ScreenQuery.model_validate(row.canonical_query)
        elif (
            row.catalog_hash != catalog.catalog_hash
            or row.criteria_contract_hash != catalog.criteria_contract_hash
        ):
            compatibility = "reconfirmation_required"
            reason = "screening_catalog_changed"
        else:
            compatibility = "compatible"
            reason = None
        return SavedScreenResponse(
            id=row.id,
            name=row.name,
            description=row.description,
            query=query,
            query_hash=row.query_hash,
            source_kind=cast(Any, row.source_kind),
            original_text=row.original_text,
            compatibility=compatibility,
            compatibility_reason=reason,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create_execution(
        self,
        user_id: UUID,
        query: ScreenQuery,
        *,
        saved_screen_id: UUID | None = None,
        confirmed_parse_run_id: UUID | None = None,
    ) -> ScreenExecutionResponse:
        validation = self.validate(query)
        if not validation.valid or validation.query_hash is None:
            raise ValueError("invalid_screen_query")
        snapshot = await self._latest_snapshot()
        if snapshot is None:
            raise LookupError("screening_snapshot_not_built")
        if saved_screen_id is not None:
            saved = await self._session.scalar(
                select(SavedScreenRecord).where(
                    SavedScreenRecord.id == saved_screen_id, SavedScreenRecord.user_id == user_id
                )
            )
            if saved is None:
                raise LookupError("saved_screen_not_found")
        if confirmed_parse_run_id is not None:
            parse_run = await self._session.scalar(
                select(NaturalLanguageScreenParseRunRecord).where(
                    NaturalLanguageScreenParseRunRecord.id == confirmed_parse_run_id,
                    NaturalLanguageScreenParseRunRecord.user_id == user_id,
                    NaturalLanguageScreenParseRunRecord.status == "succeeded",
                    NaturalLanguageScreenParseRunRecord.semantic_status == "ready",
                )
            )
            if parse_run is None:
                raise LookupError("confirmed_parse_run_not_ready")
            parsed_query = ScreenQuery.model_validate(
                cast(dict[str, Any], parse_run.output_document)["query"]
            )
            parsed_validation = self.validate(parsed_query)
            if parsed_validation.query_hash != validation.query_hash:
                raise ValueError("confirmed_parse_query_mismatch")
        existing = await self._session.scalar(
            select(ScreenExecutionRecord).where(
                ScreenExecutionRecord.user_id == user_id,
                ScreenExecutionRecord.screening_snapshot_id == snapshot.id,
                ScreenExecutionRecord.query_hash == validation.query_hash,
                ScreenExecutionRecord.engine_version == ENGINE_VERSION,
            )
        )
        reused = existing is not None
        if existing is None:
            existing = ScreenExecutionRecord(
                id=uuid4(),
                user_id=user_id,
                screening_snapshot_id=snapshot.id,
                canonical_query=_canonical(query),
                query_hash=validation.query_hash,
                engine_version=ENGINE_VERSION,
                status="pending",
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=LEASE_MINUTES),
            )
            self._session.add(existing)
            await self._session.flush()
        request = ScreenExecutionRequestRecord(
            id=uuid4(),
            user_id=user_id,
            execution_id=existing.id,
            saved_screen_id=saved_screen_id,
            confirmed_parse_run_id=confirmed_parse_run_id,
            request_source=(
                "saved_screen"
                if saved_screen_id
                else "natural_language"
                if confirmed_parse_run_id
                else "builder"
            ),
            reused_execution=reused,
        )
        self._session.add(request)
        await self._session.commit()
        return self._execution_response(existing, snapshot, request_id=request.id, reused=reused)

    async def get_execution(
        self, user_id: UUID, execution_id: UUID
    ) -> ScreenExecutionResponse | None:
        row = await self._session.scalar(
            select(ScreenExecutionRecord).where(
                ScreenExecutionRecord.id == execution_id,
                ScreenExecutionRecord.user_id == user_id,
            )
        )
        if row is None:
            return None
        snapshot = await self._session.get(ScreeningSnapshotRecord, row.screening_snapshot_id)
        if snapshot is None:
            return None
        return self._execution_response(row, snapshot)

    async def list_executions(self, user_id: UUID, limit: int = 20) -> ScreenExecutionListResponse:
        rows = (
            await self._session.scalars(
                select(ScreenExecutionRecord)
                .where(ScreenExecutionRecord.user_id == user_id)
                .order_by(ScreenExecutionRecord.created_at.desc(), ScreenExecutionRecord.id)
                .limit(limit)
            )
        ).all()
        items: list[ScreenExecutionResponse] = []
        for row in rows:
            snapshot = await self._session.get(ScreeningSnapshotRecord, row.screening_snapshot_id)
            if snapshot is not None:
                items.append(self._execution_response(row, snapshot))
        return ScreenExecutionListResponse(items=items, total=len(items))

    def _execution_response(
        self,
        row: ScreenExecutionRecord,
        snapshot: ScreeningSnapshotRecord,
        *,
        request_id: UUID | None = None,
        reused: bool = False,
    ) -> ScreenExecutionResponse:
        return ScreenExecutionResponse(
            id=row.id,
            screening_snapshot_id=row.screening_snapshot_id,
            status=cast(Any, row.status),
            query_hash=row.query_hash,
            engine_version=row.engine_version,
            knowledge_cutoff=snapshot.knowledge_cutoff,
            result_count=row.result_count,
            evaluated_count=row.evaluated_count,
            unknown_count=row.unknown_count,
            excluded_count=row.excluded_count,
            error_summary=row.error_summary,
            created_at=row.created_at,
            finished_at=row.finished_at,
            request_id=request_id,
            reused=reused,
        )

    async def execute(self, execution_id: UUID) -> ScreenExecutionResponse:
        now = datetime.now(UTC)
        claimed = await self._session.scalar(
            update(ScreenExecutionRecord)
            .where(
                ScreenExecutionRecord.id == execution_id,
                or_(
                    ScreenExecutionRecord.status == "pending",
                    and_(
                        ScreenExecutionRecord.status == "running",
                        ScreenExecutionRecord.lease_expires_at < now,
                    ),
                ),
            )
            .values(
                status="running",
                started_at=now,
                lease_expires_at=now + timedelta(minutes=LEASE_MINUTES),
                error_summary=None,
            )
            .returning(ScreenExecutionRecord)
        )
        await self._session.commit()
        if claimed is None:
            row = await self._session.get(ScreenExecutionRecord, execution_id)
            if row is None:
                raise LookupError("screen_execution_not_found")
            snapshot = await self._session.get(ScreeningSnapshotRecord, row.screening_snapshot_id)
            if snapshot is None:
                raise LookupError("screening_snapshot_not_found")
            return self._execution_response(row, snapshot)
        snapshot = await self._session.get(ScreeningSnapshotRecord, claimed.screening_snapshot_id)
        if snapshot is None:
            raise LookupError("screening_snapshot_not_found")
        try:
            query = ScreenQuery.model_validate(claimed.canonical_query)
            await self._evaluate(claimed, snapshot, query)
        except Exception as exc:
            await self._session.execute(
                update(ScreenExecutionRecord)
                .where(ScreenExecutionRecord.id == execution_id)
                .values(
                    status="failed",
                    error_summary=type(exc).__name__,
                    finished_at=datetime.now(UTC),
                )
            )
            await self._session.commit()
            raise
        refreshed = await self._session.get(ScreenExecutionRecord, execution_id)
        assert refreshed is not None
        return self._execution_response(refreshed, snapshot)

    async def _evaluate(
        self,
        execution: ScreenExecutionRecord,
        snapshot: ScreeningSnapshotRecord,
        query: ScreenQuery,
    ) -> None:
        members = (
            await self._session.scalars(
                select(ScreeningSnapshotMemberRecord).where(
                    ScreeningSnapshotMemberRecord.snapshot_id == snapshot.id,
                    ScreeningSnapshotMemberRecord.eligibility_status == "eligible",
                )
            )
        ).all()
        facts = (
            await self._session.scalars(
                select(ScreeningSnapshotFactRecord).where(
                    ScreeningSnapshotFactRecord.snapshot_id == snapshot.id
                )
            )
        ).all()
        fact_map = {(row.symbol, row.criterion_key): row for row in facts}
        metric_ids = [row.metric_point_id for row in facts if row.metric_point_id]
        valuation_ids = [
            row.valuation_observation_id for row in facts if row.valuation_observation_id
        ]
        peer_ids = [row.peer_position_id for row in facts if row.peer_position_id]
        industry_ids = [row.industry_membership_id for row in facts if row.industry_membership_id]
        event_ids = [row.event_radar_snapshot_id for row in facts if row.event_radar_snapshot_id]
        metric_rows = (
            (
                await self._session.scalars(
                    select(FundamentalMetricPointRecord).where(
                        FundamentalMetricPointRecord.id.in_(metric_ids)
                    )
                )
            ).all()
            if metric_ids
            else []
        )
        valuation_rows = (
            (
                await self._session.scalars(
                    select(ValuationObservationRecord).where(
                        ValuationObservationRecord.id.in_(valuation_ids)
                    )
                )
            ).all()
            if valuation_ids
            else []
        )
        peer_rows = (
            (
                await self._session.scalars(
                    select(CompanyPeerMetricPositionRecord).where(
                        CompanyPeerMetricPositionRecord.id.in_(peer_ids)
                    )
                )
            ).all()
            if peer_ids
            else []
        )
        industry_rows = (
            (
                await self._session.scalars(
                    select(IndustryMembershipRecord).where(
                        IndustryMembershipRecord.id.in_(industry_ids)
                    )
                )
            ).all()
            if industry_ids
            else []
        )
        event_rows = (
            (
                await self._session.scalars(
                    select(EventRadarSnapshotRecord).where(
                        EventRadarSnapshotRecord.id.in_(event_ids)
                    )
                )
            ).all()
            if event_ids
            else []
        )
        metrics = {row.id: row for row in metric_rows}
        valuations = {row.id: row for row in valuation_rows}
        peers = {row.id: row for row in peer_rows}
        industries = {row.id: row for row in industry_rows}
        events = {row.id: row for row in event_rows}
        event_occurrences: dict[tuple[UUID, str], list[datetime]] = defaultdict(list)
        if event_ids:
            for snapshot_id, family, known_at in (
                await self._session.execute(
                    select(
                        EventRadarSnapshotItemRecord.snapshot_id,
                        CorporateEventRecord.event_family,
                        CorporateEventRecord.known_at,
                    )
                    .join(
                        CorporateEventRecord,
                        CorporateEventRecord.id == EventRadarSnapshotItemRecord.event_id,
                    )
                    .where(EventRadarSnapshotItemRecord.snapshot_id.in_(event_ids))
                )
            ).all():
                event_occurrences[(snapshot_id, family)].append(known_at)

        candidates: list[tuple[str, Decimal | None, list[ScreenMatchedCondition]]] = []
        unknown_count = 0
        excluded_count = 0
        for member in members:
            matched: list[ScreenMatchedCondition] = []
            has_unknown = False
            has_miss = False
            for criterion in query.filters:
                result = self._evaluate_criterion(
                    member.symbol,
                    criterion,
                    fact_map,
                    metrics,
                    valuations,
                    peers,
                    industries,
                    events,
                    event_occurrences,
                )
                if result is None:
                    has_unknown = True
                    break
                if result is False:
                    has_miss = True
                    break
                matched.append(result)
            if has_unknown:
                unknown_count += 1
                continue
            if has_miss:
                excluded_count += 1
                continue
            sort_value = self._sort_value(
                member.symbol, query.sort.field, fact_map, metrics, valuations
            )
            candidates.append((member.symbol, sort_value, matched))

        reverse = query.sort.direction == "desc"
        if query.sort.field == "symbol":
            candidates.sort(key=lambda item: item[0], reverse=reverse)
        else:
            with_value = [row for row in candidates if row[1] is not None]
            without_value = [row for row in candidates if row[1] is None]
            with_value.sort(key=lambda item: (cast(Decimal, item[1]), item[0]), reverse=reverse)
            without_value.sort(key=lambda item: item[0])
            candidates = with_value + without_value
        await self._session.execute(
            delete(ScreenResultRecord).where(ScreenResultRecord.execution_id == execution.id)
        )
        for ordinal, (symbol, sort_value, conditions) in enumerate(candidates, start=1):
            self._session.add(
                ScreenResultRecord(
                    id=uuid4(),
                    user_id=execution.user_id,
                    execution_id=execution.id,
                    symbol=symbol,
                    ordinal=ordinal,
                    sort_value=sort_value,
                    matched_condition_manifest={
                        "items": [item.model_dump(mode="json") for item in conditions]
                    },
                    evidence_refs={
                        "items": [
                            {"type": item.evidence_type, "id": str(item.evidence_id)}
                            for item in conditions
                        ]
                    },
                )
            )
        await self._session.execute(
            update(ScreenExecutionRecord)
            .where(ScreenExecutionRecord.id == execution.id)
            .values(
                status="succeeded",
                result_count=len(candidates),
                evaluated_count=len(members),
                unknown_count=unknown_count,
                excluded_count=excluded_count,
                finished_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    def _evaluate_criterion(
        self,
        symbol: str,
        criterion: Any,
        facts: dict[tuple[str, str], ScreeningSnapshotFactRecord],
        metrics: dict[UUID, FundamentalMetricPointRecord],
        valuations: dict[UUID, ValuationObservationRecord],
        peers: dict[UUID, CompanyPeerMetricPositionRecord],
        industries: dict[UUID, IndustryMembershipRecord],
        events: dict[UUID, EventRadarSnapshotRecord],
        event_occurrences: dict[tuple[UUID, str], list[datetime]],
    ) -> ScreenMatchedCondition | Literal[False] | None:
        if isinstance(criterion, MetricCriterion):
            fact = facts.get((symbol, f"metric:{criterion.metric_code}"))
            if fact is None or fact.status != "available":
                return None
            if fact.metric_point_id:
                source = metrics[fact.metric_point_id]
                value, unit, effective = source.value, source.unit, source.period_end
                evidence_type, evidence_id = "fundamental_metric_point", source.id
            elif fact.valuation_observation_id:
                source_v = valuations[fact.valuation_observation_id]
                value, unit, effective = source_v.value, source_v.unit, source_v.trade_date
                evidence_type, evidence_id = "valuation_observation", source_v.id
            else:
                return None
            if value is None:
                return None
            if not _compare(value, criterion.operator, criterion.value, criterion.upper_value):
                return False
            return ScreenMatchedCondition(
                criterion_key=f"metric:{criterion.metric_code}",
                label=DISPLAY_NAMES[criterion.metric_code],
                value=value,
                unit=unit,
                effective_on=effective,
                evidence_type=evidence_type,
                evidence_id=evidence_id,
            )
        if isinstance(criterion, PeerCriterion):
            fact = facts.get((symbol, f"peer:{criterion.metric_code}"))
            if fact is None or fact.status != "available" or not fact.peer_position_id:
                return None
            source_p = peers[fact.peer_position_id]
            value = source_p.numeric_percentile
            if value is None:
                return None
            if not _compare(value, criterion.operator, criterion.value, criterion.upper_value):
                return False
            return ScreenMatchedCondition(
                criterion_key=f"peer:{criterion.metric_code}",
                label=f"{DISPLAY_NAMES[criterion.metric_code]}同行分位",
                value=value,
                unit="percentile",
                evidence_type="company_peer_metric_position",
                evidence_id=source_p.id,
            )
        if isinstance(criterion, IndustryCriterion):
            fact = facts.get((symbol, "industry"))
            if fact is None or fact.status != "available" or not fact.industry_membership_id:
                return None
            source_i = industries[fact.industry_membership_id]
            if source_i.industry_code not in criterion.industry_codes:
                return False
            return ScreenMatchedCondition(
                criterion_key="industry",
                label="行业分类",
                value=source_i.industry_code,
                evidence_type="industry_membership",
                evidence_id=source_i.id,
            )
        if isinstance(criterion, EventCriterion):
            fact = facts.get((symbol, f"event:{criterion.event_family}"))
            if fact is None or fact.status != "available" or not fact.event_radar_snapshot_id:
                return None
            source_e = events[fact.event_radar_snapshot_id]
            window_start = source_e.knowledge_cutoff - timedelta(days=criterion.within_days)
            exists = any(
                window_start <= known_at <= source_e.knowledge_cutoff
                for known_at in event_occurrences.get((source_e.id, criterion.event_family), [])
            )
            passed = exists if criterion.mode == "exists" else not exists
            if not passed:
                return False
            return ScreenMatchedCondition(
                criterion_key=f"event:{criterion.event_family}",
                label="事件覆盖条件",
                value=exists,
                evidence_type="event_radar_snapshot",
                evidence_id=source_e.id,
            )
        return None

    def _sort_value(
        self,
        symbol: str,
        field: str,
        facts: dict[tuple[str, str], ScreeningSnapshotFactRecord],
        metrics: dict[UUID, FundamentalMetricPointRecord],
        valuations: dict[UUID, ValuationObservationRecord],
    ) -> Decimal | None:
        if field == "symbol":
            return None
        fact = facts.get((symbol, f"metric:{field}"))
        if not fact or fact.status != "available":
            return None
        if fact.metric_point_id:
            return metrics[fact.metric_point_id].value
        if fact.valuation_observation_id:
            return valuations[fact.valuation_observation_id].value
        return None

    async def results(
        self, user_id: UUID, execution_id: UUID, *, cursor: str | None, limit: int
    ) -> ScreenResultListResponse | None:
        execution = await self._session.scalar(
            select(ScreenExecutionRecord).where(
                ScreenExecutionRecord.id == execution_id,
                ScreenExecutionRecord.user_id == user_id,
            )
        )
        if execution is None:
            return None
        start = _decode_cursor(cursor) if cursor else 0
        rows = (
            await self._session.execute(
                select(ScreenResultRecord, StockRecord)
                .join(StockRecord, StockRecord.symbol == ScreenResultRecord.symbol)
                .where(
                    ScreenResultRecord.execution_id == execution_id,
                    ScreenResultRecord.user_id == user_id,
                    ScreenResultRecord.ordinal > start,
                )
                .order_by(ScreenResultRecord.ordinal)
                .limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        symbols = [result.symbol for result, _ in rows]
        memberships = (
            set(
                (
                    await self._session.scalars(
                        select(WatchlistItemRecord.symbol)
                        .join(WatchlistRecord)
                        .where(
                            WatchlistRecord.user_id == user_id,
                            WatchlistItemRecord.symbol.in_(symbols),
                        )
                    )
                ).all()
            )
            if symbols
            else set()
        )
        industry_ids = [
            UUID(item["evidence_id"])
            for result, _ in rows
            for item in result.matched_condition_manifest.get("items", [])
            if item.get("evidence_type") == "industry_membership"
        ]
        industry_memberships = (
            (
                await self._session.scalars(
                    select(IndustryMembershipRecord).where(
                        IndustryMembershipRecord.id.in_(industry_ids)
                    )
                )
            ).all()
            if industry_ids
            else []
        )
        industry_codes = {row.symbol: row.industry_code for row in industry_memberships}
        industry_name_rows = (
            await self._session.execute(
                select(IndustryRecord.code, IndustryRecord.name).where(
                    IndustryRecord.taxonomy_code == PRIMARY_TAXONOMY_CODE,
                    IndustryRecord.taxonomy_version == PRIMARY_TAXONOMY_VERSION,
                )
            )
        ).all()
        industry_names: dict[str, str] = {code: name for code, name in industry_name_rows}
        items = [
            ScreenResultItem(
                symbol=result.symbol,
                stock_name=stock.name,
                exchange=stock.exchange,
                industry_name=industry_names.get(industry_codes.get(result.symbol, "")),
                ordinal=result.ordinal,
                matched_conditions=[
                    ScreenMatchedCondition.model_validate(item)
                    for item in result.matched_condition_manifest.get("items", [])
                ],
                research_path=f"/stock/{result.symbol}",
                is_in_watchlist=result.symbol in memberships,
            )
            for result, stock in rows
        ]
        snapshot = await self._session.get(ScreeningSnapshotRecord, execution.screening_snapshot_id)
        assert snapshot is not None
        return ScreenResultListResponse(
            execution_id=execution_id,
            query_cutoff=snapshot.knowledge_cutoff,
            items=items,
            total=execution.result_count,
            next_cursor=_encode_cursor(rows[-1][0].ordinal) if has_more and rows else None,
        )
