from sqlalchemy.ext.asyncio import AsyncSession

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
