from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from zhaoniu_api.domain.models import DailyBar, Stock, Watchlist


class StockRepository(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[Stock]: ...

    async def get(self, symbol: str) -> Stock | None: ...

    async def upsert_many(self, stocks: list[Stock]) -> int: ...


class DailyBarRepository(Protocol):
    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]: ...

    async def latest_date(self, canonical_symbol: str) -> date | None: ...

    async def upsert_many(self, bars: list[DailyBar]) -> int: ...


class SyncRunRepository(Protocol):
    async def was_successful(self, idempotency_key: str) -> bool: ...

    async def start(
        self,
        *,
        dataset: str,
        provider: str,
        canonical_symbol: str | None,
        requested_start: date | None,
        requested_end: date | None,
        idempotency_key: str,
    ) -> str: ...

    async def finish(
        self,
        run_id: str,
        *,
        status: str,
        received_count: int,
        written_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None: ...


class WatchlistRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Watchlist]: ...

    async def create(self, watchlist: Watchlist) -> Watchlist: ...

    async def get_owned(self, watchlist_id: UUID, user_id: UUID) -> Watchlist | None: ...

    async def save(self, watchlist: Watchlist) -> Watchlist: ...
