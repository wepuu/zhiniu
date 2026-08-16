import asyncio
import os
from datetime import date

from celery import Celery  # type: ignore[import-untyped]

celery_app = Celery(
    "zhaoniu",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
)


@celery_app.task(name="foundation.health_check")  # type: ignore[untyped-decorator]
def health_check() -> dict[str, str]:
    return {"status": "ok"}


async def _sync_daily_bars(symbol: str, start: str | None, end: str | None) -> dict[str, object]:
    from zhaoniu_api.composition import build_market_data_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_market_data_service(session).sync_daily_bars(
            symbol,
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
        )
        return {
            "status": result.status,
            "received_count": result.received_count,
            "written_count": result.written_count,
            "idempotency_key": result.idempotency_key,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="market_data.sync_daily_bars",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_daily_bars(
    symbol: str, start: str | None = None, end: str | None = None
) -> dict[str, object]:
    """Celery entry point; CLI and worker share the same application service."""
    return asyncio.run(_sync_daily_bars(symbol, start, end))


async def _sync_financial_statements(symbol: str, start_year: int) -> dict[str, object]:
    from zhaoniu_api.composition import build_fundamental_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_fundamental_service(session).sync_financial_statements(
            symbol, start_year=start_year
        )
        return {
            "status": result.status,
            "received_count": result.received_count,
            "written_count": result.written_count,
            "idempotency_key": result.idempotency_key,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="fundamentals.sync_financial_statements",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_financial_statements(symbol: str, start_year: int) -> dict[str, object]:
    """Idempotent financial-statement sync using the shared application service."""
    return asyncio.run(_sync_financial_statements(symbol, start_year))


async def _sync_valuations(symbol: str, start: str | None, end: str | None) -> dict[str, object]:
    from zhaoniu_api.composition import build_fundamental_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_fundamental_service(session).sync_valuations(
            symbol,
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
        )
        return {
            "status": result.status,
            "received_count": result.received_count,
            "written_count": result.written_count,
            "idempotency_key": result.idempotency_key,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="fundamentals.sync_valuations",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_valuations(
    symbol: str, start: str | None = None, end: str | None = None
) -> dict[str, object]:
    """Idempotent historical-valuation sync using the shared application service."""
    return asyncio.run(_sync_valuations(symbol, start, end))
