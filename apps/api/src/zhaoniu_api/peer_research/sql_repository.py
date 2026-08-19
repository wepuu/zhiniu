from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.db import (
    CompanyPeerMetricPositionRecord,
    FundamentalMetricPointRecord,
    IndustryMembershipRecord,
    IndustryRecord,
    IndustryTaxonomyRecord,
    PeerBenchmarkInputRecord,
    PeerBenchmarkMetricResultRecord,
    PeerBenchmarkRunRecord,
    PeerBenchmarkSnapshotRecord,
    StockRecord,
    ValuationObservationRecord,
)
from zhaoniu_api.peer_research.engine import FUNDAMENTAL_CODES, METRIC_DIMENSIONS, VALUATION_CODES
from zhaoniu_api.peer_research.models import (
    PEER_PRODUCER_VERSION,
    PEER_SCHEMA_VERSION,
    PRIMARY_TAXONOMY_CODE,
    PRIMARY_TAXONOMY_VERSION,
    ComparableMetricInput,
    IndustryResponse,
    IndustryTaxonomy,
    PeerBenchmarkEvidenceSummary,
    PeerBenchmarkResult,
    PeerComparisonEnvelope,
    PeerComparisonStatus,
    PeerMetricComparisonResponse,
    PeerMetricKind,
    PeerStockResponse,
    PeerUniverse,
    PeerUniverseResponse,
)

DEV_INDUSTRY_SEEDS: dict[str, tuple[str, str]] = {
    "600519.SH": ("dev_baijiu", "白酒"),
    "000858.SZ": ("dev_baijiu", "白酒"),
    "000568.SZ": ("dev_baijiu", "白酒"),
    "600809.SH": ("dev_baijiu", "白酒"),
    "000596.SZ": ("dev_baijiu", "白酒"),
    "603369.SH": ("dev_baijiu", "白酒"),
    "600702.SH": ("dev_baijiu", "白酒"),
    "603589.SH": ("dev_baijiu", "白酒"),
    "000799.SZ": ("dev_baijiu", "白酒"),
    "600779.SH": ("dev_baijiu", "白酒"),
    "300750.SZ": ("dev_battery", "动力电池"),
    "002594.SZ": ("dev_battery", "动力电池"),
    "300014.SZ": ("dev_battery", "动力电池"),
    "002812.SZ": ("dev_battery", "动力电池"),
    "688005.SH": ("dev_battery", "动力电池"),
    "300207.SZ": ("dev_battery", "动力电池"),
    "002709.SZ": ("dev_battery", "动力电池"),
    "688567.SH": ("dev_battery", "动力电池"),
    "301358.SZ": ("dev_battery", "动力电池"),
}


class SQLAlchemyPeerResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_from_stock_master(self) -> int:
        now = datetime.now(UTC)
        taxonomy = IndustryTaxonomy(
            code=PRIMARY_TAXONOMY_CODE,
            name="AKShare stock master industry field (development taxonomy)",
            version=PRIMARY_TAXONOMY_VERSION,
            source="stock_master_or_phase6_dev_seed",
            source_reference=(
                "stocks.industry_code when populated; otherwise explicit "
                "phase6_dev_seed acceptance mappings"
            ),
            commercial_use_status="TBD / requires legal review",
            redistribution_status="TBD / requires legal review",
        )
        await self._session.execute(
            insert(IndustryTaxonomyRecord)
            .values(
                code=taxonomy.code,
                name=taxonomy.name,
                version=taxonomy.version,
                source=taxonomy.source,
                source_reference=taxonomy.source_reference,
                commercial_use_status=taxonomy.commercial_use_status,
                redistribution_status=taxonomy.redistribution_status,
            )
            .on_conflict_do_update(
                constraint="uq_industry_taxonomy_identity",
                set_={
                    "name": taxonomy.name,
                    "source": taxonomy.source,
                    "source_reference": taxonomy.source_reference,
                    "commercial_use_status": taxonomy.commercial_use_status,
                    "redistribution_status": taxonomy.redistribution_status,
                },
            )
        )
        rows = (await self._session.execute(select(StockRecord))).scalars()
        stocks = list(rows)
        stock_industries: dict[str, tuple[str, str, str]] = {}
        for stock in stocks:
            if stock.industry_code:
                stock_industries[stock.symbol] = (
                    _industry_code(stock.industry_code),
                    stock.industry_code,
                    "stocks.industry_code",
                )
            elif stock.symbol in DEV_INDUSTRY_SEEDS:
                code, name = DEV_INDUSTRY_SEEDS[stock.symbol]
                stock_industries[stock.symbol] = (code, name, "phase6_dev_seed")
        industries = sorted({(code, name) for code, name, _ in stock_industries.values()})
        for code, name in industries:
            await self._session.execute(
                insert(IndustryRecord)
                .values(
                    taxonomy_code=PRIMARY_TAXONOMY_CODE,
                    taxonomy_version=PRIMARY_TAXONOMY_VERSION,
                    code=code,
                    name=name,
                    level=1,
                )
                .on_conflict_do_update(
                    constraint="uq_industry_identity",
                    set_={"name": name, "level": 1},
                )
            )
        written = 0
        for stock in stocks:
            industry = stock_industries.get(stock.symbol)
            if industry is None:
                continue
            code, name, source_reference = industry
            lineage = _hash(
                {
                    "symbol": stock.symbol,
                    "industry_code": code,
                    "industry_name": name,
                    "taxonomy": PRIMARY_TAXONOMY_CODE,
                    "taxonomy_version": PRIMARY_TAXONOMY_VERSION,
                    "source_reference": source_reference,
                }
            )
            result = await self._session.execute(
                insert(IndustryMembershipRecord)
                .values(
                    symbol=stock.symbol,
                    industry_code=code,
                    taxonomy_code=PRIMARY_TAXONOMY_CODE,
                    taxonomy_version=PRIMARY_TAXONOMY_VERSION,
                    source="stock_master",
                    source_reference=source_reference,
                    valid_from=stock.list_date,
                    valid_to=None,
                    known_at=stock.collected_at,
                    ingested_at=now,
                    lineage_hash=lineage,
                )
                .on_conflict_do_nothing(
                    constraint="uq_industry_membership_identity",
                )
                .returning(IndustryMembershipRecord.id)
            )
            if result.scalar_one_or_none() is not None:
                written += 1
        await self._session.commit()
        return written

    async def resolve_universe(self, canonical_symbol: str, cutoff: datetime) -> PeerUniverse:
        stock = await self._session.get(StockRecord, canonical_symbol)
        if stock is None:
            return PeerUniverse(
                symbol=canonical_symbol,
                taxonomy_code=PRIMARY_TAXONOMY_CODE,
                taxonomy_version=PRIMARY_TAXONOMY_VERSION,
                industry_code=None,
                industry_name=None,
                peer_symbols=(),
                peer_universe_fingerprint="",
                status=PeerComparisonStatus.NOT_BUILT,
                reason="stock_not_found",
            )
        if stock.issuer_type != "general":
            return PeerUniverse(
                symbol=canonical_symbol,
                taxonomy_code=PRIMARY_TAXONOMY_CODE,
                taxonomy_version=PRIMARY_TAXONOMY_VERSION,
                industry_code=None,
                industry_name=None,
                peer_symbols=(),
                peer_universe_fingerprint="",
                status=PeerComparisonStatus.UNSUPPORTED_TEMPLATE,
                reason="issuer_template_not_supported",
            )
        membership = (
            await self._session.execute(
                select(IndustryMembershipRecord)
                .where(
                    IndustryMembershipRecord.symbol == canonical_symbol,
                    IndustryMembershipRecord.taxonomy_code == PRIMARY_TAXONOMY_CODE,
                    IndustryMembershipRecord.taxonomy_version == PRIMARY_TAXONOMY_VERSION,
                    IndustryMembershipRecord.known_at <= cutoff,
                    or_(
                        IndustryMembershipRecord.valid_to.is_(None),
                        IndustryMembershipRecord.valid_to >= cutoff.date(),
                    ),
                )
                .order_by(IndustryMembershipRecord.known_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if membership is None:
            return PeerUniverse(
                symbol=canonical_symbol,
                taxonomy_code=PRIMARY_TAXONOMY_CODE,
                taxonomy_version=PRIMARY_TAXONOMY_VERSION,
                industry_code=None,
                industry_name=None,
                peer_symbols=(),
                peer_universe_fingerprint="",
                status=PeerComparisonStatus.MISSING_INDUSTRY,
                reason="industry_membership_missing",
            )
        industry = (
            await self._session.execute(
                select(IndustryRecord).where(
                    IndustryRecord.taxonomy_code == membership.taxonomy_code,
                    IndustryRecord.taxonomy_version == membership.taxonomy_version,
                    IndustryRecord.code == membership.industry_code,
                )
            )
        ).scalar_one()
        peer_rows = (
            await self._session.execute(
                select(IndustryMembershipRecord.symbol)
                .join(StockRecord, StockRecord.symbol == IndustryMembershipRecord.symbol)
                .where(
                    IndustryMembershipRecord.taxonomy_code == membership.taxonomy_code,
                    IndustryMembershipRecord.taxonomy_version == membership.taxonomy_version,
                    IndustryMembershipRecord.industry_code == membership.industry_code,
                    IndustryMembershipRecord.known_at <= cutoff,
                    StockRecord.status == "listed",
                    StockRecord.issuer_type == stock.issuer_type,
                    StockRecord.symbol != canonical_symbol,
                )
                .distinct()
                .order_by(IndustryMembershipRecord.symbol)
            )
        ).scalars()
        peers = tuple(peer_rows)
        fingerprint = _hash(
            {
                "symbol": canonical_symbol,
                "taxonomy": membership.taxonomy_code,
                "taxonomy_version": membership.taxonomy_version,
                "industry_code": membership.industry_code,
                "peer_symbols": peers,
            }
        )
        return PeerUniverse(
            symbol=canonical_symbol,
            taxonomy_code=membership.taxonomy_code,
            taxonomy_version=membership.taxonomy_version,
            industry_code=membership.industry_code,
            industry_name=industry.name,
            peer_symbols=peers,
            peer_universe_fingerprint=fingerprint,
            status=PeerComparisonStatus.AVAILABLE,
        )

    async def peer_universe_response(
        self, canonical_symbol: str, cutoff: datetime
    ) -> PeerUniverseResponse:
        universe = await self.resolve_universe(canonical_symbol, cutoff)
        stocks = []
        if universe.peer_symbols:
            rows = (
                await self._session.execute(
                    select(StockRecord)
                    .where(StockRecord.symbol.in_(universe.peer_symbols))
                    .order_by(StockRecord.symbol)
                )
            ).scalars()
            stocks = [
                PeerStockResponse(
                    symbol=row.symbol,
                    name=row.name,
                    exchange=row.exchange,
                    issuer_type=row.issuer_type,
                )
                for row in rows
            ]
        return PeerUniverseResponse(
            symbol=canonical_symbol.split(".")[0],
            canonical_symbol=canonical_symbol,
            status=universe.status,
            reason=universe.reason,
            industry=await self._industry_response(universe),
            peer_universe_fingerprint=universe.peer_universe_fingerprint or None,
            sample_size=len(stocks),
            stocks=stocks,
        )

    async def list_inputs(
        self, symbols: tuple[str, ...], cutoff: datetime
    ) -> list[ComparableMetricInput]:
        if not symbols:
            return []
        points = (
            await self._session.execute(
                select(FundamentalMetricPointRecord).where(
                    FundamentalMetricPointRecord.symbol.in_(symbols),
                    FundamentalMetricPointRecord.code.in_(FUNDAMENTAL_CODES),
                    FundamentalMetricPointRecord.status == "available",
                    FundamentalMetricPointRecord.value.is_not(None),
                    FundamentalMetricPointRecord.known_at <= cutoff,
                )
            )
        ).scalars()
        inputs = [
            ComparableMetricInput(
                symbol=row.symbol,
                metric_code=row.code,
                value=row.value,
                unit=row.unit,
                period_end=row.period_end,
                fiscal_period=row.fiscal_period,
                basis=row.basis,
                metric_version=row.metric_version,
                known_at=row.known_at,
                source_id=row.id,
                source_kind=PeerMetricKind.FUNDAMENTAL,
            )
            for row in points
            if row.value is not None
        ]
        valuations = (
            await self._session.execute(
                select(ValuationObservationRecord).where(
                    ValuationObservationRecord.symbol.in_(symbols),
                    ValuationObservationRecord.metric_code.in_(VALUATION_CODES),
                    ValuationObservationRecord.collected_at <= cutoff,
                )
            )
        ).scalars()
        inputs.extend(
            ComparableMetricInput(
                symbol=row.symbol,
                metric_code=row.metric_code,
                value=row.value,
                unit=row.unit,
                period_end=row.trade_date,
                fiscal_period="trade_date",
                basis="trade_date",
                metric_version=row.provider,
                known_at=row.collected_at,
                source_id=row.id,
                source_kind=PeerMetricKind.VALUATION,
            )
            for row in valuations
        )
        return inputs

    async def has_successful_run(self, idempotency_key: str) -> bool:
        row = (
            await self._session.execute(
                select(PeerBenchmarkRunRecord).where(
                    PeerBenchmarkRunRecord.idempotency_key == idempotency_key,
                    PeerBenchmarkRunRecord.status == "succeeded",
                )
            )
        ).scalar_one_or_none()
        return row is not None

    async def save_results(
        self,
        *,
        canonical_symbol: str,
        universe: PeerUniverse,
        results: list[PeerBenchmarkResult],
        idempotency_key: str,
        input_fingerprint: str,
        knowledge_cutoff: datetime,
    ) -> int:
        existing = (
            await self._session.execute(
                select(PeerBenchmarkSnapshotRecord.id).where(
                    PeerBenchmarkSnapshotRecord.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return 0
        industry = (
            await self._session.execute(
                select(IndustryRecord).where(
                    IndustryRecord.taxonomy_code == universe.taxonomy_code,
                    IndustryRecord.taxonomy_version == universe.taxonomy_version,
                    IndustryRecord.code == universe.industry_code,
                )
            )
        ).scalar_one()
        run_id = (
            await self._session.execute(
                insert(PeerBenchmarkRunRecord)
                .values(
                    symbol=canonical_symbol,
                    idempotency_key=idempotency_key,
                    status="running",
                    taxonomy_code=universe.taxonomy_code,
                    taxonomy_version=universe.taxonomy_version,
                    peer_universe_fingerprint=universe.peer_universe_fingerprint,
                )
                .on_conflict_do_nothing(constraint="uq_peer_benchmark_run_idempotency")
                .returning(PeerBenchmarkRunRecord.id)
            )
        ).scalar_one_or_none()
        snapshot_id = (
            await self._session.execute(
                insert(PeerBenchmarkSnapshotRecord)
                .values(
                    idempotency_key=idempotency_key,
                    industry_id=industry.id,
                    taxonomy_code=universe.taxonomy_code,
                    taxonomy_version=universe.taxonomy_version,
                    knowledge_cutoff=knowledge_cutoff,
                    peer_universe_fingerprint=universe.peer_universe_fingerprint,
                    input_fingerprint=input_fingerprint,
                    benchmark_schema_version=PEER_SCHEMA_VERSION,
                    producer_version=PEER_PRODUCER_VERSION,
                )
                .returning(PeerBenchmarkSnapshotRecord.id)
            )
        ).scalar_one()
        comparison_count = 0
        for result in results:
            company = result.company_input
            metric_result_id = (
                await self._session.execute(
                    insert(PeerBenchmarkMetricResultRecord)
                    .values(
                        snapshot_id=snapshot_id,
                        metric_code=result.metric_code,
                        metric_kind=result.metric_kind.value,
                        fiscal_period=company.fiscal_period if company else None,
                        period_end=company.period_end if company else None,
                        basis=company.basis if company else None,
                        unit=company.unit if company else None,
                        status=result.status.value,
                        sample_size=result.sample_size,
                        median=result.median,
                        p25=result.p25,
                        p75=result.p75,
                        excluded_invalid_value_count=result.excluded_invalid_value_count,
                        reason=result.reason,
                    )
                    .returning(PeerBenchmarkMetricResultRecord.id)
                )
            ).scalar_one()
            if company:
                await self._insert_input(metric_result_id, company, "target", 0)
            for index, item in enumerate(result.peer_inputs):
                await self._insert_input(metric_result_id, item, "peer", index)
            await self._session.execute(
                insert(CompanyPeerMetricPositionRecord)
                .values(
                    symbol=canonical_symbol,
                    benchmark_snapshot_id=snapshot_id,
                    benchmark_metric_result_id=metric_result_id,
                    metric_point_id=company.source_id
                    if company and company.source_kind == PeerMetricKind.FUNDAMENTAL
                    else None,
                    valuation_observation_id=company.source_id
                    if company and company.source_kind == PeerMetricKind.VALUATION
                    else None,
                    metric_code=result.metric_code,
                    metric_kind=result.metric_kind.value,
                    status=result.status.value,
                    company_value=company.value if company else None,
                    numeric_percentile=result.numeric_percentile,
                    numeric_rank_desc=result.numeric_rank_desc,
                    sample_size=result.sample_size,
                    reason=result.reason,
                )
            )
            if result.status == PeerComparisonStatus.AVAILABLE:
                comparison_count += 1
        if run_id is not None:
            await self._session.execute(
                update(PeerBenchmarkRunRecord)
                .where(PeerBenchmarkRunRecord.id == run_id)
                .values(
                    status="succeeded",
                    comparison_count=comparison_count,
                    finished_at=datetime.now(UTC),
                )
            )
        await self._session.commit()
        return comparison_count

    async def latest_comparisons(
        self, canonical_symbol: str, dimension: str | None
    ) -> PeerComparisonEnvelope:
        snapshot_id = (
            await self._session.execute(
                select(CompanyPeerMetricPositionRecord.benchmark_snapshot_id)
                .where(CompanyPeerMetricPositionRecord.symbol == canonical_symbol)
                .order_by(CompanyPeerMetricPositionRecord.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snapshot_id is None:
            return PeerComparisonEnvelope(
                status="not_built",
                symbol=canonical_symbol.split(".")[0],
                canonical_symbol=canonical_symbol,
            )
        rows = (
            await self._session.execute(
                select(
                    CompanyPeerMetricPositionRecord,
                    PeerBenchmarkMetricResultRecord,
                    PeerBenchmarkSnapshotRecord,
                    IndustryRecord,
                    IndustryTaxonomyRecord,
                )
                .join(
                    PeerBenchmarkMetricResultRecord,
                    PeerBenchmarkMetricResultRecord.id
                    == CompanyPeerMetricPositionRecord.benchmark_metric_result_id,
                )
                .join(
                    PeerBenchmarkSnapshotRecord,
                    PeerBenchmarkSnapshotRecord.id
                    == CompanyPeerMetricPositionRecord.benchmark_snapshot_id,
                )
                .join(IndustryRecord, IndustryRecord.id == PeerBenchmarkSnapshotRecord.industry_id)
                .join(
                    IndustryTaxonomyRecord,
                    and_(
                        IndustryTaxonomyRecord.code == IndustryRecord.taxonomy_code,
                        IndustryTaxonomyRecord.version == IndustryRecord.taxonomy_version,
                    ),
                )
                .where(
                    CompanyPeerMetricPositionRecord.symbol == canonical_symbol,
                    CompanyPeerMetricPositionRecord.benchmark_snapshot_id == snapshot_id,
                )
                .order_by(CompanyPeerMetricPositionRecord.metric_code)
            )
        ).all()
        items: list[PeerMetricComparisonResponse] = []
        industry_response = None
        knowledge_cutoff = None
        universe_fingerprint = None
        for position, metric, snapshot, industry, taxonomy in rows:
            metric_dimension = METRIC_DIMENSIONS.get(position.metric_code, "unknown")
            if dimension and metric_dimension != dimension:
                continue
            industry_response = IndustryResponse(
                taxonomy_code=taxonomy.code,
                taxonomy_version=taxonomy.version,
                industry_code=industry.code,
                industry_name=industry.name,
                source=taxonomy.source,
                source_reference=taxonomy.source_reference,
                commercial_use_status=taxonomy.commercial_use_status,
                redistribution_status=taxonomy.redistribution_status,
            )
            knowledge_cutoff = snapshot.knowledge_cutoff
            universe_fingerprint = snapshot.peer_universe_fingerprint
            peer_ids = await self._peer_source_ids(metric.id)
            items.append(
                PeerMetricComparisonResponse(
                    metric_code=position.metric_code,
                    metric_kind=PeerMetricKind(position.metric_kind),
                    dimension=metric_dimension,
                    status=PeerComparisonStatus(position.status),
                    reason=position.reason,
                    company_value=position.company_value,
                    unit=metric.unit,
                    period_end=metric.period_end,
                    fiscal_period=metric.fiscal_period,
                    basis=metric.basis,
                    peer_median=metric.median,
                    peer_p25=metric.p25,
                    peer_p75=metric.p75,
                    numeric_percentile=position.numeric_percentile,
                    numeric_rank_desc=position.numeric_rank_desc,
                    sample_size=position.sample_size,
                    evidence=PeerBenchmarkEvidenceSummary(
                        benchmark_snapshot_id=snapshot.id,
                        company_source_kind=PeerMetricKind(position.metric_kind)
                        if (position.metric_point_id or position.valuation_observation_id)
                        else None,
                        company_source_id=position.metric_point_id
                        or position.valuation_observation_id,
                        peer_input_count=len(peer_ids),
                        peer_source_ids=peer_ids[:20],
                        excluded_invalid_value_count=metric.excluded_invalid_value_count,
                        knowledge_cutoff=snapshot.knowledge_cutoff,
                    ),
                )
            )
        status = "ready" if items else "not_built"
        return PeerComparisonEnvelope(
            status=status,  # type: ignore[arg-type]
            symbol=canonical_symbol.split(".")[0],
            canonical_symbol=canonical_symbol,
            industry=industry_response,
            peer_universe_fingerprint=universe_fingerprint,
            knowledge_cutoff=knowledge_cutoff,
            items=items,
            total=len(items),
        )

    async def reset_symbol_results(self, canonical_symbol: str) -> None:
        await self._session.execute(
            delete(CompanyPeerMetricPositionRecord).where(
                CompanyPeerMetricPositionRecord.symbol == canonical_symbol
            )
        )

    async def _insert_input(
        self, metric_result_id: UUID, item: ComparableMetricInput, role: str, ordinal: int
    ) -> None:
        await self._session.execute(
            insert(PeerBenchmarkInputRecord).values(
                metric_result_id=metric_result_id,
                symbol=item.symbol,
                role=role,
                ordinal=ordinal,
                metric_point_id=item.source_id
                if item.source_kind == PeerMetricKind.FUNDAMENTAL
                else None,
                valuation_observation_id=item.source_id
                if item.source_kind == PeerMetricKind.VALUATION
                else None,
            )
        )

    async def _peer_source_ids(self, metric_result_id: UUID) -> list[UUID]:
        rows = (
            await self._session.execute(
                select(
                    PeerBenchmarkInputRecord.metric_point_id,
                    PeerBenchmarkInputRecord.valuation_observation_id,
                )
                .where(
                    PeerBenchmarkInputRecord.metric_result_id == metric_result_id,
                    PeerBenchmarkInputRecord.role == "peer",
                )
                .order_by(PeerBenchmarkInputRecord.ordinal)
            )
        ).all()
        return [
            metric_id or valuation_id
            for metric_id, valuation_id in rows
            if metric_id or valuation_id
        ]

    async def _industry_response(self, universe: PeerUniverse) -> IndustryResponse | None:
        if not universe.industry_code:
            return None
        row = (
            await self._session.execute(
                select(IndustryRecord, IndustryTaxonomyRecord)
                .join(
                    IndustryTaxonomyRecord,
                    and_(
                        IndustryTaxonomyRecord.code == IndustryRecord.taxonomy_code,
                        IndustryTaxonomyRecord.version == IndustryRecord.taxonomy_version,
                    ),
                )
                .where(
                    IndustryRecord.taxonomy_code == universe.taxonomy_code,
                    IndustryRecord.taxonomy_version == universe.taxonomy_version,
                    IndustryRecord.code == universe.industry_code,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        industry, taxonomy = row
        return IndustryResponse(
            taxonomy_code=taxonomy.code,
            taxonomy_version=taxonomy.version,
            industry_code=industry.code,
            industry_name=industry.name,
            source=taxonomy.source,
            source_reference=taxonomy.source_reference,
            commercial_use_status=taxonomy.commercial_use_status,
            redistribution_status=taxonomy.redistribution_status,
        )


def latest_target_and_peers(
    inputs: list[ComparableMetricInput], canonical_symbol: str
) -> tuple[dict[str, ComparableMetricInput], dict[str, list[ComparableMetricInput]]]:
    target: dict[str, ComparableMetricInput] = {}
    peer_inputs: dict[str, list[ComparableMetricInput]] = defaultdict(list)
    grouped: dict[tuple[str, str], list[ComparableMetricInput]] = defaultdict(list)
    for item in inputs:
        grouped[(item.symbol, item.metric_code)].append(item)
    for (symbol, metric_code), rows in grouped.items():
        selected = max(
            rows,
            key=lambda item: (
                item.period_end is not None,
                item.period_end,
                item.known_at or datetime.min,
                item.source_id.hex,
            ),
        )
        if symbol == canonical_symbol:
            target[metric_code] = selected
        else:
            peer_inputs[metric_code].append(selected)
    return target, peer_inputs


async def existing_position_count(session: AsyncSession, canonical_symbol: str) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(CompanyPeerMetricPositionRecord).where(
                CompanyPeerMetricPositionRecord.symbol == canonical_symbol
            )
        )
        or 0
    )


def _industry_code(name: str) -> str:
    return hashlib.sha256(name.strip().encode()).hexdigest()[:16]


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()
