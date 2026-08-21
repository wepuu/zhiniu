from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from typing import Any, Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.automation.models import (
    AutomationPolicyConfiguration,
    AutomationPolicyView,
    AutomationRunDetail,
    AutomationRunStatus,
    AutomationRunSummary,
    AutomationStepView,
    AutomationTickResult,
    AutomationTriggerResponse,
)
from zhaoniu_api.config import Settings
from zhaoniu_api.coverage.service import ResearchCoverageService
from zhaoniu_api.db import (
    AIResearchOutputRecord,
    AutomationPolicyRecord,
    AutomationPolicyRevisionRecord,
    AutomationRunRecord,
    AutomationRunStepRecord,
    AutomationStepAttemptRecord,
    BetaResearchUniverseMemberRecord,
    CompanyPeerMetricPositionRecord,
    DataSyncRunRecord,
    EventRadarSnapshotRecord,
    FinancialReportRevisionRecord,
    FundamentalSnapshotRecord,
    IndustryMembershipRecord,
    ResearchSignalRecord,
    ResearchSnapshotRecord,
    StockDailyBarRecord,
    ValuationObservationRecord,
)

POLICY_KEY = "priority_daily_refresh"
POLICY_DISPLAY_NAME = "优先股票池每日研究刷新"
POLICY_SCHEMA_VERSION = "automation-policy-v1"
PIPELINE_VERSION = "priority-research-pipeline-v1"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def stable_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


def due_slot(now: datetime, daily_time: str) -> tuple[datetime | None, datetime]:
    """Return today's due slot (when reached) and the next future slot in UTC."""
    aware = now if now.tzinfo else now.replace(tzinfo=UTC)
    local = aware.astimezone(SHANGHAI)
    hour, minute = (int(part) for part in daily_time.split(":"))
    today = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local < today:
        return None, today.astimezone(UTC)
    tomorrow = today + timedelta(days=1)
    return today.astimezone(UTC), tomorrow.astimezone(UTC)


def is_reporting_window(day: date) -> bool:
    return day.month in {3, 4, 7, 8, 10}


@dataclass(frozen=True, slots=True)
class StepExecutionResult:
    status: Literal["succeeded", "skipped"] = "succeeded"
    provider_calls: int = 0
    rows_received: int = 0
    rows_written: int = 0
    signal_count: int = 0
    alert_count: int = 0
    ai_output_count: int = 0


