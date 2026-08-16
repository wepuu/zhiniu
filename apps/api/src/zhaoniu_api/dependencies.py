from typing import Annotated
from uuid import UUID

from fastapi import Depends

from zhaoniu_api.infrastructure.mock_repositories import (
    InMemoryStockRepository,
    InMemoryWatchlistRepository,
)
from zhaoniu_api.ports.repositories import StockRepository, WatchlistRepository

DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
stock_repository = InMemoryStockRepository()
watchlist_repository = InMemoryWatchlistRepository()


def get_current_user_id() -> UUID:
    """Auth seam: replace with secure HttpOnly cookie session validation in Phase 1."""
    return DEMO_USER_ID


def get_stock_repository() -> StockRepository:
    return stock_repository


def get_watchlist_repository() -> WatchlistRepository:
    return watchlist_repository


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
StockRepo = Annotated[StockRepository, Depends(get_stock_repository)]
WatchlistRepo = Annotated[WatchlistRepository, Depends(get_watchlist_repository)]
