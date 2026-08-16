from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.db import DataSyncRunRecord, StockDailyBarRecord, StockRecord
from zhaoniu_api.domain.models import AdjustType, DailyBar, Stock, resolve_symbol


class SQLAlchemyStockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _domain(record: StockRecord, bar: StockDailyBarRecord | None) -> Stock:
        return Stock(
            symbol=record.ticker,
            canonical_symbol=record.symbol,
            name=record.name,
            exchange=record.exchange,
            industry=record.industry_code,
            board=record.board,
            asset_type=record.asset_type,
            list_date=record.list_date,
            status=record.status,
            source=record.source,
            collected_at=record.collected_at,
            latest_price=bar.close if bar else None,
            change_percent=bar_to_pct_change(bar),
            latest_trade_date=bar.trade_date if bar else None,
        )

    async def _latest_bar(self, canonical_symbol: str) -> StockDailyBarRecord | None:
        return cast(
            StockDailyBarRecord | None,
            await self._session.scalar(
                select(StockDailyBarRecord)
                .where(
                    StockDailyBarRecord.symbol == canonical_symbol,
                    StockDailyBarRecord.adjust_type == AdjustType.NONE,
                )
                .order_by(StockDailyBarRecord.trade_date.desc())
                .limit(1)
            ),
        )

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        needle = f"%{query.strip()}%"
        records = (
            await self._session.scalars(
                select(StockRecord)
                .where(or_(StockRecord.ticker.ilike(needle), StockRecord.name.ilike(needle)))
                .order_by(StockRecord.ticker)
                .limit(limit)
            )
        ).all()
        return [self._domain(record, await self._latest_bar(record.symbol)) for record in records]

    async def get(self, symbol: str) -> Stock | None:
        try:
            canonical = resolve_symbol(symbol).canonical
        except ValueError:
            return None
        record = await self._session.get(StockRecord, canonical)
        if record is None:
            return None
        return self._domain(record, await self._latest_bar(canonical))

    async def upsert_many(self, stocks: list[Stock]) -> int:
        if not stocks:
            return 0
        values = [
            {
                "symbol": stock.canonical_symbol,
                "ticker": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "industry_code": stock.industry,
                "asset_type": stock.asset_type,
                "board": stock.board,
                "list_date": stock.list_date,
                "status": stock.status,
                "source": stock.source or "unknown",
                "collected_at": stock.collected_at or datetime.now(UTC),
            }
            for stock in stocks
        ]
        try:
            for offset in range(0, len(values), 1000):
                statement = insert(StockRecord).values(values[offset : offset + 1000])
                await self._session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[StockRecord.symbol],
                        set_={
                            "ticker": statement.excluded.ticker,
                            "name": statement.excluded.name,
                            "exchange": statement.excluded.exchange,
                            "industry_code": statement.excluded.industry_code,
                            "asset_type": statement.excluded.asset_type,
                            "board": statement.excluded.board,
                            "list_date": statement.excluded.list_date,
                            "status": statement.excluded.status,
                            "source": statement.excluded.source,
                            "collected_at": statement.excluded.collected_at,
                            "updated_at": func.now(),
                        },
                    )
                )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(stocks)


def bar_to_pct_change(bar: StockDailyBarRecord | None) -> Decimal | None:
    if bar is None or bar.pre_close is None or bar.pre_close == 0:
        return None
    return ((bar.close - bar.pre_close) / bar.pre_close * Decimal("100")).quantize(
        Decimal("0.0001")
    )


class SQLAlchemyDailyBarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _domain(row: StockDailyBarRecord) -> DailyBar:
        return DailyBar(
            canonical_symbol=row.symbol,
            trade_date=row.trade_date,
            adjust_type=AdjustType(row.adjust_type),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            pre_close=row.pre_close,
            volume=row.volume,
            amount=row.amount,
            source=row.source,
            collected_at=row.collected_at,
        )

    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]:
        filters = [
            StockDailyBarRecord.symbol == canonical_symbol,
            StockDailyBarRecord.adjust_type == AdjustType.NONE,
        ]
        if start is not None:
            filters.append(StockDailyBarRecord.trade_date >= start)
        if end is not None:
            filters.append(StockDailyBarRecord.trade_date <= end)
        rows = (
            await self._session.scalars(
                select(StockDailyBarRecord)
                .where(*filters)
                .order_by(StockDailyBarRecord.trade_date.desc())
                .limit(limit)
            )
        ).all()
        return [self._domain(row) for row in reversed(rows)]

    async def latest_date(self, canonical_symbol: str) -> date | None:
        latest = await self._session.scalar(
            select(func.max(StockDailyBarRecord.trade_date)).where(
                StockDailyBarRecord.symbol == canonical_symbol,
                StockDailyBarRecord.adjust_type == AdjustType.NONE,
            )
        )
        return latest if isinstance(latest, date) else None

    async def upsert_many(self, bars: list[DailyBar]) -> int:
        if not bars:
            return 0
        values = [
            {
                "symbol": bar.canonical_symbol,
                "trade_date": bar.trade_date,
                "adjust_type": bar.adjust_type,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "pre_close": bar.pre_close,
                "volume": bar.volume,
                "amount": bar.amount,
                "source": bar.source,
                "collected_at": bar.collected_at,
            }
            for bar in bars
        ]
        try:
            statement = insert(StockDailyBarRecord).values(values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_stock_daily_bar_identity",
                    set_={
                        "open": statement.excluded.open,
                        "high": statement.excluded.high,
                        "low": statement.excluded.low,
                        "close": statement.excluded.close,
                        "pre_close": statement.excluded.pre_close,
                        "volume": statement.excluded.volume,
                        "amount": statement.excluded.amount,
                        "source": statement.excluded.source,
                        "collected_at": statement.excluded.collected_at,
                        "updated_at": func.now(),
                    },
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(bars)


class SQLAlchemySyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def was_successful(self, idempotency_key: str) -> bool:
        return bool(
            await self._session.scalar(
                select(func.count(DataSyncRunRecord.id)).where(
                    DataSyncRunRecord.idempotency_key == idempotency_key,
                    DataSyncRunRecord.status == "succeeded",
                )
            )
        )

    async def start(
        self,
        *,
        dataset: str,
        provider: str,
        canonical_symbol: str | None,
        requested_start: date | None,
        requested_end: date | None,
        idempotency_key: str,
    ) -> str:
        record = DataSyncRunRecord(
            dataset=dataset,
            provider=provider,
            symbol=canonical_symbol,
            requested_start=requested_start,
            requested_end=requested_end,
            idempotency_key=idempotency_key,
            status="running",
        )
        self._session.add(record)
        await self._session.commit()
        return str(record.id)

    async def finish(
        self,
        run_id: str,
        *,
        status: str,
        received_count: int,
        written_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None:
        record = await self._session.get(DataSyncRunRecord, UUID(run_id))
        if record is None:
            raise RuntimeError("sync run not found")
        record.status = status
        record.received_count = received_count
        record.written_count = written_count
        record.error_summary = error_summary[:500] if error_summary else None
        record.finished_at = finished_at
        started = record.started_at
        if started is not None:
            record.duration_ms = int((finished_at - started).total_seconds() * 1000)
        await self._session.commit()
