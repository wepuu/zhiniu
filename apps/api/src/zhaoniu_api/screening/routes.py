from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from zhaoniu_api.dependencies import (
    CSRFSafe,
    CurrentUserId,
    NaturalLanguageScreeningServiceDependency,
    ScreeningDispatcherDependency,
    ScreeningServiceDependency,
)
from zhaoniu_api.screening.models import (
    NaturalLanguageParseCreate,
    NaturalLanguageParseResponse,
    SavedScreenCreate,
    SavedScreenListResponse,
    SavedScreenResponse,
    SavedScreenUpdate,
    ScreenCatalogResponse,
    ScreenCoverageEstimateResponse,
    ScreenCoverageResponse,
    ScreenExecutionCreate,
    ScreenExecutionListResponse,
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


@router.post("/coverage/estimate", response_model=ScreenCoverageEstimateResponse)
async def estimate_screen_coverage(
    query: ScreenQuery, service: ScreeningServiceDependency
) -> ScreenCoverageEstimateResponse:
    try:
        return await service.estimate_coverage(query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        execution = await service.create_execution(
            user_id,
            payload.query,
            saved_screen_id=payload.saved_screen_id,
            confirmed_parse_run_id=payload.confirmed_parse_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution.status == "pending":
        dispatcher.enqueue(execution.id)
    return execution


@router.get("/executions", response_model=ScreenExecutionListResponse)
async def list_screen_executions(
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScreenExecutionListResponse:
    return await service.list_executions(user_id, limit)


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


@router.post(
    "/natural-language/parses",
    response_model=NaturalLanguageParseResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_natural_language_parse(
    payload: NaturalLanguageParseCreate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: NaturalLanguageScreeningServiceDependency,
    dispatcher: ScreeningDispatcherDependency,
) -> NaturalLanguageParseResponse:
    try:
        response = await service.create_run(user_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if response.status == "pending":
        try:
            dispatcher.enqueue_parse(response.id, payload.text.strip())
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="screen_parse_dispatch_unavailable"
            ) from exc
    return response


@router.get("/natural-language/parses/{parse_run_id}", response_model=NaturalLanguageParseResponse)
async def get_natural_language_parse(
    parse_run_id: UUID,
    user_id: CurrentUserId,
    service: NaturalLanguageScreeningServiceDependency,
) -> NaturalLanguageParseResponse:
    response = await service.get_run(user_id, parse_run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="screen_parse_run_not_found")
    return response


@router.post(
    "/saved",
    response_model=SavedScreenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_screen(
    payload: SavedScreenCreate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
) -> SavedScreenResponse:
    try:
        return await service.create_saved_screen(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/saved", response_model=SavedScreenListResponse)
async def list_saved_screens(
    user_id: CurrentUserId, service: ScreeningServiceDependency
) -> SavedScreenListResponse:
    return await service.list_saved_screens(user_id)


@router.get("/saved/{saved_screen_id}", response_model=SavedScreenResponse)
async def get_saved_screen(
    saved_screen_id: UUID,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
) -> SavedScreenResponse:
    response = await service.get_saved_screen(user_id, saved_screen_id)
    if response is None:
        raise HTTPException(status_code=404, detail="saved_screen_not_found")
    return response


@router.patch("/saved/{saved_screen_id}", response_model=SavedScreenResponse)
async def update_saved_screen(
    saved_screen_id: UUID,
    payload: SavedScreenUpdate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
) -> SavedScreenResponse:
    try:
        response = await service.update_saved_screen(user_id, saved_screen_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="saved_screen_not_found")
    return response


@router.delete("/saved/{saved_screen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_screen(
    saved_screen_id: UUID,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ScreeningServiceDependency,
) -> Response:
    if not await service.delete_saved_screen(user_id, saved_screen_id):
        raise HTTPException(status_code=404, detail="saved_screen_not_found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
