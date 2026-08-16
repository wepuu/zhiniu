import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.fundamentals.metrics import METRIC_VERSION
from zhaoniu_api.ports.repositories import (
    FundamentalRepository,
    ResearchRepository,
    StockRepository,
)
from zhaoniu_api.research.metric_series import (
    build_financial_metric_points,
    build_valuation_metric_points,
)
from zhaoniu_api.research.models import (
    CoverageStatus,
    FundamentalMetricPoint,
    ObservationDimension,
    ObservationList,
    ResearchBuildResult,
    ResearchCoverage,
    ResearchObservation,
    ResearchSnapshotDocument,
)
from zhaoniu_api.research.rules import (
    RULE_ENGINE_VERSION,
    RULES,
    evaluate_rules,
    rule_set_version,
)

TEMPLATE_VERSION = "fundamental_general:v1"
SNAPSHOT_SCHEMA_VERSION = "research-snapshot-v1"


class ResearchBuildInProgressError(RuntimeError):
    pass


def _safe_error(error: Exception) -> str:
    return f"{type(error).__name__}: {str(error)[:420]}"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def scope_observations_to_snapshot(
    snapshot_id: UUID, observations: list[ResearchObservation]
) -> list[ResearchObservation]:
    return [
        item.model_copy(
            update={
                "id": uuid5(
                    NAMESPACE_URL,
                    f"zhaoniu:research-observation:{snapshot_id}:{item.content_fingerprint}",
                )
            }
        )
        for item in observations
    ]


