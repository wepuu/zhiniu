from fastapi import APIRouter, HTTPException, Request, status

from zhaoniu_api.access_control.models import (
    AccessActivationRequest,
    AccessActivationResponse,
    AccessEnvelope,
    EffectiveEntitlements,
)
from zhaoniu_api.access_control.rate_limit import (
    AccessRateLimitExceeded,
    enforce_access_rate_limit,
)
from zhaoniu_api.access_control.service import AccessControlError
from zhaoniu_api.config import get_settings
from zhaoniu_api.dependencies import AccessControlServiceDependency, CSRFSafe, CurrentUserId

router = APIRouter(prefix="/api/v1/me", tags=["access"])


@router.get("/access", response_model=AccessEnvelope)
async def get_access(
    user_id: CurrentUserId, service: AccessControlServiceDependency
) -> AccessEnvelope:
    return await service.access_envelope(user_id)


@router.get("/entitlements", response_model=EffectiveEntitlements)
async def get_entitlements(
    user_id: CurrentUserId, service: AccessControlServiceDependency
) -> EffectiveEntitlements:
    return await service.effective_entitlements(user_id)


@router.post("/access/activate", response_model=AccessActivationResponse)
async def activate_access(
    payload: AccessActivationRequest,
    request: Request,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    service: AccessControlServiceDependency,
) -> AccessActivationResponse:
    try:
        await enforce_access_rate_limit(
            get_settings(),
            scope="activate",
            identity=f"{user_id}:{request.client.host if request.client else 'unknown'}",
        )
        return await service.activate(user_id, payload.activation_code)
    except AccessRateLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="access_temporarily_unavailable",
        ) from error
    except AccessControlError as error:
        code = str(error)
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if code == "access_activation_unavailable"
            else (
                status.HTTP_409_CONFLICT
                if code == "email_verification_required"
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        )
        raise HTTPException(status_code=http_status, detail=code) from error