class ProductionAutomationExecutor:
    """Allow-listed adapter from automation steps to existing application services."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def execute(
        self,
        step_key: str,
        *,
        symbol: str | None,
        universe_snapshot_id: UUID | None,
        scope_key: str,
    ) -> StepExecutionResult:
        from zhaoniu_api.composition import (
            build_ai_research_service,
            build_corporate_event_service,
            build_coverage_service,
            build_fundamental_service,
            build_market_data_service,
            build_peer_research_service,
            build_research_feed_service,
            build_research_service,
        )

        result: Any
        if step_key == "coverage_finalize":
            result = await build_coverage_service(self._session).build_coverage_snapshot(
                universe_snapshot_id
            )
            return StepExecutionResult(status=cast(Any, result.status))
        if symbol is None:
            raise ValueError("automation_symbol_required")
        if step_key == "market_sync":
            result = await build_market_data_service(self._session).sync_daily_bars(symbol)
            return _service_result(result, provider_calls=1)
        if step_key == "financial_sync":
            result = await build_fundamental_service(self._session).sync_financial_statements(
                symbol, start_year=date.today().year - 6
            )
            return _service_result(result, provider_calls=1)
        if step_key == "valuation_sync":
            result = await build_fundamental_service(self._session).sync_valuations(symbol)
            return _service_result(result, provider_calls=1)
        if step_key == "fundamental_build":
            result = await build_fundamental_service(self._session).compute_snapshot(symbol)
            return _service_result(result)
        if step_key == "research_build":
            result = await build_research_service(self._session).build_snapshot(symbol)
            return _service_result(result)
        if step_key == "event_pipeline":
            service = build_corporate_event_service(self._session)
            synced = await service.sync_disclosures(symbol)
            await service.build_corporate_events(symbol)
            radar = await service.build_event_radar(symbol)
            combined = _service_result(synced, provider_calls=1)
            return StepExecutionResult(
                status="skipped"
                if combined.status == "skipped" and getattr(radar, "status", "") == "skipped"
                else "succeeded",
                provider_calls=1,
                rows_received=combined.rows_received,
                rows_written=combined.rows_written,
            )
        if step_key == "peer_research":
            targets = [symbol]
            if universe_snapshot_id is not None:
                taxonomy, version, industry = scope_key.split(":", 2)
                targets = list(
                    (
                        await self._session.scalars(
                            select(BetaResearchUniverseMemberRecord.symbol)
                            .join(
                                IndustryMembershipRecord,
                                IndustryMembershipRecord.symbol
                                == BetaResearchUniverseMemberRecord.symbol,
                            )
                            .where(
                                BetaResearchUniverseMemberRecord.snapshot_id
                                == universe_snapshot_id,
                                IndustryMembershipRecord.taxonomy_code == taxonomy,
                                IndustryMembershipRecord.taxonomy_version == version,
                                IndustryMembershipRecord.industry_code == industry,
                            )
                            .distinct()
                        )
                    ).all()
                )
            statuses = []
            peer_service = build_peer_research_service(self._session)
            for target in sorted(set(targets)):
                statuses.append((await peer_service.build_peer_research(target)).status)
            return StepExecutionResult(
                status="skipped"
                if statuses and all(item == "skipped" for item in statuses)
                else "succeeded"
            )
        if step_key == "signal_projection":
            feed = build_research_feed_service(self._session)
            projected = await feed.project_symbol(symbol)
            alerts = 0
            for signal_id in projected.projected_signal_ids:
                alerts += (await feed.dispatch(signal_id)).delivery_count
            return StepExecutionResult(
                status=projected.status,
                signal_count=len(projected.projected_signal_ids),
                alert_count=alerts,
            )
        if step_key == "ai_research":
            result = await build_ai_research_service(self._session).generate_stock_health(symbol)
            return StepExecutionResult(
                status="skipped" if result.status == "skipped" else "succeeded",
                ai_output_count=int(result.output_id is not None),
            )
        raise ValueError("unsupported_automation_step")


def _service_result(result: object, *, provider_calls: int = 0) -> StepExecutionResult:
    result_status = str(getattr(result, "status", "succeeded"))
    return StepExecutionResult(
        status="skipped" if result_status in {"skipped", "not_applicable"} else "succeeded",
        provider_calls=provider_calls,
        rows_received=int(getattr(result, "received_count", 0) or 0),
        rows_written=int(getattr(result, "written_count", 0) or 0),
    )


class AutomationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        executor: ProductionAutomationExecutor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._executor = executor or ProductionAutomationExecutor(session, settings)
        self._coverage = ResearchCoverageService(session, settings)

    async def ensure_default_policy(self) -> AutomationPolicyRecord:
        policy = await self._session.scalar(
            select(AutomationPolicyRecord).where(AutomationPolicyRecord.policy_key == POLICY_KEY)
        )
        if policy is not None:
            return policy
        configuration = AutomationPolicyConfiguration(
            max_universe_size=min(100, self._settings.automation_max_universe_size)
        )
        policy = AutomationPolicyRecord(
            id=uuid4(),
            policy_key=POLICY_KEY,
            display_name=POLICY_DISPLAY_NAME,
            enabled=False,
        )
        self._session.add(policy)
        await self._session.flush()
        config_json = configuration.model_dump(mode="json")
        revision = AutomationPolicyRevisionRecord(
            id=uuid4(),
            policy_id=policy.id,
            revision=1,
            configuration=config_json,
            configuration_hash=stable_hash(
                {"schema": POLICY_SCHEMA_VERSION, "configuration": config_json}
            ),
        )
        self._session.add(revision)
        await self._session.flush()
        policy.current_revision_id = revision.id
        try:
            await self._session.commit()
            return policy
        except IntegrityError:
            await self._session.rollback()
            existing = await self._session.scalar(
                select(AutomationPolicyRecord).where(
                    AutomationPolicyRecord.policy_key == POLICY_KEY
                )
            )
            if existing is None:
                raise
            return existing

    async def list_policies(self) -> list[AutomationPolicyView]:
        await self.ensure_default_policy()
        rows = (
            await self._session.execute(
                select(AutomationPolicyRecord, AutomationPolicyRevisionRecord)
                .join(
                    AutomationPolicyRevisionRecord,
                    AutomationPolicyRevisionRecord.id == AutomationPolicyRecord.current_revision_id,
                )
                .order_by(AutomationPolicyRecord.policy_key)
            )
        ).all()
        return [self._policy_view(policy, revision) for policy, revision in rows]

    async def update_policy(
        self,
        policy_key: str,
        *,
        enabled: bool,
        configuration: AutomationPolicyConfiguration,
        actor_user_id: UUID,
    ) -> AutomationPolicyView:
        policy, current = await self._load_policy(policy_key, lock=True)
        if configuration.max_universe_size > self._settings.automation_max_universe_size:
            raise ValueError("automation_universe_limit_exceeds_environment_cap")
        config_json = configuration.model_dump(mode="json")
        config_hash = stable_hash({"schema": POLICY_SCHEMA_VERSION, "configuration": config_json})
        if config_hash != current.configuration_hash:
            revision = AutomationPolicyRevisionRecord(
                id=uuid4(),
                policy_id=policy.id,
                revision=current.revision + 1,
                configuration=config_json,
                configuration_hash=config_hash,
                created_by_user_id=actor_user_id,
            )
            self._session.add(revision)
            await self._session.flush()
            policy.current_revision_id = revision.id
            current = revision
        policy.enabled = enabled
        _, next_due = due_slot(datetime.now(UTC), configuration.daily_time)
        policy.next_due_at = next_due
        await self._session.commit()
        await self._session.refresh(policy)
        return self._policy_view(policy, current)

    async def tick(self, now: datetime | None = None) -> AutomationTickResult:
        moment = now or datetime.now(UTC)
        policy = await self.ensure_default_policy()
        if self._settings.automation_hard_disabled:
            return AutomationTickResult(status="disabled")
        policy, revision = await self._load_policy(policy.policy_key, lock=True)
        policy.last_evaluated_at = moment
        configuration = AutomationPolicyConfiguration.model_validate(revision.configuration)
        slot, next_due = due_slot(moment, configuration.daily_time)
        policy.next_due_at = next_due
        if not policy.enabled or slot is None:
            await self._session.commit()
            return AutomationTickResult(status="idle")
        await self._session.commit()
        if moment - slot > timedelta(minutes=self._settings.automation_catchup_window_minutes):
            await self._create_missed_run(policy, revision, slot)
            return AutomationTickResult(status="idle")
        result = await self.trigger_run(
            policy.policy_key,
            trigger_kind="scheduled",
            scheduled_for=slot,
            request_key=slot.isoformat(),
        )
        return AutomationTickResult(status="scheduled", run_ids=[result.run_id])

    async def trigger_run(
        self,
        policy_key: str = POLICY_KEY,
        *,
        trigger_kind: Literal["scheduled", "manual"] = "manual",
        scheduled_for: datetime | None = None,
        request_key: str | None = None,
        symbols: tuple[str, ...] | None = None,
    ) -> AutomationTriggerResponse:
        policy, revision = await self._load_policy(policy_key)
        configuration = AutomationPolicyConfiguration.model_validate(revision.configuration)
        moment = scheduled_for or datetime.now(UTC)
        key = stable_hash(
            {
                "policy": str(policy.id),
                "revision": str(revision.id),
                "trigger": trigger_kind,
                "scheduled_for": moment.isoformat() if trigger_kind == "scheduled" else None,
                "request_key": request_key or str(uuid4()),
                "symbols": sorted(symbols or ()),
            }
        )
        existing = await self._session.scalar(
            select(AutomationRunRecord).where(AutomationRunRecord.idempotency_key == key)
        )
        if existing is not None:
            return AutomationTriggerResponse(
                status="skipped", run_id=existing.id, run_status=cast(Any, existing.status)
            )
        universe_id: UUID | None = None
        if symbols is None:
            universe = await self._coverage.build_universe(as_of=datetime.now(UTC))
            universe_id = universe.id
            universe_symbols = [item.symbol for item in universe.items]
            universe_hash = universe.universe_fingerprint
        else:
            from zhaoniu_api.domain.models import resolve_symbol

            universe_symbols = sorted({resolve_symbol(symbol).canonical for symbol in symbols})
            universe_hash = stable_hash(universe_symbols)
        policy_snapshot = {
            "schema_version": POLICY_SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "revision": revision.revision,
            "configuration": configuration.model_dump(mode="json"),
        }
        run = AutomationRunRecord(
            id=uuid4(),
            policy_id=policy.id,
            policy_revision_id=revision.id,
            universe_snapshot_id=universe_id,
            trigger_kind=trigger_kind,
            scheduled_for=moment,
            idempotency_key=key,
            policy_snapshot=policy_snapshot,
            policy_hash=revision.configuration_hash,
            universe_snapshot={"symbols": universe_symbols, "size": len(universe_symbols)},
            universe_hash=universe_hash,
            status="pending",
        )
        self._session.add(run)
        await self._session.flush()
        if len(universe_symbols) > configuration.max_universe_size:
            run.status = "blocked"
            run.error_code = "automation_universe_limit_exceeded"
            run.finished_at = datetime.now(UTC)
            await self._session.commit()
            return AutomationTriggerResponse(status="blocked", run_id=run.id, run_status="blocked")
        await self._plan_steps(run, configuration, universe_symbols)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._session.scalar(
                select(AutomationRunRecord).where(AutomationRunRecord.idempotency_key == key)
            )
            if existing is None:
                raise
            return AutomationTriggerResponse(
                status="skipped", run_id=existing.id, run_status=cast(Any, existing.status)
            )
        return AutomationTriggerResponse(status="accepted", run_id=run.id, run_status="pending")

    async def _plan_steps(
        self,
        run: AutomationRunRecord,
        configuration: AutomationPolicyConfiguration,
        symbols: list[str],
    ) -> None:
        symbol_steps = [
            (10, "market_sync"),
            (20, "financial_sync"),
            (30, "valuation_sync"),
            (40, "fundamental_build"),
            (50, "research_build"),
        ]
        if configuration.event_pipeline_enabled:
            symbol_steps.append((60, "event_pipeline"))
        for symbol in symbols:
            for order, key in symbol_steps:
                self._add_step(run, "symbol", symbol, key, order, symbol)
        if configuration.peer_research_enabled:
            industries: dict[str, str] = {}
            for symbol in symbols:
                membership = await self._session.scalar(
                    select(IndustryMembershipRecord)
                    .where(IndustryMembershipRecord.symbol == symbol)
                    .order_by(IndustryMembershipRecord.known_at.desc())
                    .limit(1)
                )
                if membership is not None:
                    scope = (
                        f"{membership.taxonomy_code}:{membership.taxonomy_version}:"
                        f"{membership.industry_code}"
                    )
                    industries.setdefault(scope, symbol)
            for scope, representative in sorted(industries.items()):
                self._add_step(run, "industry", scope, "peer_research", 70, representative)
        for symbol in symbols:
            self._add_step(run, "symbol", symbol, "signal_projection", 80, symbol)
            if configuration.ai_research_enabled:
                self._add_step(run, "symbol", symbol, "ai_research", 90, symbol)
        self._add_step(run, "run", str(run.id), "coverage_finalize", 100, None)

    def _add_step(
        self,
        run: AutomationRunRecord,
        scope_type: str,
        scope_key: str,
        step_key: str,
        order: int,
        symbol: str | None,
    ) -> None:
        run.total_steps += 1
        self._session.add(
            AutomationRunStepRecord(
                id=uuid4(),
                run_id=run.id,
                scope_type=scope_type,
                scope_key=scope_key,
                symbol=symbol,
                step_key=step_key,
                dependency_order=order,
                idempotency_key=stable_hash(
                    {"run": str(run.id), "scope": scope_key, "step": step_key}
                ),
                status="pending",
            )
        )

    async def execute_run(
        self, run_id: UUID, *, worker_id: str = "automation-worker"
    ) -> AutomationRunDetail:
        now = datetime.now(UTC)
        run = await self._session.get(AutomationRunRecord, run_id, with_for_update=True)
        if run is None:
            raise ValueError("automation_run_not_found")
        if run.status not in {"pending", "running"}:
            return await self.run_detail(run.id)
        if (
            run.status == "running"
            and run.lease_expires_at is not None
            and run.lease_expires_at > now
        ):
            return await self.run_detail(run.id)
        await self._session.execute(
            update(AutomationRunStepRecord)
            .where(
                AutomationRunStepRecord.run_id == run.id,
                AutomationRunStepRecord.status == "running",
                AutomationRunStepRecord.lease_expires_at < now,
            )
            .values(
                status="pending",
                lease_owner=None,
                lease_expires_at=None,
                error_code="expired_lease_recovered",
            )
        )
        run.status = "running"
        run.started_at = run.started_at or now
        run.lease_owner = worker_id
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(minutes=self._settings.automation_lease_minutes)
        await self._session.commit()
        steps = (
            await self._session.scalars(
                select(AutomationRunStepRecord)
                .where(
                    AutomationRunStepRecord.run_id == run.id,
                    AutomationRunStepRecord.status == "pending",
                )
                .order_by(
                    AutomationRunStepRecord.dependency_order,
                    AutomationRunStepRecord.scope_key,
                )
            )
        ).all()
        for step in steps:
            await self._execute_step(run, step, worker_id)
        await self._finalize_run(run.id)
        return await self.run_detail(run.id)

    async def _execute_step(
        self, run: AutomationRunRecord, step: AutomationRunStepRecord, worker_id: str
    ) -> None:
        now = datetime.now(UTC)
        step.status = "running"
        step.attempt_count += 1
        step.lease_owner = worker_id
        step.started_at = now
        step.heartbeat_at = now
        step.lease_expires_at = now + timedelta(minutes=self._settings.automation_lease_minutes)
        step.before_fingerprint = await self._artifact_fingerprint(
            step.step_key, step.symbol, step.scope_key
        )
        attempt = AutomationStepAttemptRecord(
            id=uuid4(),
            step_id=step.id,
            attempt_number=step.attempt_count,
            worker_id=worker_id,
            status="running",
            started_at=now,
        )
        self._session.add(attempt)
        await self._session.commit()
        started = perf_counter()
        try:
            skip_reason = await self._skip_reason(run.id, step)
            if skip_reason is not None:
                step.status = "skipped"
                step.error_code = skip_reason
                result = StepExecutionResult(status="skipped")
            else:
                result = await self._executor.execute(
                    step.step_key,
                    symbol=step.symbol,
                    universe_snapshot_id=run.universe_snapshot_id,
                    scope_key=step.scope_key,
                )
                step.after_fingerprint = await self._artifact_fingerprint(
                    step.step_key, step.symbol, step.scope_key
                )
                step.changed = step.before_fingerprint != step.after_fingerprint
                step.status = (
                    "skipped" if result.status == "skipped" or not step.changed else "succeeded"
                )
                step.provider_call_count = result.provider_calls
                step.rows_received = result.rows_received
                step.rows_written = result.rows_written
                run.signal_count += result.signal_count
                run.alert_count += result.alert_count
                run.ai_output_count += result.ai_output_count
            attempt.status = step.status
        except Exception as error:
            await self._session.rollback()
            persisted_step = await self._session.get(AutomationRunStepRecord, step.id)
            persisted_attempt = await self._session.get(AutomationStepAttemptRecord, attempt.id)
            assert persisted_step is not None and persisted_attempt is not None
            step = persisted_step
            attempt = persisted_attempt
            persisted_run = await self._session.get(AutomationRunRecord, run.id)
            assert persisted_run is not None
            run = persisted_run
            code = type(error).__name__[:120]
            step.status = "failed"
            step.error_code = code
            attempt.status = "failed"
            attempt.error_code = code
            attempt.retryable = _retryable(error)
        finally:
            duration = round((perf_counter() - started) * 1000)
            step.finished_at = datetime.now(UTC)
            step.duration_ms = duration
            step.lease_owner = None
            step.lease_expires_at = None
            step.heartbeat_at = None
            attempt.finished_at = step.finished_at
            attempt.duration_ms = duration
            run.heartbeat_at = step.finished_at
            run.lease_expires_at = step.finished_at + timedelta(
                minutes=self._settings.automation_lease_minutes
            )
            await self._session.commit()

    async def _skip_reason(self, run_id: UUID, step: AutomationRunStepRecord) -> str | None:
        if step.step_key == "financial_sync" and step.symbol:
            latest = await self._session.scalar(
                select(func.max(DataSyncRunRecord.finished_at)).where(
                    DataSyncRunRecord.dataset == "financial_statements",
                    DataSyncRunRecord.symbol == step.symbol,
                    DataSyncRunRecord.status == "succeeded",
                )
            )
            if latest is not None:
                revision = await self._session.get(
                    AutomationPolicyRevisionRecord,
                    (await self._session.get(AutomationRunRecord, run_id)).policy_revision_id,  # type: ignore[union-attr]
                )
                assert revision is not None
                config = AutomationPolicyConfiguration.model_validate(revision.configuration)
                hours = (
                    config.financial_reporting_interval_hours
                    if is_reporting_window(datetime.now(SHANGHAI).date())
                    else config.financial_normal_interval_hours
                )
                if latest > datetime.now(UTC) - timedelta(hours=hours):
                    return "financial_check_not_due"
        if step.step_key == "valuation_sync" and step.symbol:
            if not await self._changed_step(run_id, step.symbol, "market_sync"):
                if await self._artifact_exists("valuation_sync", step.symbol):
                    return "market_input_unchanged"
        if step.step_key == "fundamental_build" and step.symbol:
            changed = await self._changed_any(
                run_id, step.symbol, {"financial_sync", "valuation_sync"}
            )
            if not changed and await self._artifact_exists("fundamental_build", step.symbol):
                return "fundamental_input_unchanged"
        if step.step_key == "research_build" and step.symbol:
            if not await self._changed_step(run_id, step.symbol, "fundamental_build"):
                if await self._artifact_exists("research_build", step.symbol):
                    return "research_input_unchanged"
        if step.step_key == "signal_projection" and step.symbol:
            symbol_changed = await self._changed_any(
                run_id, step.symbol, {"research_build", "event_pipeline", "peer_research"}
            )
            peer_changed = bool(
                await self._session.scalar(
                    select(func.count())
                    .select_from(AutomationRunStepRecord)
                    .where(
                        AutomationRunStepRecord.run_id == run_id,
                        AutomationRunStepRecord.step_key == "peer_research",
                        AutomationRunStepRecord.changed.is_(True),
                    )
                )
            )
            if not symbol_changed and not peer_changed:
                return "signal_inputs_unchanged"
        if step.step_key == "ai_research" and step.symbol:
            if not self._settings.automation_ai_enabled or not self._settings.llm_enabled:
                return "automation_ai_disabled"
            if not await self._changed_step(run_id, step.symbol, "research_build"):
                return "ai_research_snapshot_unchanged"
            count = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(AutomationRunStepRecord)
                    .where(
                        AutomationRunStepRecord.run_id == run_id,
                        AutomationRunStepRecord.step_key == "ai_research",
                        AutomationRunStepRecord.status == "succeeded",
                    )
                )
                or 0
            )
            if count >= self._settings.automation_ai_max_calls_per_run:
                return "automation_ai_call_limit_reached"
        return None

    async def _changed_step(self, run_id: UUID, symbol: str, step_key: str) -> bool:
        return bool(
            await self._session.scalar(
                select(AutomationRunStepRecord.changed).where(
                    AutomationRunStepRecord.run_id == run_id,
                    AutomationRunStepRecord.symbol == symbol,
                    AutomationRunStepRecord.step_key == step_key,
                )
            )
        )

    async def _changed_any(self, run_id: UUID, symbol: str, keys: set[str]) -> bool:
        return bool(
            await self._session.scalar(
                select(func.count())
                .select_from(AutomationRunStepRecord)
                .where(
                    AutomationRunStepRecord.run_id == run_id,
                    AutomationRunStepRecord.symbol == symbol,
                    AutomationRunStepRecord.step_key.in_(keys),
                    AutomationRunStepRecord.changed.is_(True),
                )
            )
        )

    async def _artifact_exists(self, step_key: str, symbol: str) -> bool:
        models: dict[str, type[Any]] = {
            "valuation_sync": ValuationObservationRecord,
            "fundamental_build": FundamentalSnapshotRecord,
            "research_build": ResearchSnapshotRecord,
        }
        model = models.get(step_key)
        if model is None:
            return False
        return bool(
            await self._session.scalar(
                select(func.count()).select_from(model).where(model.symbol == symbol)
            )
        )

    async def _artifact_fingerprint(self, step_key: str, symbol: str | None, scope_key: str) -> str:
        if symbol is None:
            return stable_hash([])
        model_and_time: dict[str, tuple[type[Any], Any]] = {
            "market_sync": (StockDailyBarRecord, StockDailyBarRecord.trade_date),
            "financial_sync": (
                FinancialReportRevisionRecord,
                FinancialReportRevisionRecord.known_at,
            ),
            "valuation_sync": (ValuationObservationRecord, ValuationObservationRecord.trade_date),
            "fundamental_build": (
                FundamentalSnapshotRecord,
                FundamentalSnapshotRecord.calculated_at,
            ),
            "research_build": (ResearchSnapshotRecord, ResearchSnapshotRecord.generated_at),
            "event_pipeline": (EventRadarSnapshotRecord, EventRadarSnapshotRecord.generated_at),
            "peer_research": (
                CompanyPeerMetricPositionRecord,
                CompanyPeerMetricPositionRecord.created_at,
            ),
            "signal_projection": (ResearchSignalRecord, ResearchSignalRecord.created_at),
            "ai_research": (AIResearchOutputRecord, AIResearchOutputRecord.generated_at),
        }
        mapping = model_and_time.get(step_key)
        if mapping is None:
            return stable_hash([])
        model, timestamp = mapping
        symbols = [symbol]
        if step_key == "peer_research" and ":" in scope_key:
            taxonomy, version, industry = scope_key.split(":", 2)
            symbols = list(
                (
                    await self._session.scalars(
                        select(IndustryMembershipRecord.symbol)
                        .where(
                            IndustryMembershipRecord.taxonomy_code == taxonomy,
                            IndustryMembershipRecord.taxonomy_version == version,
                            IndustryMembershipRecord.industry_code == industry,
                        )
                        .distinct()
                    )
                ).all()
            )
        count, latest = (
            await self._session.execute(
                select(func.count(model.id), func.max(timestamp)).where(model.symbol.in_(symbols))
            )
        ).one()
        return stable_hash([(model.__tablename__, int(count or 0), latest)])

    async def _finalize_run(self, run_id: UUID) -> None:
        run = await self._session.get(AutomationRunRecord, run_id, with_for_update=True)
        assert run is not None
        steps = (
            await self._session.scalars(
                select(AutomationRunStepRecord).where(AutomationRunStepRecord.run_id == run.id)
            )
        ).all()
        counts = Counter(step.status for step in steps)
        ai_failures = sum(
            step.status == "failed" and step.step_key == "ai_research" for step in steps
        )
        required_failures = counts["failed"] - ai_failures
        run.total_steps = len(steps)
        run.succeeded_steps = counts["succeeded"]
        run.failed_steps = counts["failed"]
        run.skipped_steps = counts["skipped"]
        run.warning_steps = ai_failures
        run.provider_call_count = sum(step.provider_call_count for step in steps)
        run.rows_received = sum(step.rows_received for step in steps)
        run.rows_written = sum(step.rows_written for step in steps)
        if required_failures and counts["succeeded"]:
            run.status = "partial"
        elif required_failures:
            run.status = "failed"
        elif ai_failures:
            run.status = "succeeded_with_warnings"
        else:
            run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        run.lease_owner = None
        run.lease_expires_at = None
        run.heartbeat_at = None
        await self._session.commit()

    async def resume_run(self, run_id: UUID) -> AutomationTriggerResponse:
        run = await self._session.get(AutomationRunRecord, run_id, with_for_update=True)
        if run is None:
            raise ValueError("automation_run_not_found")
        if run.status not in {"failed", "partial", "succeeded_with_warnings"}:
            return AutomationTriggerResponse(
                status="skipped", run_id=run.id, run_status=cast(Any, run.status)
            )
        failed = (
            await self._session.scalars(
                select(AutomationRunStepRecord).where(
                    AutomationRunStepRecord.run_id == run.id,
                    AutomationRunStepRecord.status == "failed",
                )
            )
        ).all()
        first_failed_order = min((item.dependency_order for item in failed), default=10_000)
        for item in failed:
            item.status = "pending"
            item.error_code = None
        await self._session.execute(
            update(AutomationRunStepRecord)
            .where(
                AutomationRunStepRecord.run_id == run.id,
                AutomationRunStepRecord.dependency_order > first_failed_order,
                AutomationRunStepRecord.status == "skipped",
            )
            .values(status="pending", error_code=None)
        )
        run.status = "pending"
        run.finished_at = None
        await self._session.commit()
        return AutomationTriggerResponse(status="accepted", run_id=run.id, run_status="pending")

    async def list_runs(self, limit: int = 50) -> list[AutomationRunSummary]:
        rows = (
            await self._session.execute(
                select(AutomationRunRecord, AutomationPolicyRecord.policy_key)
                .join(
                    AutomationPolicyRecord,
                    AutomationPolicyRecord.id == AutomationRunRecord.policy_id,
                )
                .order_by(AutomationRunRecord.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [self._run_summary(run, key) for run, key in rows]

    async def run_detail(self, run_id: UUID) -> AutomationRunDetail:
        row = (
            await self._session.execute(
                select(
                    AutomationRunRecord,
                    AutomationPolicyRecord.policy_key,
                    AutomationPolicyRevisionRecord.revision,
                )
                .join(
                    AutomationPolicyRecord,
                    AutomationPolicyRecord.id == AutomationRunRecord.policy_id,
                )
                .join(
                    AutomationPolicyRevisionRecord,
                    AutomationPolicyRevisionRecord.id == AutomationRunRecord.policy_revision_id,
                )
                .where(AutomationRunRecord.id == run_id)
            )
        ).first()
        if row is None:
            raise ValueError("automation_run_not_found")
        run, policy_key, revision = row
        steps = (
            await self._session.scalars(
                select(AutomationRunStepRecord)
                .where(AutomationRunStepRecord.run_id == run.id)
                .order_by(
                    AutomationRunStepRecord.dependency_order,
                    AutomationRunStepRecord.scope_key,
                )
            )
        ).all()
        return AutomationRunDetail(
            **self._run_summary(run, policy_key).model_dump(),
            policy_revision=revision,
            policy_hash=run.policy_hash,
            universe_hash=run.universe_hash,
            universe_symbols=list(run.universe_snapshot.get("symbols", [])),
            steps=[self._step_view(step) for step in steps],
        )

    async def _create_missed_run(
        self,
        policy: AutomationPolicyRecord,
        revision: AutomationPolicyRevisionRecord,
        slot: datetime,
    ) -> None:
        key = stable_hash({"policy": str(policy.id), "slot": slot.isoformat(), "missed": True})
        if await self._session.scalar(
            select(AutomationRunRecord.id).where(AutomationRunRecord.idempotency_key == key)
        ):
            return
        self._session.add(
            AutomationRunRecord(
                id=uuid4(),
                policy_id=policy.id,
                policy_revision_id=revision.id,
                trigger_kind="scheduled",
                scheduled_for=slot,
                idempotency_key=key,
                policy_snapshot=revision.configuration,
                policy_hash=revision.configuration_hash,
                universe_snapshot={},
                status="skipped",
                error_code="missed_catchup_window",
                finished_at=datetime.now(UTC),
            )
        )
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()

    async def _load_policy(
        self, policy_key: str, *, lock: bool = False
    ) -> tuple[AutomationPolicyRecord, AutomationPolicyRevisionRecord]:
        await self.ensure_default_policy()
        statement = select(AutomationPolicyRecord).where(
            AutomationPolicyRecord.policy_key == policy_key
        )
        if lock:
            statement = statement.with_for_update()
        policy = await self._session.scalar(statement)
        if policy is None or policy.current_revision_id is None:
            raise ValueError("automation_policy_not_found")
        revision = await self._session.get(
            AutomationPolicyRevisionRecord, policy.current_revision_id
        )
        if revision is None:
            raise ValueError("automation_policy_revision_not_found")
        return policy, revision

    def _policy_view(
        self,
        policy: AutomationPolicyRecord,
        revision: AutomationPolicyRevisionRecord,
    ) -> AutomationPolicyView:
        return AutomationPolicyView(
            id=policy.id,
            policy_key=policy.policy_key,
            display_name=policy.display_name,
            enabled=policy.enabled,
            hard_disabled=self._settings.automation_hard_disabled,
            revision=revision.revision,
            configuration=AutomationPolicyConfiguration.model_validate(revision.configuration),
            configuration_hash=revision.configuration_hash,
            next_due_at=policy.next_due_at,
            last_evaluated_at=policy.last_evaluated_at,
            updated_at=policy.updated_at,
        )

    @staticmethod
    def _run_summary(run: AutomationRunRecord, policy_key: str) -> AutomationRunSummary:
        return AutomationRunSummary(
            id=run.id,
            policy_key=policy_key,
            trigger_kind=cast(Any, run.trigger_kind),
            scheduled_for=run.scheduled_for,
            status=cast(AutomationRunStatus, run.status),
            universe_size=int(run.universe_snapshot.get("size", 0)),
            total_steps=run.total_steps,
            succeeded_steps=run.succeeded_steps,
            failed_steps=run.failed_steps,
            skipped_steps=run.skipped_steps,
            warning_steps=run.warning_steps,
            provider_call_count=run.provider_call_count,
            rows_received=run.rows_received,
            rows_written=run.rows_written,
            signal_count=run.signal_count,
            alert_count=run.alert_count,
            ai_output_count=run.ai_output_count,
            error_code=run.error_code,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )

    @staticmethod
    def _step_view(step: AutomationRunStepRecord) -> AutomationStepView:
        return AutomationStepView(
            id=step.id,
            scope_type=cast(Any, step.scope_type),
            scope_key=step.scope_key,
            symbol=step.symbol,
            step_key=step.step_key,
            dependency_order=step.dependency_order,
            status=cast(Any, step.status),
            attempt_count=step.attempt_count,
            changed=step.changed,
            provider_call_count=step.provider_call_count,
            rows_received=step.rows_received,
            rows_written=step.rows_written,
            duration_ms=step.duration_ms,
            error_code=step.error_code,
            started_at=step.started_at,
            finished_at=step.finished_at,
        )


def _retryable(error: Exception) -> bool:
    name = type(error).__name__.lower()
    return any(token in name for token in ("timeout", "transient", "rate", "connection", "http"))
