from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_research.litellm_gateway import LiteLLMGateway
from zhaoniu_api.ai_research.service import AIResearchOptions, AIResearchService
from zhaoniu_api.ai_research.sql_repository import SQLAlchemyAIResearchRepository
from zhaoniu_api.config import get_settings
from zhaoniu_api.corporate_events.normalizer import AKShareDisclosureNormalizer
from zhaoniu_api.corporate_events.provider import AKShareDisclosureProvider
from zhaoniu_api.corporate_events.service import CorporateEventService
from zhaoniu_api.corporate_events.sql_repository import SQLAlchemyCorporateEventRepository
from zhaoniu_api.fundamentals.akshare_provider import AKShareFinancialProvider
from zhaoniu_api.fundamentals.normalizer import AKShareFinancialNormalizer
from zhaoniu_api.fundamentals.service import FundamentalResearchService
from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyDailyBarRepository,
    SQLAlchemyFundamentalRepository,
    SQLAlchemyStockRepository,
    SQLAlchemySyncRunRepository,
)
from zhaoniu_api.market_data.akshare_provider import AKShareProvider
from zhaoniu_api.market_data.normalizer import AKShareNormalizer
from zhaoniu_api.market_data.service import MarketDataSyncService
from zhaoniu_api.peer_research.service import PeerResearchService
from zhaoniu_api.peer_research.sql_repository import SQLAlchemyPeerResearchRepository
from zhaoniu_api.research.service import DeterministicResearchService
from zhaoniu_api.research.sql_repository import SQLAlchemyResearchRepository
from zhaoniu_api.research_feed.service import ResearchFeedService
from zhaoniu_api.screening.service import ScreeningService


def build_market_data_service(session: AsyncSession) -> MarketDataSyncService:
    return MarketDataSyncService(
        provider=AKShareProvider(),
        normalizer=AKShareNormalizer(),
        stocks=SQLAlchemyStockRepository(session),
        bars=SQLAlchemyDailyBarRepository(session),
        runs=SQLAlchemySyncRunRepository(session),
    )


def build_fundamental_service(session: AsyncSession) -> FundamentalResearchService:
    return FundamentalResearchService(
        provider=AKShareFinancialProvider(),
        normalizer=AKShareFinancialNormalizer(),
        stocks=SQLAlchemyStockRepository(session),
        fundamentals=SQLAlchemyFundamentalRepository(session),
        runs=SQLAlchemySyncRunRepository(session),
    )


def build_research_service(session: AsyncSession) -> DeterministicResearchService:
    return DeterministicResearchService(
        stocks=SQLAlchemyStockRepository(session),
        fundamentals=SQLAlchemyFundamentalRepository(session),
        research=SQLAlchemyResearchRepository(session),
    )


def build_peer_research_service(session: AsyncSession) -> PeerResearchService:
    return PeerResearchService(
        stocks=SQLAlchemyStockRepository(session),
        peer_repository=SQLAlchemyPeerResearchRepository(session),
    )


def build_ai_research_service(session: AsyncSession) -> AIResearchService:
    settings = get_settings()
    return AIResearchService(
        stocks=SQLAlchemyStockRepository(session),
        research=SQLAlchemyResearchRepository(session),
        ai_research=SQLAlchemyAIResearchRepository(session),
        gateway=LiteLLMGateway(),
        options=AIResearchOptions(
            enabled=settings.llm_enabled,
            model_chain=settings.llm_models,
            max_attempts=settings.llm_max_attempts,
            per_model_timeout_seconds=settings.llm_per_model_timeout_seconds,
            run_deadline_seconds=settings.llm_run_deadline_seconds,
        ),
    )


def build_corporate_event_service(session: AsyncSession) -> CorporateEventService:
    return CorporateEventService(
        provider=AKShareDisclosureProvider(),
        normalizer=AKShareDisclosureNormalizer(),
        stocks=SQLAlchemyStockRepository(session),
        events=SQLAlchemyCorporateEventRepository(session),
    )


def build_research_feed_service(session: AsyncSession) -> ResearchFeedService:
    return ResearchFeedService(session, get_settings())


def build_screening_service(session: AsyncSession) -> ScreeningService:
    return ScreeningService(session)
