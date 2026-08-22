from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_explanations.dispatch import AIExplanationDispatcher
from zhaoniu_api.ai_explanations.models import (
    ExplanationQuestionCatalog,
    ExplanationRequestCreate,
    ExplanationRequestResponse,
)
from zhaoniu_api.ai_explanations.service import AIExplanationService, ExplanationServiceError
from zhaoniu_api.config import Settings, get_settings
from zhaoniu_api.database import get_session
from zhaoniu_api.dependencies import CSRFSafe, CurrentUserId

router = APIRouter(prefix="/api/v1/stocks/{symbol}/ai", tags=["ai-explanations"])


def get_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIExplanationService:
    return AIExplanationService(session, settings)


def get_dispatcher(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIExplanationDispatcher:
    return AIExplanationDispatcher(settings)


Service = Annotated[AIExplanationService, Depends(get_service)]
Dispatcher = Annotated[AIExplanationDispatcher, Depends(get_dispatcher)]


def _raise(error: Exception) -> NoReturn:
    code = str(error)
    if isinstance(error, LookupError):
        raise HTTPException(status_code=404, detail=code) from error
    mapping = {
        "advanced_access_required": 403,
        "ai_explanation_disabled": 503,
        "daily_limit_reached": 429,
        "deterministic_snapshot_missing": 409,
        "insufficient_evidence": 409,
        "request_not_failed": 409,
    }
    raise HTTPException(status_code=mapping.get(code, 400), detail=code) from error


@router.get("/questions", response_model=ExplanationQuestionCatalog)
async def questions(
    symbol: str, user_id: CurrentUserId, service: Service
) -> ExplanationQuestionCatalog:
    try:
        return await service.question_catalog(user_id, symbol)
    except (LookupError, ExplanationServiceError) as error:
        _raise(error)


@router.post(
    "/explanation-requests",
    response_model=ExplanationRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_request(
    symbol: str,
    payload: ExplanationRequestCreate,
    response: Response,
    user_id: CurrentUserId,
    service: Service,
    dispatcher: Dispatcher,
    _csrf: CSRFSafe,
) -> ExplanationRequestResponse:
    try:
        result, created = await service.create_request(
            user_id, symbol, payload.question_key, payload.client_request_id
        )
        if not created:
            response.status_code = status.HTTP_200_OK
            return result
        try:
            dispatcher.enqueue(str(result.id))
        except Exception as error:
            await service.mark_dispatch_failed(user_id, result.id)
            raise HTTPException(
                status_code=503, detail="ai_explanation_dispatch_unavailable"
            ) from error
        return result
    except (LookupError, ExplanationServiceError) as error:
        _raise(error)


@router.get("/explanation-requests/{request_id}", response_model=ExplanationRequestResponse)
async def get_request(
    symbol: str, request_id: UUID, user_id: CurrentUserId, service: Service
) -> ExplanationRequestResponse:
    try:
        result = await service.get_request(user_id, request_id)
        if result.symbol != (await service._stock_symbol(symbol)):
            raise LookupError("explanation_request_not_found")
        return result
    except (LookupError, ExplanationServiceError) as error:
        _raise(error)


@router.post(
    "/explanation-requests/{request_id}/retry",
    response_model=ExplanationRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_request(
    symbol: str,
    request_id: UUID,
    user_id: CurrentUserId,
    service: Service,
    dispatcher: Dispatcher,
    _csrf: CSRFSafe,
) -> ExplanationRequestResponse:
    try:
        result = await service.retry(user_id, request_id)
        if result.symbol != (await service._stock_symbol(symbol)):
            raise LookupError("explanation_request_not_found")
        try:
            dispatcher.enqueue(str(result.id))
        except Exception as error:
            await service.mark_dispatch_failed(user_id, result.id)
            raise HTTPException(
                status_code=503, detail="ai_explanation_dispatch_unavailable"
            ) from error
        return result
    except (LookupError, ExplanationServiceError) as error:
        _raise(error)
