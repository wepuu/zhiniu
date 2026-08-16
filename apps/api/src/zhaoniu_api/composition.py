from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.infrastructure.sql_repositories import (
    SQLAlchemyDailyBarRepository,
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
