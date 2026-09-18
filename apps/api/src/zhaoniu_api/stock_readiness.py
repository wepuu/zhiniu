from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    AIResearchOutputRecord,
    AutomationRunRecord,
    AutomationRunStepRecord,
    DataSyncRunRecord,
    EventRadarSnapshotRecord,
    PeerPositionObservationRecord,
    ResearchSnapshotRecord,
    StockDailyBarRecord,
    StockRecord,
    TradingSessionRecord,
)
from zhaoniu_api.domain.models import AdjustType, resolve_symbol
from zhaoniu_api.market_data.trading_calendar import (
    CALENDAR_PROVIDER,
    CALENDAR_SOURCE,
    CALENDAR_VERSION,
    calendar_health_status,
)
from zhaoniu_api.schemas import (
    MarketFreshness,
    StockReadinessResponse,
    StockReadinessStage,
    StockReadinessStatus,
)

StageKey = Literal["market", "deterministic_research", "extended_research", "ai_research"]
MARKET_PUBLICATION_GRACE = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class CalendarContext:
    expected_trade_date: date | None = None
    status: Literal["healthy", "stale", "unknown"] = "unknown"
    checked_at: datetime | None = None
    source: str | None = None
    calendar_version: str | None = None

_STAGE_STEPS: dict[StageKey, set[str]] = {
    "market": {"market_sync"},
    "deterministic_research": {
        "financial_sync",
        "valuation_sync",
        "fundamental_build",
        "research_build",
    },
    "extended_research": {"event_pipeline", "peer_research", "signal_projection"},
    "ai_research": {"ai_research"},
}


def market_data_freshness(
    bar: object | None,
    expected_trade_date: date | None,
) -> MarketFreshness:
    """Compare the latest retained bar with a source-backed calendar date.

    A missing calendar is deliberately ``unknown``.  Weekday arithmetic is
    not a safe substitute for exchange holidays, suspension days, or delayed
    provider delivery.
    """

    trade_date = getattr(bar, "trade_date", None)
    if not isinstance(trade_date, date) or expected_trade_date is None:
        return "unknown"
    if trade_date == expected_trade_date:
        return "current"
    if trade_date < expected_trade_date:
        return "stale"
    return "unknown"


