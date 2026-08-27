from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from zhaoniu_api.automation.service import AutomationService
from zhaoniu_api.config import Settings
from zhaoniu_api.db import StockRecord
from zhaoniu_api.stock_readiness import StockReadinessService


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


async def test_watchlist_preparation_switch_fails_closed_without_database_work() -> None:
    service = AutomationService(  # type: ignore[arg-type]
        None,
        Settings(automation_hard_disabled=False, watchlist_preparation_enabled=False),
    )

    status, result = await service.request_watchlist_preparation("600519")

    assert status == "paused"
    assert result is None
