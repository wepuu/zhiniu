from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.composition import build_fundamental_service, build_research_service
from zhaoniu_api.database import get_session
from zhaoniu_api.fundamentals.service import FundamentalResearchService
from zhaoniu_api.infrastructure.mock_repositories import InMemoryWatchlistRepository
from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyDailyBarRepository,
    SQLAlchemyStockRepository,
)
from zhaoniu_api.ports.repositories import DailyBarRepository, StockRepository, WatchlistRepository
from zhaoniu_api.research.service import DeterministicResearchService

DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
watchlist_repository = InMemoryWatchlistRepository()


def get_current_user_id() -> UUID:
    """Auth seam: replace with secure HttpOnly cookie session validation in Phase 1."""
    return DEMO_USER_ID


def get_stock_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> StockRepository:
    return SQLAlchemyStockRepository(session)


def get_daily_bar_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DailyBarRepository:
    return SQLAlchemyDailyBarRepository(session)


def get_watchlist_repository() -> WatchlistRepository:
    return watchlist_repository


def get_fundamental_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FundamentalResearchService:
    return build_fundamental_service(session)


def get_research_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeterministicResearchService:
    return build_research_service(session)


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
StockRepo = Annotated[StockRepository, Depends(get_stock_repository)]
DailyBarRepo = Annotated[DailyBarRepository, Depends(get_daily_bar_repository)]
WatchlistRepo = Annotated[WatchlistRepository, Depends(get_watchlist_repository)]
FundamentalService = Annotated[FundamentalResearchService, Depends(get_fundamental_service)]
ResearchService = Annotated[DeterministicResearchService, Depends(get_research_service)]
