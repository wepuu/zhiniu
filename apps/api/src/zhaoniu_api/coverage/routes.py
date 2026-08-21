from fastapi import APIRouter, HTTPException, Request, status

from zhaoniu_api.access_control.rate_limit import (
    AccessRateLimitExceeded,
    enforce_access_rate_limit,
)
from zhaoniu_api.config import get_settings
from zhaoniu_api.coverage.models import (
    BetaFeedbackCreate,
    BetaFeedbackResponse,
    StockCoverageResponse,
)
from zhaoniu_api.dependencies import CoverageServiceDependency, CSRFSafe, CurrentUserId

router = APIRouter(prefix="/api/v1")


@router.get(
    "/stocks/{symbol}/coverage",
    response_model=StockCoverageResponse,
    tags=["coverage"],
)
async def get_stock_coverage(
    symbol: str, service: CoverageServiceDependency
) -> StockCoverageResponse:
    try:
        return await service.stock_coverage(symbol)
    except ValueError as error:
        if str(error) == "stock_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="stock_not_found"
            ) from error
        raise


@router.post(
    "/me/beta-feedback",
    response_model=BetaFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["beta"],
)
async def create_beta_feedback(
    payload: BetaFeedbackCreate,
    request: Request,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: CoverageServiceDependency,
) -> BetaFeedbackResponse:
    settings = get_settings()
    try:
        await enforce_access_rate_limit(
            settings,
            scope="beta_feedback",
            identity=f"{user_id}:{request.client.host if request.client else 'unknown'}",
            limit=settings.beta_feedback_rate_limit,
            window_seconds=3600,
        )
    except AccessRateLimitExceeded as error:
        raise HTTPException(status_code=429, detail="beta_feedback_rate_limited") from error
    return await service.create_feedback(user_id, payload)
