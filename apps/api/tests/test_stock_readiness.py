from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from zhaoniu_api.automation.service import AutomationService
from zhaoniu_api.config import Settings
from zhaoniu_api.db import StockRecord
from zhaoniu_api.stock_readiness import (
    CalendarContext,
    StockReadinessService,
    market_data_freshness,
)


def _stock(*, issuer_type: str = "general") -> StockRecord:
    return StockRecord(
        symbol="600519.SH",
        ticker="600519",
        name="贵州茅台",
        search_name="贵州茅台",
        name_pinyin="guizhoumaotai",
        name_pinyin_initials="gzmt",
        exchange="SSE",
        asset_type="stock",
        board="main",
        status="listed",
        issuer_type=issuer_type,
        source="fixture",
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
    )


def test_readiness_is_paused_when_preparation_switch_is_closed() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=False),
    )
    result = service._build(_stock(), None, None, None, None, None, {})

    assert result.overall_status == "paused"
    assert result.next_action == "enable_preparation"
    assert result.blocking_reason_code == "preparation_disabled"
    assert {stage.status for stage in result.stages} == {"paused"}


def test_readiness_exposes_core_data_while_extended_and_ai_are_partial() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(
            automation_hard_disabled=False,
            watchlist_preparation_enabled=True,
            automation_ai_enabled=False,
        ),
    )
    bar = SimpleNamespace(
        close=Decimal("1292.30"),
        trade_date=date(2026, 8, 27),
        collected_at=datetime(2026, 8, 27, tzinfo=UTC),
    )
    research = SimpleNamespace(generated_at=datetime(2026, 8, 27, tzinfo=UTC))
    event = SimpleNamespace(generated_at=datetime(2026, 8, 27, tzinfo=UTC))

    result = service._build(_stock(), bar, research, event, None, None, {})

    assert result.overall_status == "partial"
    assert result.latest_price == Decimal("1292.30")
    assert result.stages[2].status == "partial"
    assert result.stages[3].reason_code == "automatic_ai_disabled"


def test_market_freshness_requires_a_source_backed_calendar() -> None:
    bar = SimpleNamespace(trade_date=date(2026, 8, 28))

    assert market_data_freshness(bar, date(2026, 8, 28)) == "current"
    assert market_data_freshness(bar, date(2026, 8, 29)) == "stale"
    assert market_data_freshness(bar, None) == "unknown"
    assert (
        market_data_freshness(
            SimpleNamespace(trade_date=date(2026, 8, 30)),
            date(2026, 8, 28),
        )
        == "unknown"
    )


def test_readiness_exposes_market_freshness_without_blocking_core_data() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=True),
    )
    bar = SimpleNamespace(
        close=Decimal("1292.30"),
        trade_date=date(2026, 8, 27),
        collected_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    result = service._build(
        _stock(),
        bar,
        None,
        None,
        None,
        None,
        {},
        expected_trade_date=date(2026, 8, 28),
    )

    assert result.market_freshness == "stale"
    assert result.expected_trade_date == date(2026, 8, 28)
    assert result.stages[0].status == "ready"


def test_stale_calendar_suppresses_a_false_market_freshness_claim() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=True),
    )
    checked_at = datetime(2026, 8, 26, tzinfo=UTC)
    bar = SimpleNamespace(
        close=Decimal("1292.30"),
        trade_date=date(2026, 8, 27),
        collected_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    result = service._build(
        _stock(),
        bar,
        None,
        None,
        None,
        None,
        {},
        calendar=CalendarContext(
            status="stale",
            checked_at=checked_at,
            source="akshare_sina",
            calendar_version="sina-trading-calendar-v1",
        ),
    )

    assert result.market_freshness == "unknown"
    assert result.expected_trade_date is None
    assert result.calendar_status == "stale"
    assert result.calendar_checked_at == checked_at


def test_stalled_preparation_is_not_reported_as_78_percent_queued() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(
            automation_hard_disabled=False,
            automation_ai_enabled=True,
            watchlist_preparation_enabled=True,
        ),
    )
    stale = SimpleNamespace(
        status="pending",
        created_at=datetime.now(UTC) - timedelta(minutes=11),
        started_at=None,
        finished_at=None,
        error_code=None,
    )

    result = service._build(
        _stock(),
        SimpleNamespace(
            close=Decimal("1292.30"),
            trade_date=date(2026, 8, 27),
            collected_at=datetime(2026, 8, 27, tzinfo=UTC),
        ),
        SimpleNamespace(generated_at=datetime(2026, 8, 27, tzinfo=UTC)),
        SimpleNamespace(generated_at=datetime(2026, 8, 27, tzinfo=UTC)),
        None,
        None,
        {"ai_research": [stale]},
    )

    assert result.stages[3].status == "failed"
    assert result.stages[3].reason_code == "preparation_stalled"
    assert result.progress == 75
    assert result.next_action == "retry"
    assert result.blocking_reason_code == "preparation_stalled"


def test_readiness_exposes_successful_and_next_scheduled_refresh_times() -> None:
    service = StockReadinessService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=True),
    )
    finished_at = datetime(2026, 9, 25, 11, 35, tzinfo=UTC)
    next_due_at = datetime(2026, 9, 26, 11, 30, tzinfo=UTC)
    succeeded = SimpleNamespace(
        status="succeeded",
        created_at=datetime(2026, 9, 25, 11, 30, tzinfo=UTC),
        started_at=datetime(2026, 9, 25, 11, 30, tzinfo=UTC),
        finished_at=finished_at,
        error_code=None,
    )

    result = service._build(
        _stock(),
        SimpleNamespace(
            close=Decimal("1292.30"),
            trade_date=date(2026, 9, 25),
            collected_at=finished_at,
        ),
        None,
        None,
        None,
        None,
        {"market_sync": [succeeded]},
        next_scheduled_refresh_at=next_due_at,
    )

    assert result.last_successful_refresh_at == finished_at
    assert result.next_scheduled_refresh_at == next_due_at


class _ScheduledSymbolSession:
    async def scalars(self, _statement: object) -> "_ScheduledSymbolSession":
        return self

    def all(self) -> list[str]:
        return ["300750.SZ"]


async def test_next_scheduled_refresh_is_limited_to_the_daily_universe() -> None:
    service = StockReadinessService(
        _ScheduledSymbolSession(),  # type: ignore[arg-type]
        Settings(
            coverage_operator_pinned_symbols="600519.SH",
            coverage_acceptance_symbols="",
        ),
    )

    scheduled = await service._scheduled_symbols(  # noqa: SLF001
        ["600519.SH", "300750.SZ", "300376.SZ"]
    )

    assert scheduled == {"600519.SH", "300750.SZ"}


async def test_watchlist_preparation_switch_fails_closed_without_database_work() -> None:
    service = AutomationService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=False),
    )

    status, result = await service.request_watchlist_preparation("600519")

    assert status == "paused"
    assert result is None
