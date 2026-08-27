import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.config import get_settings
from zhaoniu_api.db import DataSyncRunRecord, StockDailyBarRecord, StockRecord
from zhaoniu_api.domain.models import AdjustType, DailyBar, Stock
from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyDailyBarRepository,
    SQLAlchemyStockRepository,
    SQLAlchemySyncRunRepository,
)
from zhaoniu_api.market_data.normalizer import AKShareNormalizer
from zhaoniu_api.market_data.service import MarketDataSyncService
from zhaoniu_api.ports.providers import RawDailyBar, RawStock

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class FixtureProvider:
    name = "fixture"

    def __init__(self) -> None:
        self.window: tuple[date, date] | None = None

    async def get_stock_master(self) -> list[RawStock]:
        return [RawStock(provider=self.name, payload={"code": "601998", "name": "纵切测试"})]

    async def get_daily_bars(self, symbol: str, start: date, end: date) -> list[RawDailyBar]:
        self.window = (start, end)
        return [
            RawDailyBar(
                provider=self.name,
                requested_symbol=symbol,
                payload={
                    "日期": "2026-08-14",
                    "开盘": "10",
                    "最高": "12",
                    "最低": "9",
                    "收盘": "11",
                    "昨收": "10",
                    "成交量": "100",
                    "成交额": "1100",
                },
            )
        ]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_postgres_upserts_are_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    assert TEST_DATABASE_URL != get_settings().database_url
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    symbol = "601999.SH"
    timestamp = datetime(2026, 8, 16, tzinfo=UTC)
    stock = Stock(
        symbol="601999",
        canonical_symbol=symbol,
        name="集成测试股份",
        exchange="SSE",
        board="main",
        source="fixture",
        collected_at=timestamp,
    )
    bar = DailyBar(
        canonical_symbol=symbol,
        trade_date=date(2026, 8, 14),
        adjust_type=AdjustType.NONE,
        open=Decimal("10.00"),
        high=Decimal("12.00"),
        low=Decimal("9.00"),
        close=Decimal("11.00"),
        pre_close=Decimal("10.00"),
        volume=100,
        amount=Decimal("1100.00"),
        source="fixture",
        collected_at=timestamp,
    )
    try:
        async with sessions() as session:
            stocks = SQLAlchemyStockRepository(session)
            bars = SQLAlchemyDailyBarRepository(session)
            await stocks.upsert_many([stock])
            await stocks.upsert_many([stock])
            await bars.upsert_many([bar])
            await bars.upsert_many([bar])
            stock_count = await session.scalar(
                select(func.count()).select_from(StockRecord).where(StockRecord.symbol == symbol)
            )
            bar_count = await session.scalar(
                select(func.count())
                .select_from(StockDailyBarRecord)
                .where(StockDailyBarRecord.symbol == symbol)
            )
            assert (stock_count, bar_count) == (1, 1)
            assert (await stocks.get("601999")).latest_price == Decimal("11.000000")  # type: ignore[union-attr]
            assert [item.canonical_symbol for item in await stocks.search("jichengceshi")] == [
                symbol
            ]
            assert [item.canonical_symbol for item in await stocks.search("jccsgf")] == [symbol]
            listed = await bars.list_for_symbol(symbol, start=None, end=None, limit=120)
            assert [item.trade_date for item in listed] == [date(2026, 8, 14)]
    finally:
        async with sessions() as session:
            await session.execute(
                delete(DataSyncRunRecord).where(DataSyncRunRecord.symbol == symbol)
            )
            await session.execute(
                delete(StockDailyBarRecord).where(StockDailyBarRecord.symbol == symbol)
            )
            await session.execute(delete(StockRecord).where(StockRecord.symbol == symbol))
            await session.commit()
        await engine.dispose()


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_application_service_reaches_postgres_repositories() -> None:
    assert TEST_DATABASE_URL is not None
    assert TEST_DATABASE_URL != get_settings().database_url
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    symbol = "601998.SH"
    try:
        async with sessions() as session:
            stocks = SQLAlchemyStockRepository(session)
            bars = SQLAlchemyDailyBarRepository(session)
            provider = FixtureProvider()
            service = MarketDataSyncService(
                provider=provider,
                normalizer=AKShareNormalizer(),
                stocks=stocks,
                bars=bars,
                runs=SQLAlchemySyncRunRepository(session),
            )
            master_result = await service.sync_stock_master(force=True, today=date(2026, 8, 16))
            await bars.upsert_many(
                [
                    DailyBar(
                        canonical_symbol=symbol,
                        trade_date=date(2026, 8, 13),
                        adjust_type=AdjustType.NONE,
                        open=Decimal("9"),
                        high=Decimal("11"),
                        low=Decimal("8"),
                        close=Decimal("10"),
                        pre_close=Decimal("9"),
                        volume=90,
                        amount=Decimal("900"),
                        source="fixture",
                        collected_at=datetime(2026, 8, 14, tzinfo=UTC),
                    )
                ]
            )
            daily_result = await service.sync_daily_bars(
                "601998", end=date(2026, 8, 14), force=True
            )
            assert master_result.written_count == 1
            assert daily_result.written_count == 1
            assert provider.window == (date(2026, 8, 14), date(2026, 8, 14))
            assert (await stocks.get(symbol)).latest_price == Decimal("11.000000")  # type: ignore[union-attr]
    finally:
        async with sessions() as session:
            await session.execute(
                delete(DataSyncRunRecord).where(
                    (DataSyncRunRecord.symbol == symbol)
                    | (
                        (DataSyncRunRecord.dataset == "stock_master")
                        & (DataSyncRunRecord.provider == "fixture")
                    )
                )
            )
            await session.execute(
                delete(StockDailyBarRecord).where(StockDailyBarRecord.symbol == symbol)
            )
            await session.execute(delete(StockRecord).where(StockRecord.symbol == symbol))
            await session.commit()
        await engine.dispose()
