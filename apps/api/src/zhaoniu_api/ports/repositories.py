from typing import Protocol
from uuid import UUID

from zhaoniu_api.domain.models import Stock, Watchlist


class StockRepository(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[Stock]: ...

    async def get(self, symbol: str) -> Stock | None: ...


class WatchlistRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Watchlist]: ...

    async def create(self, watchlist: Watchlist) -> Watchlist: ...

    async def get_owned(self, watchlist_id: UUID, user_id: UUID) -> Watchlist | None: ...

    async def save(self, watchlist: Watchlist) -> Watchlist: ...
