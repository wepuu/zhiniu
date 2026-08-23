from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from zhaoniu_api.domain.models import AdjustType, Board, DailyBar, Exchange, resolve_symbol
from zhaoniu_api.market_data.akshare_provider import AKShareProvider
from zhaoniu_api.market_data.errors import (
    DataQualityError,
    ProviderConnectionError,
    ProviderInvalidResponseError,
    ProviderProxyUnavailableError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    safe_market_error_code,
)
from zhaoniu_api.market_data.normalizer import AKShareNormalizer
from zhaoniu_api.market_data.quality import validate_daily_bar_batch
from zhaoniu_api.market_data.registry import FallbackEngine
from zhaoniu_api.market_data.service import make_idempotency_key
from zhaoniu_api.ports.providers import RawDailyBar


@pytest.mark.parametrize(
    ("value", "canonical", "exchange", "board"),
    [
        ("600519", "600519.SH", Exchange.SSE, Board.MAIN),
        ("000001.SZ", "000001.SZ", Exchange.SZSE, Board.MAIN),
        ("300750", "300750.SZ", Exchange.SZSE, Board.CHINEXT),
        ("688981.SH", "688981.SH", Exchange.SSE, Board.STAR),
        ("002594", "002594.SZ", Exchange.SZSE, Board.SME),
        ("003000", "003000.SZ", Exchange.SZSE, Board.MAIN),
        ("301308", "301308.SZ", Exchange.SZSE, Board.CHINEXT),
        ("302132", "302132.SZ", Exchange.SZSE, Board.CHINEXT),
    ],
)
def test_symbol_resolution(value: str, canonical: str, exchange: Exchange, board: Board) -> None:
    resolved = resolve_symbol(value)
    assert (resolved.canonical, resolved.exchange, resolved.board) == (
        canonical,
        exchange,
        board,
    )


def test_symbol_rejects_mismatched_suffix() -> None:
    with pytest.raises(ValueError):
        resolve_symbol("600519.SZ")


def test_akshare_fixture_normalization_uses_decimal_and_source_units() -> None:
    rows = [
        RawDailyBar(
            provider="akshare",
            requested_symbol="600519",
            payload={
                "日期": "2026-08-14",
                "开盘": "1410.10",
                "最高": "1445.00",
                "最低": "1408.20",
                "收盘": "1438.20",
                "涨跌额": "8.86",
                "成交量": "1234567",
                "成交额": "1760000000.12",
            },
        )
    ]
    bar = AKShareNormalizer().daily_bars(rows)[0]
    assert bar.close == Decimal("1438.20")
    assert bar.pre_close == Decimal("1429.34")
    assert bar.volume == 123456700
    assert bar.amount == Decimal("1760000000.12")
    assert bar.pct_change == Decimal("0.6199")


def _bar(**changes: object) -> DailyBar:
    values: dict[str, object] = {
        "canonical_symbol": "600519.SH",
        "trade_date": date(2026, 8, 14),
        "adjust_type": AdjustType.NONE,
        "open": Decimal("10"),
        "high": Decimal("12"),
        "low": Decimal("9"),
        "close": Decimal("11"),
        "pre_close": Decimal("10"),
        "volume": 10,
        "amount": Decimal("100"),
        "source": "fixture",
        "collected_at": datetime(2026, 8, 15, tzinfo=UTC),
    }
    values.update(changes)
    return DailyBar(**values)  # type: ignore[arg-type]


def test_quality_rejects_whole_invalid_or_duplicate_batch() -> None:
    with pytest.raises(DataQualityError):
        validate_daily_bar_batch([_bar(high=Decimal("10"))], "600519.SH")
    with pytest.raises(DataQualityError):
        validate_daily_bar_batch([_bar(), _bar()], "600519.SH")


class _FailingProvider:
    name = "failed"

    async def get_stock_master(self):  # type: ignore[no-untyped-def]
        raise ProviderUnavailableError("offline")

    async def get_daily_bars(self, symbol, start, end):  # type: ignore[no-untyped-def]
        raise ProviderUnavailableError("offline")


class _WorkingProvider:
    name = "working"

    async def get_stock_master(self):  # type: ignore[no-untyped-def]
        return []

    async def get_daily_bars(self, symbol, start, end):  # type: ignore[no-untyped-def]
        return []


async def test_fake_fallback_classifies_failure_and_uses_next_provider() -> None:
    name, rows = await FallbackEngine([_FailingProvider(), _WorkingProvider()]).daily_bars(
        "600519", date(2026, 1, 1), date(2026, 1, 2)
    )
    assert (name, rows) == ("working", [])


def test_idempotency_key_is_deterministic_and_window_sensitive() -> None:
    one = make_idempotency_key("daily", "600519.SH", date(2026, 1, 1))
    assert one == make_idempotency_key("daily", "600519.SH", date(2026, 1, 1))
    assert one != make_idempotency_key("daily", "600519.SH", date(2026, 1, 2))


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (type("ProxyError", (Exception,), {})(), ProviderProxyUnavailableError),
        (TimeoutError(), ProviderTimeoutError),
        (ConnectionError(), ProviderConnectionError),
        (RuntimeError("HTTP 429"), ProviderRateLimitedError),
    ],
)
async def test_akshare_retries_only_transient_failures(
    failure: Exception, expected: type[Exception]
) -> None:
    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise failure

    provider = AKShareProvider(max_attempts=2, retry_backoff_seconds=0)
    with pytest.raises(expected):
        await provider._call(fail)
    assert calls == 2


async def test_akshare_does_not_retry_invalid_response() -> None:
    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("unexpected payload")

    provider = AKShareProvider(max_attempts=2, retry_backoff_seconds=0)
    with pytest.raises(ProviderInvalidResponseError) as captured:
        await provider._call(fail)
    assert calls == 1
    assert str(captured.value) == "provider_invalid_response"


def test_market_provider_error_codes_are_safe_and_stable() -> None:
    assert safe_market_error_code(ProviderConnectionError("remote secret URL")) == (
        "provider_connection_failed"
    )
    assert safe_market_error_code(RuntimeError("token=secret")) == "provider_invalid_response"
