from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.db import (
    FundamentalMetricPointRecord,
    ResearchBuildRunRecord,
    ResearchObservationInputRecord,
    ResearchObservationRecord,
    ResearchSnapshotRecord,
)
from zhaoniu_api.research.models import (
    FundamentalMetricPoint,
    ResearchObservation,
    ResearchRunLease,
    ResearchSnapshotDocument,
)


class SQLAlchemyResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_metric_points(self, points: list[FundamentalMetricPoint]) -> int:
        if not points:
            return 0
        values = [
            {
                "id": point.id,
                "symbol": point.canonical_symbol,
                "code": point.code,
                "value": point.value,
                "unit": point.unit,
                "status": point.status,
                "period_end": point.period_end,
                "fiscal_period": point.fiscal_period,
                "basis": point.basis,
                "known_at": point.known_at,
                "metric_version": point.metric_version,
                "input_fingerprint": point.input_fingerprint,
                "input_report_ids": {"items": [str(item) for item in point.input_report_ids]},
                "input_valuation_ids": {"items": [str(item) for item in point.input_valuation_ids]},
                "detail": point.detail,
            }
            for point in points
        ]
        written = 0
        try:
            for offset in range(0, len(values), 500):
                statement = (
                    insert(FundamentalMetricPointRecord)
                    .values(values[offset : offset + 500])
                    .on_conflict_do_nothing(constraint="uq_fundamental_metric_point_fingerprint")
                    .returning(FundamentalMetricPointRecord.id)
                )
                written += len((await self._session.scalars(statement)).all())
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return written

    @staticmethod
    def _snapshot(row: ResearchSnapshotRecord) -> ResearchSnapshotDocument:
        return ResearchSnapshotDocument.model_validate(row.structured_result)

    async def find_snapshot(
        self,
        canonical_symbol: str,
        *,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchSnapshotDocument | None:
        row = await self._session.scalar(
            select(ResearchSnapshotRecord).where(
                ResearchSnapshotRecord.symbol == canonical_symbol,
                ResearchSnapshotRecord.data_version == data_version,
                ResearchSnapshotRecord.metric_version == metric_version,
                ResearchSnapshotRecord.rule_set_version == rule_set_version,
                ResearchSnapshotRecord.research_template_version == template_version,
                ResearchSnapshotRecord.producer_version == "change-engine-v1",
            )
        )
        return self._snapshot(row) if row else None

    async def latest_research_snapshot(
        self, canonical_symbol: str
    ) -> ResearchSnapshotDocument | None:
        row = await self._session.scalar(
            select(ResearchSnapshotRecord)
            .where(
                ResearchSnapshotRecord.symbol == canonical_symbol,
                ResearchSnapshotRecord.producer_kind == "deterministic",
            )
            .order_by(
                ResearchSnapshotRecord.knowledge_cutoff.desc(),
                ResearchSnapshotRecord.generated_at.desc(),
            )
            .limit(1)
        )
        return self._snapshot(row) if row else None

    async def save_research_snapshot(
        self,
        snapshot: ResearchSnapshotDocument,
        observations: list[ResearchObservation],
    ) -> None:
        try:
            await self._session.execute(
                insert(ResearchSnapshotRecord)
                .values(
                    id=snapshot.id,
                    symbol=snapshot.symbol,
                    data_version=snapshot.data_version,
                    research_template_version=snapshot.research_template_version,
                    metric_version=snapshot.metric_version,
                    rule_set_version=snapshot.rule_set_version,
                    snapshot_schema_version=snapshot.snapshot_schema_version,
                    producer_kind=snapshot.producer_kind,
                    producer_version=snapshot.producer_version,
                    knowledge_cutoff=snapshot.knowledge_cutoff,
                    input_manifest=snapshot.input_manifest,
                    structured_result=snapshot.model_dump(mode="json"),
                    generated_at=snapshot.generated_at,
                )
                .on_conflict_do_nothing(constraint="uq_research_snapshot_identity")
            )
            if observations:
                await self._session.execute(
                    insert(ResearchObservationRecord)
                    .values(
                        [
                            {
                                "id": observation.id,
                                "snapshot_id": snapshot.id,
                                "symbol": observation.symbol,
                                "dimension": observation.dimension,
                                "observation_family": observation.observation_family,
                                "observation_type": observation.observation_type,
                                "attention_level": observation.attention_level,
                                "movement": observation.movement,
                                "title": observation.title,
                                "summary": observation.summary,
                                "current_period": observation.current_period,
                                "comparison_periods": {
                                    "items": [
                                        item.isoformat() for item in observation.comparison_periods
                                    ]
                                },
                                "rule_id": observation.rule_id,
                                "rule_version": observation.rule_version,
                                "observation_key": observation.observation_key,
                                "content_fingerprint": observation.content_fingerprint,
                                "detail_payload": observation.model_dump(mode="json"),
                                "generated_at": observation.generated_at,
                            }
                            for observation in observations
                        ]
                    )
                    .on_conflict_do_nothing(constraint="uq_research_observation_content")
                )
                input_values: list[dict[str, object]] = []
                for observation in observations:
                    ordinal = 0
                    seen_reports: set[UUID] = set()
                    seen_valuations: set[UUID] = set()
                    for metric in observation.evidence_metrics:
                        input_values.append(
                            {
                                "observation_id": observation.id,
                                "role": metric.role,
                                "ordinal": ordinal,
                                "metric_point_id": metric.metric_point_id,
                                "report_revision_id": None,
                                "valuation_observation_id": None,
                            }
                        )
                        ordinal += 1
                        seen_reports.update(metric.input_report_ids)
                        seen_valuations.update(metric.input_valuation_ids)
                    for report_id in sorted(seen_reports, key=str):
                        input_values.append(
                            {
                                "observation_id": observation.id,
                                "role": "source_report",
                                "ordinal": ordinal,
                                "metric_point_id": None,
                                "report_revision_id": report_id,
                                "valuation_observation_id": None,
                            }
                        )
                        ordinal += 1
                    for valuation_id in sorted(seen_valuations, key=str):
                        input_values.append(
                            {
                                "observation_id": observation.id,
                                "role": "source_valuation",
                                "ordinal": ordinal,
                                "metric_point_id": None,
                                "report_revision_id": None,
                                "valuation_observation_id": valuation_id,
                            }
                        )
                        ordinal += 1
                if input_values:
                    await self._session.execute(
                        insert(ResearchObservationInputRecord)
                        .values(input_values)
                        .on_conflict_do_nothing()
                    )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def list_research_observations(
        self, canonical_symbol: str, *, limit: int
    ) -> tuple[UUID | None, list[ResearchObservation]]:
        snapshot = await self.latest_research_snapshot(canonical_symbol)
        if snapshot is None:
            return None, []
        rows = (
            await self._session.scalars(
                select(ResearchObservationRecord)
                .where(ResearchObservationRecord.snapshot_id == snapshot.id)
                .order_by(ResearchObservationRecord.generated_at.desc())
                .limit(limit)
            )
        ).all()
        return snapshot.id, [ResearchObservation.model_validate(row.detail_payload) for row in rows]

    async def get_research_observation(
        self, canonical_symbol: str, observation_id: UUID
    ) -> ResearchObservation | None:
        row = await self._session.scalar(
            select(ResearchObservationRecord).where(
                ResearchObservationRecord.id == observation_id,
                ResearchObservationRecord.symbol == canonical_symbol,
            )
        )
        return ResearchObservation.model_validate(row.detail_payload) if row else None

    async def acquire_research_run(
        self,
        *,
        canonical_symbol: str,
        idempotency_key: str,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchRunLease:
        run_id = uuid4()
        try:
            inserted = await self._session.scalar(
                insert(ResearchBuildRunRecord)
                .values(
                    id=run_id,
                    symbol=canonical_symbol,
                    idempotency_key=idempotency_key,
                    status="running",
                    data_version=data_version,
                    metric_version=metric_version,
                    rule_set_version=rule_set_version,
                    research_template_version=template_version,
                )
                .on_conflict_do_nothing(index_elements=[ResearchBuildRunRecord.idempotency_key])
                .returning(ResearchBuildRunRecord.id)
            )
            if inserted is not None:
                await self._session.commit()
                return ResearchRunLease(inserted, True, "running")
            row = await self._session.scalar(
                select(ResearchBuildRunRecord).where(
                    ResearchBuildRunRecord.idempotency_key == idempotency_key
                )
            )
            if row is None:
                raise RuntimeError("research build run disappeared")
            stale_before = datetime.now(UTC) - timedelta(minutes=30)
            can_reacquire = row.status == "failed" or (
                row.status == "running" and row.started_at < stale_before
            )
            if can_reacquire:
                reacquired = await self._session.scalar(
                    update(ResearchBuildRunRecord)
                    .where(
                        ResearchBuildRunRecord.id == row.id,
                        or_(
                            ResearchBuildRunRecord.status == "failed",
                            and_(
                                ResearchBuildRunRecord.status == "running",
                                ResearchBuildRunRecord.started_at < stale_before,
                            ),
                        ),
                    )
                    .values(
                        status="running",
                        error_summary=None,
                        started_at=datetime.now(UTC),
                        finished_at=None,
                        snapshot_id=None,
                        observation_count=0,
                    )
                    .returning(ResearchBuildRunRecord.id)
                )
                await self._session.commit()
                if reacquired is not None:
                    return ResearchRunLease(reacquired, True, "running")
            existing_id, existing_status = row.id, row.status
            await self._session.rollback()
            return ResearchRunLease(existing_id, False, existing_status)
        except Exception:
            await self._session.rollback()
            raise

    async def finish_research_run(
        self,
        run_id: UUID,
        *,
        status: str,
        snapshot_id: UUID | None,
        observation_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None:
        try:
            await self._session.execute(
                update(ResearchBuildRunRecord)
                .where(ResearchBuildRunRecord.id == run_id)
                .values(
                    status=status,
                    snapshot_id=snapshot_id,
                    observation_count=observation_count,
                    error_summary=error_summary,
                    finished_at=finished_at,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
