from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from zhaoniu_api.domain.models import DailyBar, Stock, Watchlist, resolve_symbol
from zhaoniu_api.fundamentals.models import (
    FinancialReport,
    FundamentalSnapshot,
    ValuationObservation,
)


class InMemoryStockRepository:
    def __init__(self) -> None:
        self._stocks = {
            "600519": Stock(
                "600519", "贵州茅台", "SSE", "白酒", Decimal("1438.20"), Decimal("0.62")
            ),
            "000001": Stock(
                "000001", "平安银行", "SZSE", "银行", Decimal("11.28"), Decimal("-0.18")
            ),
            "300750": Stock(
                "300750", "宁德时代", "SZSE", "电池", Decimal("286.35"), Decimal("1.24")
            ),
        }

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        needle = query.strip().lower()
        return [
            stock
            for stock in self._stocks.values()
            if needle in stock.symbol.lower() or needle in stock.name.lower()
        ][:limit]

    async def get(self, symbol: str) -> Stock | None:
        try:
            return self._stocks.get(resolve_symbol(symbol).ticker)
        except ValueError:
            return None

    async def upsert_many(self, stocks: list[Stock]) -> int:
        self._stocks.update({stock.symbol: stock for stock in stocks})
        return len(stocks)


class InMemoryDailyBarRepository:
    def __init__(self, bars: list[DailyBar] | None = None) -> None:
        self._bars = bars or []

    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]:
        matches = [
            bar
            for bar in self._bars
            if bar.canonical_symbol == canonical_symbol
            and (start is None or bar.trade_date >= start)
            and (end is None or bar.trade_date <= end)
        ]
        return sorted(matches, key=lambda item: item.trade_date)[-limit:]

    async def latest_date(self, canonical_symbol: str) -> date | None:
        dates = [bar.trade_date for bar in self._bars if bar.canonical_symbol == canonical_symbol]
        return max(dates) if dates else None

    async def upsert_many(self, bars: list[DailyBar]) -> int:
        identities = {(bar.canonical_symbol, bar.trade_date, bar.adjust_type) for bar in bars}
        self._bars = [
            bar
            for bar in self._bars
            if (bar.canonical_symbol, bar.trade_date, bar.adjust_type) not in identities
        ] + bars
        return len(bars)


class InMemoryFundamentalRepository:
    def __init__(
        self,
        reports: list[FinancialReport] | None = None,
        valuations: list[ValuationObservation] | None = None,
    ) -> None:
        self._reports = reports or []
        self._valuations = valuations or []
        self._snapshots: list[FundamentalSnapshot] = []

    async def upsert_reports(self, reports: list[FinancialReport]) -> int:
        identities = {
            (
                item.canonical_symbol,
                item.provider,
                item.period_end,
                item.statement_scope,
                item.normalizer_version,
                item.payload_checksum,
            )
            for item in self._reports
        }
        inserted = 0
        for report in reports:
            identity = (
                report.canonical_symbol,
                report.provider,
                report.period_end,
                report.statement_scope,
                report.normalizer_version,
                report.payload_checksum,
            )
            if identity not in identities:
                self._reports.append(report)
                identities.add(identity)
                inserted += 1
        return inserted

    async def list_reports(
        self,
        canonical_symbol: str,
        *,
        as_of: datetime | None,
        limit: int,
    ) -> list[FinancialReport]:
        candidates = [
            item
            for item in self._reports
            if item.canonical_symbol == canonical_symbol
            and (as_of is None or item.known_at <= as_of)
        ]
        selected: list[FinancialReport] = []
        seen: set[tuple[date, str]] = set()
        for item in sorted(
            candidates, key=lambda report: (report.period_end, report.known_at), reverse=True
        ):
            identity = (item.period_end, item.statement_scope)
            if identity not in seen:
                selected.append(item)
                seen.add(identity)
            if len(selected) >= limit:
                break
        return selected

    async def save_snapshot(self, snapshot: FundamentalSnapshot) -> int:
        self._snapshots = [
            item
            for item in self._snapshots
            if not (
                item.canonical_symbol == snapshot.canonical_symbol
                and item.data_version == snapshot.data_version
                and item.metric_version == snapshot.metric_version
            )
        ]
        self._snapshots.append(snapshot)
        return len(snapshot.metrics)

    async def latest_snapshot(
        self, canonical_symbol: str, *, as_of: datetime | None
    ) -> FundamentalSnapshot | None:
        candidates = [
            item
            for item in self._snapshots
            if item.canonical_symbol == canonical_symbol and (as_of is None or item.as_of <= as_of)
        ]
        return max(candidates, key=lambda item: item.as_of, default=None)

    async def upsert_valuations(self, observations: list[ValuationObservation]) -> int:
        identities = {
            (item.canonical_symbol, item.trade_date, item.metric_code, item.provider)
            for item in observations
        }
        self._valuations = [
            item
            for item in self._valuations
            if (item.canonical_symbol, item.trade_date, item.metric_code, item.provider)
            not in identities
        ] + observations
        return len(observations)

    async def list_valuations(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        metric_codes: tuple[str, ...] | None,
        limit: int,
    ) -> list[ValuationObservation]:
        matches = [
            item
            for item in self._valuations
            if item.canonical_symbol == canonical_symbol
            and (start is None or item.trade_date >= start)
            and (end is None or item.trade_date <= end)
            and (not metric_codes or item.metric_code in metric_codes)
        ]
        return sorted(matches, key=lambda item: item.trade_date)[-limit:]


class InMemoryWatchlistRepository:
    def __init__(self) -> None:
        self._watchlists: dict[UUID, Watchlist] = {}

    async def list_for_user(self, user_id: UUID) -> list[Watchlist]:
        return [item for item in self._watchlists.values() if item.user_id == user_id]

    async def create(self, watchlist: Watchlist) -> Watchlist:
        self._watchlists[watchlist.id] = watchlist
        return watchlist

    async def get_owned(self, watchlist_id: UUID, user_id: UUID) -> Watchlist | None:
        item = self._watchlists.get(watchlist_id)
        return item if item and item.user_id == user_id else None

    async def save(self, watchlist: Watchlist) -> Watchlist:
        self._watchlists[watchlist.id] = watchlist
        return watchlist
