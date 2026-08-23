import asyncio
import os
from datetime import date, datetime
from uuid import UUID

# Every Celery task below owns a short-lived asyncio.run() event loop. Keep database
# connections out of a cross-task pool because asyncpg connections are loop-bound.
os.environ["ZHAONIU_DISABLE_DB_POOL"] = "1"

from celery import Celery  # type: ignore[import-untyped]
from redis import Redis
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
    beat_schedule={
        "automation-tick": {
            "task": "automation.tick",
            "schedule": float(os.getenv("AUTOMATION_TICK_SECONDS", "60")),
        }
    },
)


@celery_app.task(name="foundation.health_check")  # type: ignore[untyped-decorator]
def health_check() -> dict[str, str]:
    return {"status": "ok"}


async def _deliver_transactional_email(
    delivery_id: str, message_data: dict[str, object]
) -> dict[str, object]:
    from sqlalchemy import select
    from zhaoniu_api.auth.email import (
        TransactionalEmail,
        TransactionalEmailError,
        build_managed_email_gateway,
    )
    from zhaoniu_api.config import get_settings
    from zhaoniu_api.database import session_factory
    from zhaoniu_api.db import TransactionalEmailDeliveryRecord

    async with session_factory() as session:
        delivery = await session.scalar(
            select(TransactionalEmailDeliveryRecord)
            .where(TransactionalEmailDeliveryRecord.id == UUID(delivery_id))
            .with_for_update()
        )
        if delivery is None:
            return {"status": "missing", "delivery_id": delivery_id}
        if delivery.status in {"submitted", "delivered"}:
            return {"status": "skipped", "delivery_id": delivery_id}

        gateway = await build_managed_email_gateway(session, get_settings())
        try:
            result = await gateway.send(TransactionalEmail(**message_data))  # type: ignore[arg-type]
        except TransactionalEmailError as error:
            delivery.status = "failed"
            delivery.error_code = str(error)[:80]
            await session.commit()
            raise

        now = datetime.now().astimezone()
        delivery.provider = result.provider
        delivery.provider_message_id = result.message_id
        delivery.status = "submitted"
        delivery.error_code = None
        delivery.sent_at = now
        delivery.submitted_at = now
        delivery.last_event_at = now
        await session.commit()
        return {
            "status": "submitted",
            "delivery_id": delivery_id,
            "provider": result.provider,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="transactional_email.deliver",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def deliver_transactional_email(
    delivery_id: str, message_data: dict[str, object]
) -> dict[str, object]:
    """Submit one idempotent transactional email outside the request lifecycle."""
    return asyncio.run(_deliver_transactional_email(delivery_id, message_data))


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


async def _generate_ai_explanation(request_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_ai_explanation_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_ai_explanation_service(session).execute(UUID(request_id))
        return {
            "status": result.status,
            "request_id": str(result.id),
            "output_id": str(result.output.output_id) if result.output else None,
        }


@celery_app.task(name="ai_research.generate_explanation")  # type: ignore[untyped-decorator]
def generate_ai_explanation(request_id: str) -> dict[str, object]:
    """Generate one shared DeepSeek explanation for a user-owned request wrapper."""
    return asyncio.run(_generate_ai_explanation(request_id))


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


async def _project_research_signals(symbol: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_research_feed_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_research_feed_service(session).project_symbol(symbol)
        return result.model_dump(mode="json")


@celery_app.task(name="research_signals.project")  # type: ignore[untyped-decorator]
def project_research_signals(symbol: str) -> dict[str, object]:
    return asyncio.run(_project_research_signals(symbol))


async def _dispatch_research_alert(signal_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_research_feed_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_research_feed_service(session).dispatch(UUID(signal_id))
        return result.model_dump(mode="json")


@celery_app.task(name="research_alerts.dispatch")  # type: ignore[untyped-decorator]
def dispatch_research_alert(signal_id: str) -> dict[str, object]:
    return asyncio.run(_dispatch_research_alert(signal_id))


async def _build_screening_snapshot(as_of: str | None) -> dict[str, object]:
    from zhaoniu_api.composition import build_screening_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_screening_service(session).build_snapshot(
            datetime.fromisoformat(as_of) if as_of else None
        )
        return result.model_dump(mode="json")


@celery_app.task(name="screening.build_snapshot")  # type: ignore[untyped-decorator]
def build_screening_snapshot(as_of: str | None = None) -> dict[str, object]:
    return asyncio.run(_build_screening_snapshot(as_of))


async def _execute_screen(execution_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_screening_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_screening_service(session).execute(UUID(execution_id))
        return result.model_dump(mode="json")


@celery_app.task(name="screening.execute")  # type: ignore[untyped-decorator]
def execute_screen(execution_id: str) -> dict[str, object]:
    return asyncio.run(_execute_screen(execution_id))


async def _build_comparison(request_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_comparison_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_comparison_service(session).execute(UUID(request_id))
        return result.model_dump(mode="json")


@celery_app.task(name="comparisons.build")  # type: ignore[untyped-decorator]
def build_comparison(request_id: str) -> dict[str, object]:
    return asyncio.run(_build_comparison(request_id))


async def _run_coverage_backfill(run_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_coverage_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_coverage_service(session).run_backfill(UUID(run_id))
        return result.model_dump(mode="json")


@celery_app.task(name="coverage.run_backfill")  # type: ignore[untyped-decorator]
def run_coverage_backfill(run_id: str) -> dict[str, object]:
    """Run one explicitly planned, bounded coverage backfill batch."""
    return asyncio.run(_run_coverage_backfill(run_id))


async def _parse_natural_language_screen(run_id: str, text: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_natural_language_screening_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_natural_language_screening_service(session).parse(UUID(run_id), text)
        return {
            "id": str(result.id),
            "status": result.status,
            "semantic_status": result.semantic_status,
            "error_code": result.error_code,
        }


@celery_app.task(name="screening.parse_natural_language")  # type: ignore[untyped-decorator]
def parse_natural_language_screen(run_id: str) -> dict[str, object]:
    key = f"screen-parse-input:{run_id}"
    with Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
    ) as client:
        text = client.getdel(key)
    return asyncio.run(_parse_natural_language_screen(run_id, text or ""))


async def _automation_tick() -> dict[str, object]:
    from zhaoniu_api.composition import build_automation_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_automation_service(session).tick()
        return result.model_dump(mode="json")


@celery_app.task(name="automation.tick")  # type: ignore[untyped-decorator]
def automation_tick() -> dict[str, object]:
    """Single Beat entry point; the database decides whether a policy is due."""
    result = asyncio.run(_automation_tick())
    run_ids = result.get("run_ids")
    if isinstance(run_ids, list):
        for run_id in run_ids:
            celery_app.send_task("automation.execute_run", args=[str(run_id)])
    return result


async def _execute_automation_run(run_id: str) -> dict[str, object]:
    from zhaoniu_api.composition import build_automation_service
    from zhaoniu_api.database import session_factory

    async with session_factory() as session:
        result = await build_automation_service(session).execute_run(UUID(run_id))
        return result.model_dump(mode="json")


@celery_app.task(name="automation.execute_run")  # type: ignore[untyped-decorator]
def execute_automation_run(run_id: str) -> dict[str, object]:
    """Execute an allow-listed pipeline from database-owned run state."""
    return asyncio.run(_execute_automation_run(run_id))
