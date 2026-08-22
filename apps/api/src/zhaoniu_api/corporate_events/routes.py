from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from zhaoniu_api.corporate_events.models import (
    CorporateEventListResponse,
    CorporateEventResponse,
    EventRadarEnvelope,
    EventThreadResponse,
)
from zhaoniu_api.dependencies import CorporateEventServiceDependency

router = APIRouter(prefix="/api/v1", tags=["corporate-events"])


@router.get(
    "/stocks/{symbol}/events",
    response_model=CorporateEventListResponse,
)
async def list_events(
    symbol: str,
    service: CorporateEventServiceDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> CorporateEventListResponse:
    try:
        return await service.list_events(symbol, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
        ) from exc


@router.get(
    "/stocks/{symbol}/events/{event_id}",
    response_model=CorporateEventResponse,
)
async def get_event(
    symbol: str,
    event_id: UUID,
    service: CorporateEventServiceDependency,
) -> CorporateEventResponse:
    try:
        result = await service.get_event(symbol, event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return result


@router.get(
    "/stocks/{symbol}/events/{event_id}/thread",
    response_model=EventThreadResponse,
)
async def get_event_thread(
    symbol: str,
    event_id: UUID,
    service: CorporateEventServiceDependency,
) -> EventThreadResponse:
    try:
        result = await service.get_event_thread(symbol, event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return result


@router.get(
    "/stocks/{symbol}/event-radar",
    response_model=EventRadarEnvelope,
)
async def get_event_radar(
    symbol: str,
    service: CorporateEventServiceDependency,
) -> EventRadarEnvelope:
    try:
        return await service.get_radar(symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
        ) from exc
