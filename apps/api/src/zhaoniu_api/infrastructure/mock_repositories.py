from decimal import Decimal
from uuid import UUID

from zhaoniu_api.domain.models import Stock, Watchlist


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
        return self._stocks.get(symbol.upper())


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
