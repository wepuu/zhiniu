from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_research.service import AIResearchService
from zhaoniu_api.auth.service import AuthService
from zhaoniu_api.composition import (
    build_ai_research_service,
    build_corporate_event_service,
    build_fundamental_service,
    build_peer_research_service,
    build_research_service,
    build_screening_service,
)
from zhaoniu_api.config import Settings, get_settings
from zhaoniu_api.corporate_events.service import CorporateEventService
from zhaoniu_api.database import get_session
from zhaoniu_api.domain.models import UserAccount
from zhaoniu_api.fundamentals.service import FundamentalResearchService
from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyDailyBarRepository,
    SQLAlchemyStockRepository,
    SQLAlchemyWatchlistRepository,
)
from zhaoniu_api.peer_research.service import PeerResearchService
from zhaoniu_api.ports.repositories import DailyBarRepository, StockRepository, WatchlistRepository
from zhaoniu_api.research.service import DeterministicResearchService
from zhaoniu_api.research_feed.service import ResearchFeedService
from zhaoniu_api.screening.dispatch import ScreeningDispatcher
from zhaoniu_api.screening.service import ScreeningService


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, settings)


async def get_current_user_id(
    auth: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[str | None, Cookie(alias="zhaoniu_session")] = None,
) -> UUID:
    account = await get_current_user(auth, token)
    return account.id


async def get_current_user(
    auth: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[str | None, Cookie(alias="zhaoniu_session")] = None,
) -> UserAccount:
    account = await auth.authenticate(token)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return account


def get_stock_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> StockRepository:
    return SQLAlchemyStockRepository(session)


def get_daily_bar_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DailyBarRepository:
    return SQLAlchemyDailyBarRepository(session)


def get_watchlist_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WatchlistRepository:
    return SQLAlchemyWatchlistRepository(session)


def get_fundamental_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FundamentalResearchService:
    return build_fundamental_service(session)


def get_research_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeterministicResearchService:
    return build_research_service(session)


def get_ai_research_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AIResearchService:
    return build_ai_research_service(session)


def get_peer_research_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PeerResearchService:
    return build_peer_research_service(session)


def get_corporate_event_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CorporateEventService:
    return build_corporate_event_service(session)


def get_research_feed_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchFeedService:
    return ResearchFeedService(session, settings)


def get_screening_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScreeningService:
    return build_screening_service(session)


def get_screening_dispatcher(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScreeningDispatcher:
    return ScreeningDispatcher(settings)


async def require_csrf(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.origin_allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="origin_not_allowed")
    session_token = request.cookies.get(settings.auth_cookie_name)
    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_validation_failed")
    if not await auth.validate_csrf(session_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_validation_failed")


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
CurrentUser = Annotated[UserAccount, Depends(get_current_user)]
AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
StockRepo = Annotated[StockRepository, Depends(get_stock_repository)]
DailyBarRepo = Annotated[DailyBarRepository, Depends(get_daily_bar_repository)]
WatchlistRepo = Annotated[WatchlistRepository, Depends(get_watchlist_repository)]
FundamentalService = Annotated[FundamentalResearchService, Depends(get_fundamental_service)]
ResearchService = Annotated[DeterministicResearchService, Depends(get_research_service)]
AIResearchServiceDependency = Annotated[AIResearchService, Depends(get_ai_research_service)]
PeerResearchServiceDependency = Annotated[PeerResearchService, Depends(get_peer_research_service)]
CorporateEventServiceDependency = Annotated[
    CorporateEventService, Depends(get_corporate_event_service)
]
ResearchFeedServiceDependency = Annotated[ResearchFeedService, Depends(get_research_feed_service)]
ScreeningServiceDependency = Annotated[ScreeningService, Depends(get_screening_service)]
ScreeningDispatcherDependency = Annotated[
    ScreeningDispatcher, Depends(get_screening_dispatcher)
]
CSRFSafe = Annotated[None, Depends(require_csrf)]
