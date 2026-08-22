from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from zhaoniu_api.company_timeline.models import CompanyTimelineEnvelope
from zhaoniu_api.dependencies import CompanyTimelineServiceDependency

router = APIRouter(prefix="/api/v1", tags=["company-timeline"])


@router.get("/stocks/{symbol}/timeline", response_model=CompanyTimelineEnvelope)
async def get_company_timeline(
    symbol: str,
    service: CompanyTimelineServiceDependency,
    source_kind: Literal["fundamental", "peer", "corporate_event"] | None = None,
    minimum_attention: Literal["info", "notice", "important"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CompanyTimelineEnvelope:
    try:
        return await service.get(
            symbol,
            source_kind=source_kind,
            minimum_attention=minimum_attention,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        if str(exc) == "stock_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found"
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
