from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from zhaoniu_api.comparisons.models import (
    ComparisonCatalogResponse,
    ComparisonCreate,
    ComparisonListResponse,
    ComparisonResponse,
    SavedComparisonCreate,
    SavedComparisonListResponse,
    SavedComparisonResponse,
)
from zhaoniu_api.dependencies import (
    ComparisonDispatcherDependency,
    ComparisonServiceDependency,
    CSRFSafe,
    CurrentUserId,
)

router = APIRouter(prefix="/api/v1/comparisons", tags=["company comparisons"])


@router.get("/catalog", response_model=ComparisonCatalogResponse)
async def catalog(
    user_id: CurrentUserId, service: ComparisonServiceDependency
) -> ComparisonCatalogResponse:
    return await service.catalog(user_id)


@router.post("", response_model=ComparisonResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_comparison(
    payload: ComparisonCreate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ComparisonServiceDependency,
    dispatcher: ComparisonDispatcherDependency,
) -> ComparisonResponse:
    try:
        response = await service.create(user_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        code = str(exc)
        http_status = (
            403 if code in {"advanced_access_required", "comparison_access_required"} else 422
        )
        raise HTTPException(status_code=http_status, detail=code) from exc
    if response.status == "pending":
        try:
            dispatcher.enqueue(response.id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="comparison_dispatch_unavailable") from exc
    return response


@router.get("", response_model=ComparisonListResponse)
async def list_comparisons(
    user_id: CurrentUserId,
    service: ComparisonServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ComparisonListResponse:
    return ComparisonListResponse(items=await service.list_requests(user_id, limit))


@router.post("/saved", response_model=SavedComparisonResponse, status_code=status.HTTP_201_CREATED)
async def save_comparison(
    payload: SavedComparisonCreate,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: ComparisonServiceDependency,
) -> SavedComparisonResponse:
    try:
        return await service.create_saved(user_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=403 if str(exc) == "advanced_access_required" else 422, detail=str(exc)
        ) from exc


@router.get("/saved/list", response_model=SavedComparisonListResponse)
async def list_saved_comparisons(
    user_id: CurrentUserId, service: ComparisonServiceDependency
) -> SavedComparisonListResponse:
    return await service.list_saved(user_id)


@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_comparison(
    saved_id: UUID, _csrf: CSRFSafe, user_id: CurrentUserId, service: ComparisonServiceDependency
) -> Response:
    if not await service.delete_saved(user_id, saved_id):
        raise HTTPException(status_code=404, detail="saved_comparison_not_found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{request_id}", response_model=ComparisonResponse)
async def get_comparison(
    request_id: UUID, user_id: CurrentUserId, service: ComparisonServiceDependency
) -> ComparisonResponse:
    try:
        return await service.get(user_id, request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
