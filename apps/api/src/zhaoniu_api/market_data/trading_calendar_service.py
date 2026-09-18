from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from zhaoniu_api.market_data.errors import safe_market_error_code
from zhaoniu_api.market_data.service import make_idempotency_key
from zhaoniu_api.market_data.trading_calendar import (
    CALENDAR_VERSION,
    CN_TZ,
    AKShareTradingCalendarNormalizer,
)
from zhaoniu_api.ports.providers import TradingCalendarProvider
from zhaoniu_api.ports.repositories import SyncRunRepository, TradingSessionRepository


@dataclass(frozen=True, slots=True)
class TradingCalendarSyncResult:
    status: str
    provider: str
    calendar_version: str
    received_count: int
    written_count: int
    idempotency_key: str
    requested_start: date
    requested_end: date


class TradingCalendarSyncService:
    def __init__(
        self,
        *,
        provider: TradingCalendarProvider,
        normalizer: AKShareTradingCalendarNormalizer,
        sessions: TradingSessionRepository,
        runs: SyncRunRepository,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._sessions = sessions
        self._runs = runs

    async def sync(
        self,
        *,
        start: date = date(1992, 5, 4),
        end: date | None = None,
        force: bool = False,
    ) -> TradingCalendarSyncResult:
        final_end = end or datetime.now(CN_TZ).date()
        key = make_idempotency_key(
            "trading-calendar",
            self._provider.name,
            CALENDAR_VERSION,
            start,
            final_end,
        )
        if not force and await self._runs.was_successful(key):
            return TradingCalendarSyncResult(
                status="skipped",
                provider=self._provider.name,
                calendar_version=CALENDAR_VERSION,
                received_count=0,
                written_count=0,
                idempotency_key=key,
                requested_start=start,
                requested_end=final_end,
            )
        run_id = await self._runs.start(
            dataset="trading_calendar",
            provider=self._provider.name,
            canonical_symbol=None,
            requested_start=start,
            requested_end=final_end,
            idempotency_key=key,
        )
        received = 0
        try:
            raw = await self._provider.get_trading_sessions(start, final_end)
            received = len(raw)
            normalized = self._normalizer.sessions(raw, start=start, end=final_end)
            written = await self._sessions.upsert_many(normalized)
            finished = datetime.now(UTC)
            await self._runs.finish(
                run_id,
                status="succeeded",
                received_count=received,
                written_count=written,
                error_summary=None,
                finished_at=finished,
            )
            return TradingCalendarSyncResult(
                status="succeeded",
                provider=self._provider.name,
                calendar_version=CALENDAR_VERSION,
                received_count=received,
                written_count=written,
                idempotency_key=key,
                requested_start=start,
                requested_end=final_end,
            )
        except Exception as exc:
            await self._runs.finish(
                run_id,
                status="failed",
                received_count=received,
                written_count=0,
                error_summary=safe_market_error_code(exc),
                finished_at=datetime.now(UTC),
            )
            raise