class DeterministicResearchService:
    def __init__(
        self,
        *,
        stocks: StockRepository,
        fundamentals: FundamentalRepository,
        research: ResearchRepository,
    ) -> None:
        self._stocks = stocks
        self._fundamentals = fundamentals
        self._research = research

    @staticmethod
    def _coverage(issuer_type: str, points: list[FundamentalMetricPoint]) -> list[ResearchCoverage]:
        result: list[ResearchCoverage] = []
        for dimension in ObservationDimension:
            if issuer_type != "general":
                result.append(
                    ResearchCoverage(
                        dimension=dimension,
                        status=CoverageStatus.NOT_APPLICABLE,
                        reason="general_issuer_template_not_supported",
                    )
                )
                continue
            codes = {
                code
                for rule in RULES
                if rule.dimension == dimension
                for code in rule.required_metrics
            }
            relevant = [point for point in points if point.code in codes]
            if any(point.value is not None and point.status == "available" for point in relevant):
                status, reason = CoverageStatus.AVAILABLE, None
            elif relevant:
                status, reason = CoverageStatus.INSUFFICIENT_HISTORY, "rule_inputs_unavailable"
            else:
                status, reason = CoverageStatus.MISSING, "metric_points_missing"
            result.append(ResearchCoverage(dimension=dimension, status=status, reason=reason))
        return result

    async def build_snapshot(
        self, symbol: str, *, as_of: datetime | None = None
    ) -> ResearchBuildResult:
        canonical = resolve_symbol(symbol).canonical
        stock = await self._stocks.get(canonical)
        if stock is None:
            raise ValueError("stock not found")
        cutoff = as_of or datetime.now(UTC)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        reports = await self._fundamentals.list_reports(canonical, as_of=cutoff, limit=64)
        valuations = await self._fundamentals.list_valuations(
            canonical,
            start=cutoff.date() - timedelta(days=365 * 4),
            end=cutoff.date(),
            metric_codes=("pe_ttm", "pb"),
            limit=10000,
        )
        valuations = [item for item in valuations if item.collected_at <= cutoff]
        financial_points = list(build_financial_metric_points(reports))
        valuation_points = list(build_valuation_metric_points(valuations))
        points = [
            point for point in financial_points + valuation_points if point.known_at <= cutoff
        ]
        await self._research.upsert_metric_points(points)

        rule_version = rule_set_version()
        version_material = [
            {
                "id": str(point.id),
                "fingerprint": point.input_fingerprint,
                "code": point.code,
                "period_end": point.period_end.isoformat(),
            }
            for point in sorted(points, key=lambda item: (item.code, item.period_end, str(item.id)))
        ]
        data_version = _digest(version_material)
        existing = await self._research.find_snapshot(
            canonical,
            data_version=data_version,
            metric_version=METRIC_VERSION,
            rule_set_version=rule_version,
            template_version=TEMPLATE_VERSION,
        )
        idempotency_key = _digest(
            [canonical, data_version, METRIC_VERSION, rule_version, TEMPLATE_VERSION]
        )
        if existing is not None:
            return ResearchBuildResult(
                "skipped",
                existing.id,
                existing.data_version,
                len(existing.observations),
                idempotency_key,
            )

        lease = await self._research.acquire_research_run(
            canonical_symbol=canonical,
            idempotency_key=idempotency_key,
            data_version=data_version,
            metric_version=METRIC_VERSION,
            rule_set_version=rule_version,
            template_version=TEMPLATE_VERSION,
        )
        if not lease.acquired:
            if lease.status == "succeeded":
                completed = await self._research.find_snapshot(
                    canonical,
                    data_version=data_version,
                    metric_version=METRIC_VERSION,
                    rule_set_version=rule_version,
                    template_version=TEMPLATE_VERSION,
                )
                if completed is not None:
                    return ResearchBuildResult(
                        "skipped",
                        completed.id,
                        completed.data_version,
                        len(completed.observations),
                        idempotency_key,
                    )
            raise ResearchBuildInProgressError("equivalent research build is already running")

        snapshot_id: UUID | None = None
        try:
            generated_at = datetime.now(UTC)
            issuer_type = reports[0].issuer_type if reports else stock.issuer_type
            evaluated_observations = list(
                evaluate_rules(
                    symbol=canonical,
                    issuer_type=issuer_type,
                    template_version=TEMPLATE_VERSION,
                    points=points,
                    reports=reports,
                    generated_at=generated_at,
                )
            )
            identity = ":".join(
                [canonical, data_version, METRIC_VERSION, rule_version, TEMPLATE_VERSION]
            )
            snapshot_id = uuid5(NAMESPACE_URL, f"zhaoniu:research-snapshot:{identity}")
            observations = scope_observations_to_snapshot(snapshot_id, evaluated_observations)
            latest_financial = max((item.period_end for item in reports), default=None)
            latest_valuation = max((item.trade_date for item in valuations), default=None)
            snapshot = ResearchSnapshotDocument(
                id=snapshot_id,
                symbol=canonical,
                knowledge_cutoff=cutoff,
                data_version=data_version,
                metric_version=METRIC_VERSION,
                rule_set_version=rule_version,
                research_template_version=TEMPLATE_VERSION,
                snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
                producer_version=RULE_ENGINE_VERSION,
                latest_financial_period=latest_financial,
                latest_valuation_date=latest_valuation,
                input_manifest={
                    "report_revisions": [
                        {
                            "id": str(item.id),
                            "period_end": item.period_end.isoformat(),
                            "payload_checksum": item.payload_checksum,
                            "known_at": item.known_at.isoformat(),
                        }
                        for item in reports
                    ],
                    "metric_points": [
                        {"id": str(item.id), "fingerprint": item.input_fingerprint}
                        for item in points
                    ],
                    "valuation_cutoff": latest_valuation.isoformat() if latest_valuation else None,
                },
                coverage=self._coverage(issuer_type, points),
                observations=observations,
                generated_at=generated_at,
            )
            await self._research.save_research_snapshot(snapshot, observations)
            await self._research.finish_research_run(
                lease.run_id,
                status="succeeded",
                snapshot_id=snapshot.id,
                observation_count=len(observations),
                error_summary=None,
                finished_at=datetime.now(UTC),
            )
            return ResearchBuildResult(
                "succeeded", snapshot.id, data_version, len(observations), idempotency_key
            )
        except Exception as error:
            await self._research.finish_research_run(
                lease.run_id,
                status="failed",
                snapshot_id=None,
                observation_count=0,
                error_summary=_safe_error(error),
                finished_at=datetime.now(UTC),
            )
            raise

    async def latest_snapshot(self, symbol: str) -> ResearchSnapshotDocument | None:
        return await self._research.latest_research_snapshot(resolve_symbol(symbol).canonical)

    async def list_observations(self, symbol: str, *, limit: int) -> ObservationList:
        canonical = resolve_symbol(symbol).canonical
        snapshot_id, items = await self._research.list_research_observations(canonical, limit=limit)
        return ObservationList(
            symbol=canonical,
            snapshot_id=snapshot_id,
            items=items,
            total=len(items),
        )

    async def get_observation(
        self, symbol: str, observation_id: UUID
    ) -> ResearchObservation | None:
        return await self._research.get_research_observation(
            resolve_symbol(symbol).canonical, observation_id
        )
