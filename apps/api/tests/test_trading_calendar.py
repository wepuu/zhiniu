from datetime import UTC, date, datetime, timedelta

import pytest
from zhaoniu_api.market_data.akshare_calendar_provider import AKShareTradingCalendarProvider
from zhaoniu_api.market_data.errors import (
    DataNormalizationError,
    ProviderConnectionError,
    ProviderInvalidResponseError,
)
from zhaoniu_api.market_data.trading_calendar import (
    CALENDAR_SOURCE,
    CALENDAR_VERSION,
    AKShareTradingCalendarNormalizer,
    calendar_health_status,
)
from zhaoniu_api.market_data.trading_calendar_service import TradingCalendarSyncService
from zhaoniu_api.ports.providers import RawTradingSession


class _Frame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self._records


class _CalendarSDK:
    def __init__(self, records: list[dict[str, object]] | Exception) -> None:
        self.records = records

    def tool_trade_date_hist_sina(self) -> _Frame:
        if isinstance(self.records, Exception):
            raise self.records
        return _Frame(self.records)


async def test_akshare_calendar_emits_sse_and_szse_rows() -> None:
    provider = AKShareTradingCalendarProvider(
        sdk=_CalendarSDK([{"trade_date": date(2026, 8, 28)}]),
        max_attempts=1,
        retry_backoff_seconds=0,
    )

    rows = await provider.get_trading_sessions(date(2026, 8, 1), date(2026, 8, 31))

    assert provider.name == "akshare_sina_calendar"
    assert [(row.exchange, row.provider) for row in rows] == [
        ("SSE", CALENDAR_SOURCE),
        ("SZSE", CALENDAR_SOURCE),
    ]


async def test_akshare_calendar_reuses_transient_error_classification() -> None:
    provider = AKShareTradingCalendarProvider(
        sdk=_CalendarSDK(ConnectionError("remote disconnected")),
        max_attempts=1,
        retry_backoff_seconds=0,
    )

    with pytest.raises(ProviderConnectionError):
        await provider.get_trading_sessions(date(2026, 1, 1), date(2026, 1, 2))


async def test_akshare_calendar_rejects_an_empty_upstream_response() -> None:
    provider = AKShareTradingCalendarProvider(
        sdk=_CalendarSDK([]),
        max_attempts=1,
        retry_backoff_seconds=0,
    )

    with pytest.raises(ProviderInvalidResponseError, match="empty"):
        await provider.get_trading_sessions(date(2026, 1, 1), date(2026, 1, 2))


def test_calendar_normalizer_filters_and_sets_china_session_boundaries() -> None:
    rows = [
        RawTradingSession(
            provider=CALENDAR_SOURCE,
            exchange="SSE",
            payload={"trade_date": "2026-08-28"},
        ),
        RawTradingSession(
            provider=CALENDAR_SOURCE,
            exchange="SSE",
            payload={"trade_date": "2026-08-27"},
        ),
        RawTradingSession(
            provider=CALENDAR_SOURCE,
            exchange="SZSE",
            payload={"trade_date": "2025-12-31"},
        ),
    ]
    ingested = datetime(2026, 8, 29, tzinfo=UTC)

    sessions = AKShareTradingCalendarNormalizer().sessions(
        rows,
        start=date(2026, 8, 27),
        end=date(2026, 8, 28),
        ingested_at=ingested,
    )

    assert [(item.exchange, item.trade_date) for item in sessions] == [
        ("SSE", date(2026, 8, 27)),
        ("SSE", date(2026, 8, 28)),
    ]
    assert sessions[0].session_open_at == datetime(2026, 8, 27, 1, 30, tzinfo=UTC)
    assert sessions[0].session_close_at == datetime(2026, 8, 27, 7, tzinfo=UTC)
    assert sessions[0].calendar_version == CALENDAR_VERSION
    assert sessions[0].known_at == ingested
    assert len(sessions[0].lineage_hash) == 64


def test_calendar_health_requires_a_recent_successful_check() -> None:
    now = datetime(2026, 8, 29, 12, tzinfo=UTC)

    assert calendar_health_status(None, now=now) == "unknown"
    assert (
        calendar_health_status(now - timedelta(hours=35), now=now)
        == "healthy"
    )
    assert calendar_health_status(now - timedelta(hours=37), now=now) == "stale"
    assert calendar_health_status(now + timedelta(minutes=1), now=now) == "unknown"


def test_calendar_normalizer_rejects_duplicate_exchange_dates() -> None:
    row = RawTradingSession(
        provider=CALENDAR_SOURCE,
        exchange="SSE",
        payload={"trade_date": "2026-08-28"},
    )

    with pytest.raises(DataNormalizationError, match="duplicate"):
        AKShareTradingCalendarNormalizer().sessions(
            [row, row],
            start=date(2026, 8, 28),
            end=date(2026, 8, 28),
        )


class _Runs:
    def __init__(self, successful: bool = False) -> None:
        self.successful = successful
        self.started: list[dict[str, object]] = []
        self.finished: list[dict[str, object]] = []

    async def was_successful(self, _key: str) -> bool:
        return self.successful

    async def start(self, **values: object) -> str:
        self.started.append(values)
        return "calendar-run"

    async def finish(self, run_id: str, **values: object) -> None:
        self.finished.append({"run_id": run_id, **values})


class _Sessions:
    def __init__(self) -> None:
        self.values = []

    async def upsert_many(self, sessions):  # type: ignore[no-untyped-def]
        self.values.extend(sessions)
        return len(sessions)


class _Provider:
    name = "fixture-calendar"

    async def get_trading_sessions(self, start: date, end: date):  # type: ignore[no-untyped-def]
        return [
            RawTradingSession(
                provider=CALENDAR_SOURCE,
                exchange="SSE",
                payload={"trade_date": start},
            )
        ]


@pytest.mark.asyncio
async def test_calendar_sync_is_idempotent_and_audited() -> None:
    runs = _Runs()
    sessions = _Sessions()
    service = TradingCalendarSyncService(
        provider=_Provider(),
        normalizer=AKShareTradingCalendarNormalizer(),
        sessions=sessions,
        runs=runs,
    )

    result = await service.sync(start=date(2026, 8, 28), end=date(2026, 8, 28))

    assert result.status == "succeeded"
    assert result.received_count == 1
    assert result.written_count == 1
    assert len(runs.started) == 1
    assert runs.finished[0]["status"] == "succeeded"
    assert sessions.values[0].trade_date == date(2026, 8, 28)


@pytest.mark.asyncio
async def test_calendar_sync_skips_a_successful_same_day_run() -> None:
    runs = _Runs(successful=True)
    sessions = _Sessions()
    service = TradingCalendarSyncService(
        provider=_Provider(),
        normalizer=AKShareTradingCalendarNormalizer(),
        sessions=sessions,
        runs=runs,
    )

    result = await service.sync(start=date(2026, 8, 28), end=date(2026, 8, 28))

    assert result.status == "skipped"
    assert not runs.started
    assert not sessions.values
