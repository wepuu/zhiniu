import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from zhaoniu_api.config import get_settings

settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if os.getenv("ZHAONIU_DISABLE_DB_POOL") == "1":
    # Celery's synchronous tasks use a fresh asyncio.run() event loop per invocation.
    # asyncpg pooled connections are loop-bound and cannot safely cross those loops.
    engine_options["poolclass"] = NullPool
engine = create_async_engine(settings.database_url, **engine_options)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
