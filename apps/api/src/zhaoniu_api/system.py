import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings, get_settings
from zhaoniu_api.database import get_session
from zhaoniu_api.schemas import DependencyStatus, HealthResponse, ReadinessResponse

MIGRATION_HEAD = "20260825_0026"
router = APIRouter(tags=["system"])


@router.get("/livez", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service="zhaoniu-api", version="0.1.0")


@router.get("/readyz", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    dependencies: list[DependencyStatus] = []
    database_ready = False
    migration_ready = False
    try:
        await session.execute(text("SELECT 1"))
        database_ready = True
        dependencies.append(DependencyStatus(name="postgresql", status="healthy"))
        current = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        migration_ready = current == MIGRATION_HEAD
        dependencies.append(
            DependencyStatus(
                name="migration",
                status="healthy" if migration_ready else "unavailable",
                detail=None if migration_ready else "migration_not_at_head",
            )
        )
    except Exception:
        dependencies.append(
            DependencyStatus(name="postgresql", status="unavailable", detail="database_unavailable")
        )

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await asyncio.wait_for(redis.ping(), timeout=1.5)
        dependencies.append(DependencyStatus(name="redis", status="healthy"))
    except (TimeoutError, RedisError, OSError):
        dependencies.append(
            DependencyStatus(name="redis", status="degraded", detail="redis_unavailable")
        )
    finally:
        await redis.aclose()

    ready = database_ready and migration_ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        service="zhaoniu-api",
        migration_head=MIGRATION_HEAD,
        dependencies=dependencies,
    )