class StockReadinessService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def get_many(self, symbols: list[str]) -> list[StockReadinessResponse]:
        canonical = list(dict.fromkeys(resolve_symbol(item).canonical for item in symbols))
        if not canonical:
            return []
        stocks = {
            row.symbol: row
            for row in (
                await self._session.scalars(
                    select(StockRecord).where(StockRecord.symbol.in_(canonical))
                )
            ).all()
        }
        missing = [symbol for symbol in canonical if symbol not in stocks]
        if missing:
            raise ValueError("stock_not_found")

        bars = await self._latest_by_symbol(
            StockDailyBarRecord.symbol,
            StockDailyBarRecord.trade_date,
            StockDailyBarRecord,
            canonical,
            extra=(StockDailyBarRecord.adjust_type == AdjustType.NONE),
        )
        research = await self._latest_by_symbol(
            ResearchSnapshotRecord.symbol,
            ResearchSnapshotRecord.generated_at,
            ResearchSnapshotRecord,
            canonical,
        )
        events = await self._latest_by_symbol(
            EventRadarSnapshotRecord.symbol,
            EventRadarSnapshotRecord.generated_at,
            EventRadarSnapshotRecord,
            canonical,
        )
        peers = await self._latest_by_symbol(
            PeerPositionObservationRecord.symbol,
            PeerPositionObservationRecord.created_at,
            PeerPositionObservationRecord,
            canonical,
        )
        ai_outputs = await self._latest_by_symbol(
            AIResearchOutputRecord.symbol,
            AIResearchOutputRecord.generated_at,
            AIResearchOutputRecord,
            canonical,
            extra=(AIResearchOutputRecord.research_type == "stock_health"),
        )
        calendar_context = await self._calendar_context(
            {stock.exchange for stock in stocks.values()}
        )
        step_rows = (
            await self._session.execute(
                select(AutomationRunStepRecord, AutomationRunRecord)
                .join(AutomationRunRecord, AutomationRunRecord.id == AutomationRunStepRecord.run_id)
                .where(AutomationRunStepRecord.symbol.in_(canonical))
                .order_by(AutomationRunStepRecord.created_at.desc())
            )
        ).all()
        steps: dict[str, dict[str, list[AutomationRunStepRecord]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for step, _run in step_rows:
            steps[step.symbol or ""][step.step_key].append(step)

        return [
            self._build(
                stocks[symbol],
                bars.get(symbol),
                research.get(symbol),
                events.get(symbol),
                peers.get(symbol),
                ai_outputs.get(symbol),
                steps.get(symbol, {}),
                calendar=calendar_context.get(stocks[symbol].exchange),
            )
            for symbol in canonical
        ]

    async def _latest_by_symbol(
        self,
        symbol_column: InstrumentedAttribute[str],
        order_column: InstrumentedAttribute[Any],
        record_type: type[Any],
        symbols: list[str],
        *,
        extra: ColumnElement[bool] | None = None,
    ) -> dict[str, Any]:
        statement = select(record_type).where(symbol_column.in_(symbols))
        if extra is not None:
            statement = statement.where(extra)
        statement = statement.distinct(symbol_column).order_by(symbol_column, order_column.desc())
        rows = (await self._session.scalars(statement)).all()
        return {str(row.symbol): row for row in rows}

    async def _calendar_context(self, exchanges: set[str]) -> dict[str, CalendarContext]:
        """Return source-backed dates only while the calendar audit is recent."""

        if not exchanges:
            return {}
        now = datetime.now(UTC)
        availability_cutoff = now - MARKET_PUBLICATION_GRACE
        checked_at = await self._session.scalar(
            select(func.max(DataSyncRunRecord.finished_at)).where(
                DataSyncRunRecord.dataset == "trading_calendar",
                DataSyncRunRecord.provider == CALENDAR_PROVIDER,
                DataSyncRunRecord.status == "succeeded",
            )
        )
        statement = (
            select(TradingSessionRecord)
            .where(
                TradingSessionRecord.exchange.in_(exchanges),
                TradingSessionRecord.is_open.is_(True),
                TradingSessionRecord.source == CALENDAR_SOURCE,
                TradingSessionRecord.calendar_version == CALENDAR_VERSION,
                TradingSessionRecord.trade_date <= now.date(),
                or_(
                    TradingSessionRecord.session_close_at <= availability_cutoff,
                    and_(
                        TradingSessionRecord.session_close_at.is_(None),
                        TradingSessionRecord.trade_date < now.date(),
                    ),
                ),
            )
            .distinct(TradingSessionRecord.exchange)
            .order_by(
                TradingSessionRecord.exchange,
                TradingSessionRecord.trade_date.desc(),
                TradingSessionRecord.ingested_at.desc(),
            )
        )
        rows = (await self._session.scalars(statement)).all()
        latest_rows: dict[str, TradingSessionRecord] = {}
        for row in rows:
            latest_rows.setdefault(row.exchange, row)
        result: dict[str, CalendarContext] = {}
        for exchange in exchanges:
            latest_row = latest_rows.get(exchange)
            if latest_row is None:
                result[exchange] = CalendarContext()
                continue
            if checked_at is None:
                result[exchange] = CalendarContext(
                    source=latest_row.source,
                    calendar_version=latest_row.calendar_version,
                )
                continue
            normalized_check = (
                checked_at.replace(tzinfo=UTC)
                if checked_at.tzinfo is None
                else checked_at.astimezone(UTC)
            )
            status = calendar_health_status(normalized_check, now=now)
            result[exchange] = CalendarContext(
                expected_trade_date=(
                    latest_row.trade_date if status == "healthy" else None
                ),
                status=status,
                checked_at=normalized_check,
                source=latest_row.source,
                calendar_version=latest_row.calendar_version,
            )
        return result

    def _task_state(
        self, step_groups: dict[str, list[AutomationRunStepRecord]], stage: StageKey
    ) -> tuple[StockReadinessStatus | None, datetime | None, str | None]:
        relevant = [step for key in _STAGE_STEPS[stage] for step in step_groups.get(key, [])[:1]]
        if any(step.status == "running" for step in relevant):
            return (
                "preparing",
                max((step.started_at for step in relevant if step.started_at), default=None),
                None,
            )
        if any(step.status == "pending" for step in relevant):
            return "queued", max(step.created_at for step in relevant), None
        failed = next((step for step in relevant if step.status in {"failed", "blocked"}), None)
        if failed is not None:
            return (
                "failed",
                failed.finished_at or failed.created_at,
                failed.error_code or "preparation_failed",
            )
        completed = next(
            (step for step in relevant if step.status in {"succeeded", "skipped"}), None
        )
        if completed is not None:
            if stage == "extended_research":
                return (
                    "partial",
                    completed.finished_at or completed.created_at,
                    completed.error_code or "extended_source_partial",
                )
            return (
                "failed",
                completed.finished_at or completed.created_at,
                completed.error_code or "artifact_not_built",
            )
        return None, None, None

    def _build(
        self,
        stock: StockRecord,
        bar: object | None,
        research: object | None,
        event: object | None,
        peer: object | None,
        ai_output: object | None,
        step_groups: dict[str, list[AutomationRunStepRecord]],
        *,
        expected_trade_date: date | None = None,
        calendar: CalendarContext | None = None,
    ) -> StockReadinessResponse:
        if calendar is None:
            calendar = CalendarContext(expected_trade_date=expected_trade_date)
        effective_expected_date = calendar.expected_trade_date
        stages: list[StockReadinessStage] = []

        def stage(
            key: StageKey,
            artifact: object | None,
            timestamp_name: str,
            *,
            unsupported: bool = False,
        ) -> StockReadinessStage:
            if artifact is not None:
                return StockReadinessStage(
                    key=key,
                    status="ready",
                    progress=100,
                    updated_at=getattr(artifact, timestamp_name),
                )
            if unsupported:
                return StockReadinessStage(
                    key=key,
                    status="unsupported",
                    progress=100,
                    reason_code="issuer_template_unsupported",
                )
            task_status, updated_at, reason = self._task_state(step_groups, key)
            if task_status is not None:
                progress = (
                    15 if task_status == "queued" else 60 if task_status == "preparing" else 0
                )
                return StockReadinessStage(
                    key=key,
                    status=task_status,
                    progress=progress,
                    reason_code=reason,
                    updated_at=updated_at,
                )
            paused = (
                self._settings.automation_hard_disabled
                or not self._settings.watchlist_preparation_enabled
            )
            return StockReadinessStage(
                key=key,
                status="paused" if paused else "queued",
                progress=0,
                reason_code="preparation_disabled" if paused else "preparation_pending",
            )

        stages.append(stage("market", bar, "collected_at"))
        stages.append(
            stage(
                "deterministic_research",
                research,
                "generated_at",
                unsupported=stock.issuer_type != "general",
            )
        )
        event_stage = stage("extended_research", event, "generated_at")
        if event is not None and peer is None:
            event_stage.status = "partial"
            event_stage.reason_code = "peer_research_unavailable"
        elif event is None and peer is not None:
            event_stage.status = "partial"
            event_stage.progress = 50
            event_stage.updated_at = peer.created_at  # type: ignore[attr-defined]
            event_stage.reason_code = "event_research_unavailable"
        stages.append(event_stage)
        ai_stage = stage(
            "ai_research",
            ai_output,
            "generated_at",
            unsupported=stock.issuer_type != "general",
        )
        if ai_output is None and not self._settings.automation_ai_enabled:
            ai_stage.status = "paused"
            ai_stage.progress = 0
            ai_stage.reason_code = "automatic_ai_disabled"
        stages.append(ai_stage)

        core_ready = stages[0].status == "ready" and stages[1].status in {"ready", "unsupported"}
        if any(item.status == "preparing" for item in stages):
            overall: StockReadinessStatus = "preparing"
        elif any(item.status == "queued" for item in stages):
            overall = "queued"
        elif core_ready and all(item.status == "ready" for item in stages):
            overall = "ready"
        elif core_ready:
            overall = "partial"
        elif any(item.status == "failed" for item in stages):
            overall = "failed"
        else:
            overall = "paused"
        completed = sum(item.progress for item in stages) // len(stages)
        updated_values = [item.updated_at for item in stages if item.updated_at is not None]
        return StockReadinessResponse(
            symbol=stock.ticker,
            canonical_symbol=stock.symbol,
            name=stock.name,
            overall_status=overall,
            progress=completed,
            updated_at=max(updated_values, default=None),
            latest_price=getattr(bar, "close", None),
            latest_trade_date=getattr(bar, "trade_date", None),
            market_freshness=market_data_freshness(bar, effective_expected_date),
            expected_trade_date=effective_expected_date,
            calendar_status=calendar.status,
            calendar_checked_at=calendar.checked_at,
            stages=stages,
        )
