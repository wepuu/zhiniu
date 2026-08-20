from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from zhaoniu_api.dependencies import CSRFSafe, CurrentUserId, ResearchFeedServiceDependency
from zhaoniu_api.research_feed.models import (
    AlertListResponse,
    AlertSettingsResponse,
    AlertSettingsUpdate,
    AlertSummaryResponse,
    ResearchFeedResponse,
    WatchlistCoverageResponse,
)

router = APIRouter(prefix="/api/v1/me", tags=["personalized research"])


@router.get("/research-feed", response_model=ResearchFeedResponse)
async def get_research_feed(
    user_id: CurrentUserId,
    service: ResearchFeedServiceDependency,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
    source_kind: Literal["fundamental", "peer", "corporate_event"] | None = None,
    minimum_attention: Literal["info", "notice", "important"] | None = None,
) -> ResearchFeedResponse:
    try:
        return await service.feed(
            user_id,
            cursor=cursor,
            limit=limit,
            source_kind=source_kind,
            minimum_attention=minimum_attention,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/research-coverage", response_model=WatchlistCoverageResponse)
async def get_research_coverage(
    user_id: CurrentUserId, service: ResearchFeedServiceDependency
) -> WatchlistCoverageResponse:
    return await service.coverage(user_id)


@router.get("/research-alerts", response_model=AlertListResponse)
async def get_research_alerts(
    user_id: CurrentUserId,
    service: ResearchFeedServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertListResponse:
    return await service.alerts(user_id, limit=limit)


@router.get("/research-alerts/summary", response_model=AlertSummaryResponse)
async def get_research_alert_summary(
    user_id: CurrentUserId, service: ResearchFeedServiceDependency
) -> AlertSummaryResponse:
    return await service.alert_summary(user_id)


@router.post("/research-alerts/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_research_alerts_read(
    _csrf: CSRFSafe, user_id: CurrentUserId, service: ResearchFeedServiceDependency
) -> Response:
    await service.mark_all_read(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/research-alerts/{delivery_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_research_alert_read(
    delivery_id: UUID,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ResearchFeedServiceDependency,
) -> Response:
    if not await service.mark_read(user_id, delivery_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/research-alert-settings", response_model=AlertSettingsResponse)
async def get_research_alert_settings(
    user_id: CurrentUserId, service: ResearchFeedServiceDependency
) -> AlertSettingsResponse:
    return await service.get_settings(user_id)


@router.put("/research-alert-settings", response_model=AlertSettingsResponse)
async def update_research_alert_settings(
    payload: AlertSettingsUpdate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ResearchFeedServiceDependency,
) -> AlertSettingsResponse:
    return await service.update_settings(user_id, payload)
