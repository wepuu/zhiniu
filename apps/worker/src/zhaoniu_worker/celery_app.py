import asyncio
import os
from datetime import date, datetime

from celery import Celery  # type: ignore[import-untyped]
from zhaoniu_api.corporate_events.errors import DisclosureProviderTransientError

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


async def _build_research_snapshot(symbol: str, as_of: str | None) -> dict[str, object]:
    from zhaoniu_api.composition import build_research_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_research_service(session).build_snapshot(
            symbol,
            as_of=datetime.fromisoformat(as_of) if as_of else None,
        )
        return {
            "status": result.status,
            "snapshot_id": str(result.snapshot_id),
            "data_version": result.data_version,
            "observation_count": result.observation_count,
            "idempotency_key": result.idempotency_key,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="research.build_snapshot",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def build_research_snapshot(symbol: str, as_of: str | None = None) -> dict[str, object]:
    """Build an immutable deterministic research snapshot."""
    return asyncio.run(_build_research_snapshot(symbol, as_of))


async def _generate_ai_stock_health(symbol: str, retry_failed: bool) -> dict[str, object]:
    from zhaoniu_api.composition import build_ai_research_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_ai_research_service(session).generate_stock_health(
            symbol, retry_failed=retry_failed
        )
        return {
            "status": result.status,
            "run_id": str(result.run_id) if result.run_id else None,
            "output_id": str(result.output_id) if result.output_id else None,
            "idempotency_key": result.idempotency_key,
            "provider": result.provider,
            "model": result.model,
        }


@celery_app.task(name="ai_research.generate_stock_health")  # type: ignore[untyped-decorator]
def generate_ai_stock_health(symbol: str, retry_failed: bool = False) -> dict[str, object]:
    """Generate shared evidence-bound AI research with an application-level attempt budget."""
    return asyncio.run(_generate_ai_stock_health(symbol, retry_failed))


async def _event_task(command: str, symbol: str, **kwargs: object) -> dict[str, object]:
    from zhaoniu_api.composition import build_corporate_event_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        service = build_corporate_event_service(session)
        if command == "sync":
            result = await service.sync_disclosures(
                symbol,
                start=date.fromisoformat(str(kwargs["start"])) if kwargs.get("start") else None,
                end=date.fromisoformat(str(kwargs["end"])) if kwargs.get("end") else None,
            )
        elif command == "events":
            result = await service.build_corporate_events(symbol)
        elif command == "radar":
            result = await service.build_event_radar(
                symbol,
                as_of=datetime.fromisoformat(str(kwargs["as_of"])) if kwargs.get("as_of") else None,
            )
        else:
            result = await service.build_event_research(symbol)
        return {
            "status": result.status,
            "symbol": result.symbol,
            "received_count": result.received_count,
            "written_count": result.written_count,
            "idempotency_key": result.idempotency_key,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="disclosure.sync",
    autoretry_for=(DisclosureProviderTransientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_disclosures(
    symbol: str, start: str | None = None, end: str | None = None
) -> dict[str, object]:
    return asyncio.run(_event_task("sync", symbol, start=start, end=end))


@celery_app.task(name="corporate_events.build")  # type: ignore[untyped-decorator]
def build_corporate_events(symbol: str) -> dict[str, object]:
    return asyncio.run(_event_task("events", symbol))


@celery_app.task(name="event_radar.build")  # type: ignore[untyped-decorator]
def build_event_radar(symbol: str, as_of: str | None = None) -> dict[str, object]:
    return asyncio.run(_event_task("radar", symbol, as_of=as_of))


@celery_app.task(name="event_research.build")  # type: ignore[untyped-decorator]
def build_event_research(symbol: str) -> dict[str, object]:
    return asyncio.run(_event_task("research", symbol))
