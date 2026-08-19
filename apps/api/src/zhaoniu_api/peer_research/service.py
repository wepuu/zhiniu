from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.peer_research.engine import (
    FUNDAMENTAL_CODES,
    VALUATION_CODES,
    compare_metric,
)
from zhaoniu_api.peer_research.models import (
    PEER_PRODUCER_VERSION,
    PEER_SCHEMA_VERSION,
    PRIMARY_TAXONOMY_CODE,
    PRIMARY_TAXONOMY_VERSION,
    PeerBuildResult,
    PeerComparisonEnvelope,
    PeerComparisonStatus,
    PeerMetricKind,
    PeerUniverseResponse,
)
from zhaoniu_api.peer_research.sql_repository import (
    SQLAlchemyPeerResearchRepository,
    latest_target_and_peers,
)
from zhaoniu_api.ports.repositories import StockRepository


@dataclass(frozen=True, slots=True)
class IndustrySyncResult:
    status: str
    taxonomy_code: str
    taxonomy_version: str
    written_count: int


class PeerResearchService:
    def __init__(
        self,
        *,
        stocks: StockRepository,
        peer_repository: SQLAlchemyPeerResearchRepository,
    ) -> None:
        self._stocks = stocks
        self._peers = peer_repository

    async def sync_industries(self) -> IndustrySyncResult:
        written = await self._peers.sync_from_stock_master()
        return IndustrySyncResult(
            status="succeeded",
            taxonomy_code=PRIMARY_TAXONOMY_CODE,
            taxonomy_version=PRIMARY_TAXONOMY_VERSION,
            written_count=written,
        )

    async def build_peer_benchmark(
        self, symbol: str, *, as_of: datetime | None = None
    ) -> PeerBuildResult:
        canonical = resolve_symbol(symbol).canonical
        cutoff = _normalize_cutoff(as_of)
        universe = await self._peers.resolve_universe(canonical, cutoff)
        idempotency_key = _hash(
            {
                "symbol": canonical,
                "taxonomy": PRIMARY_TAXONOMY_CODE,
                "taxonomy_version": PRIMARY_TAXONOMY_VERSION,
                "universe": universe.peer_universe_fingerprint,
                "knowledge_cutoff": cutoff,
                "schema": PEER_SCHEMA_VERSION,
                "producer": PEER_PRODUCER_VERSION,
            }
        )
        if await self._peers.has_successful_run(idempotency_key):
            envelope = await self._peers.latest_comparisons(canonical, None)
            return PeerBuildResult(
                status="skipped",
                symbol=canonical,
                industry_code=universe.industry_code,
                peer_count=len(universe.peer_symbols),
                comparison_count=envelope.total,
                idempotency_key=idempotency_key,
            )
        if universe.status != PeerComparisonStatus.AVAILABLE:
            return PeerBuildResult(
                status=universe.status.value,
                symbol=canonical,
                industry_code=universe.industry_code,
                peer_count=0,
                comparison_count=0,
                idempotency_key=idempotency_key,
            )
        symbols = (canonical, *universe.peer_symbols)
        inputs = await self._peers.list_inputs(symbols, cutoff)
        target, peers_by_metric = latest_target_and_peers(inputs, canonical)
        input_fingerprint = _hash(
            {
                "metric_inputs": [
                    {
                        "symbol": item.symbol,
                        "metric_code": item.metric_code,
                        "source_id": item.source_id,
                        "value": str(item.value),
                        "period_end": item.period_end,
                        "basis": item.basis,
                        "metric_version": item.metric_version,
                    }
                    for item in sorted(
                        inputs, key=lambda row: (row.metric_code, row.symbol, row.source_id.hex)
                    )
                ]
            }
        )
        final_key = _hash(
            {
                "base": idempotency_key,
                "input_fingerprint": input_fingerprint,
            }
        )
        if await self._peers.has_successful_run(final_key):
            envelope = await self._peers.latest_comparisons(canonical, None)
            return PeerBuildResult(
                status="skipped",
                symbol=canonical,
                industry_code=universe.industry_code,
                peer_count=len(universe.peer_symbols),
                comparison_count=envelope.total,
                idempotency_key=final_key,
            )
        results = []
        for code in FUNDAMENTAL_CODES:
            results.append(
                compare_metric(
                    code,
                    PeerMetricKind.FUNDAMENTAL,
                    target.get(code),
                    peers_by_metric.get(code, []),
                )
            )
        for code in VALUATION_CODES:
            results.append(
                compare_metric(
                    code,
                    PeerMetricKind.VALUATION,
                    target.get(code),
                    peers_by_metric.get(code, []),
                )
            )
        comparison_count = await self._peers.save_results(
            canonical_symbol=canonical,
            universe=universe,
            results=results,
            idempotency_key=final_key,
            input_fingerprint=input_fingerprint,
            knowledge_cutoff=cutoff,
        )
        return PeerBuildResult(
            status="succeeded",
            symbol=canonical,
            industry_code=universe.industry_code,
            peer_count=len(universe.peer_symbols),
            comparison_count=comparison_count,
            idempotency_key=final_key,
        )

    async def build_peer_research(
        self, symbol: str, *, as_of: datetime | None = None
    ) -> PeerBuildResult:
        return await self.build_peer_benchmark(symbol, as_of=as_of)

    async def get_peers(
        self, symbol: str, *, as_of: datetime | None = None
    ) -> PeerUniverseResponse:
        canonical = resolve_symbol(symbol).canonical
        return await self._peers.peer_universe_response(canonical, _normalize_cutoff(as_of))

    async def get_peer_comparisons(
        self, symbol: str, *, dimension: str | None = None
    ) -> PeerComparisonEnvelope:
        canonical = resolve_symbol(symbol).canonical
        stock = await self._stocks.get(canonical)
        if stock and stock.issuer_type != "general":
            return PeerComparisonEnvelope(
                status="unsupported_template",
                symbol=canonical.split(".")[0],
                canonical_symbol=canonical,
            )
        return await self._peers.latest_comparisons(canonical, dimension)


def _normalize_cutoff(value: datetime | None) -> datetime:
    cutoff = value or datetime.now(UTC)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    return cutoff


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()

