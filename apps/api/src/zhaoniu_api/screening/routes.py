from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from zhaoniu_api.dependencies import (
    CSRFSafe,
    CurrentUserId,
    ScreeningDispatcherDependency,
    ScreeningServiceDependency,
)
from zhaoniu_api.screening.models import (
    ScreenCatalogResponse,
    ScreenCoverageResponse,
    ScreenExecutionCreate,
    ScreenExecutionResponse,
    ScreenQuery,
    ScreenResultListResponse,
    ScreenValidationResponse,
)

router = APIRouter(prefix="/api/v1/screens", tags=["research screening"])


@router.get("/catalog", response_model=ScreenCatalogResponse)
async def get_screen_catalog(service: ScreeningServiceDependency) -> ScreenCatalogResponse:
    return await service.catalog()


@router.get("/coverage", response_model=ScreenCoverageResponse)
async def get_screen_coverage(service: ScreeningServiceDependency) -> ScreenCoverageResponse:
    return await service.coverage()


@router.post("/validate", response_model=ScreenValidationResponse)
async def validate_screen(
    query: ScreenQuery, service: ScreeningServiceDependency
) -> ScreenValidationResponse:
    return service.validate(query)


@router.post(
    "/executions",
    response_model=ScreenExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_screen_execution(
    payload: ScreenExecutionCreate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
    dispatcher: ScreeningDispatcherDependency,
) -> ScreenExecutionResponse:
    try:
        execution = await service.create_execution(user_id, payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution.status == "pending":
        dispatcher.enqueue(execution.id)
    return execution


@router.get("/executions/{execution_id}", response_model=ScreenExecutionResponse)
async def get_screen_execution(
    execution_id: UUID,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
) -> ScreenExecutionResponse:
    response = await service.get_execution(user_id, execution_id)
    if response is None:
        raise HTTPException(status_code=404, detail="screen_execution_not_found")
    return response


@router.get("/executions/{execution_id}/results", response_model=ScreenResultListResponse)
async def get_screen_results(
    execution_id: UUID,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
) -> ScreenResultListResponse:
    try:
        response = await service.results(user_id, execution_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="screen_execution_not_found")
    return response
