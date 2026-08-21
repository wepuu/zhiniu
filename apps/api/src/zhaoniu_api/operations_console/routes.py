from typing import Annotated, Literal
from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException, Query, Request, status
from redis.asyncio import Redis

from zhaoniu_api.config import get_settings
from zhaoniu_api.coverage.models import BackfillRunResponse
from zhaoniu_api.dependencies import (
    AuthServiceDependency,
    CoverageServiceDependency,
    CSRFSafe,
    CurrentUser,
    OperatorContextDependency,
    OperatorServiceDependency,
)
from zhaoniu_api.operations_console.models import (
    OperatorAccessCodeCreate,
    OperatorAccessCodeResponse,
    OperatorActionResponse,
    OperatorAuditListResponse,
    OperatorContext,
    OperatorDashboardResponse,
    OperatorElevateRequest,
    OperatorFeedbackListResponse,
    OperatorFeedbackUpdate,
    OperatorInviteBatchCreate,
    OperatorInviteBatchResponse,
    OperatorUserDetail,
    OperatorUserListResponse,
    ProviderStatusListResponse,
)
from zhaoniu_api.operations_console.service import OperatorAuthorizationError

router = APIRouter(prefix="/api/v1/admin", tags=["operator console"])


def _require(
    context: OperatorContext,
    service: OperatorServiceDependency,
    capability: str,
    *,
    elevated: bool = False,
) -> None:
    try:
        service.require(context, capability, elevated=elevated)
    except OperatorAuthorizationError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error


def _dispatcher() -> Celery:
    settings = get_settings()
    return Celery(
        "zhaoniu-operator-dispatch",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )


@router.get("/context", response_model=OperatorContext)
async def get_context(context: OperatorContextDependency) -> OperatorContext:
    return context


@router.post("/auth/elevate", response_model=OperatorContext)
async def elevate(
    payload: OperatorElevateRequest,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    auth: AuthServiceDependency,
    service: OperatorServiceDependency,
) -> OperatorContext:
    if not await auth.verify_current_password(user.id, payload.password):
        raise HTTPException(status_code=403, detail="operator_elevation_failed")
    settings = get_settings()
    elevated_until = await auth.elevate_operator_session(
        request.cookies.get(settings.auth_cookie_name), minutes=settings.operator_elevation_minutes
    )
    if elevated_until is None:
        raise HTTPException(status_code=401, detail="operator_session_unavailable")
    elevated = await service.context(user.id, elevated_until)
    assert elevated is not None
    await service.audit(
        user.id,
        elevated,
        "operator.auth.elevate",
        "user_session",
        None,
        request_id=request.headers.get("x-request-id"),
    )
    return elevated


@router.get("/dashboard", response_model=OperatorDashboardResponse)
async def dashboard(
    context: OperatorContextDependency, service: OperatorServiceDependency
) -> OperatorDashboardResponse:
    _require(context, service, "dashboard.read")
    return await service.dashboard()


@router.get("/users", response_model=OperatorUserListResponse)
async def list_users(
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
    user: CurrentUser,
    q: Annotated[str, Query(max_length=320)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> OperatorUserListResponse:
    _require(context, service, "users.read")
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        key = f"zhaoniu:operator:user-search:{user.id}"
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)
        if count > settings.operator_user_search_rate_limit:
            raise HTTPException(status_code=429, detail="operator_user_search_rate_limited")
    finally:
        await client.aclose()
    items = await service.list_users(q, limit)
    return OperatorUserListResponse(items=items, total=len(items))


@router.get("/users/{user_id}", response_model=OperatorUserDetail)
async def user_detail(
    user_id: UUID,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorUserDetail:
    _require(context, service, "users.read")
    detail = await service.user_detail(user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return detail


@router.post("/users/{user_id}/status", response_model=OperatorActionResponse)
async def set_user_status(
    user_id: UUID,
    target_status: Literal["active", "disabled"],
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorActionResponse:
    _require(context, service, "users.status.manage", elevated=True)
    if user_id == user.id and target_status == "disabled":
        raise HTTPException(status_code=409, detail="operator_cannot_disable_self")
    if not await service.set_user_status(user_id, target_status):
        raise HTTPException(status_code=404, detail="user_not_found")
    await service.audit(
        user.id,
        context,
        f"user.{target_status}",
        "user",
        str(user_id),
        request_id=request.headers.get("x-request-id"),
    )
    return OperatorActionResponse(status="completed", target_id=str(user_id))


@router.post("/users/{user_id}/revoke-sessions", response_model=OperatorActionResponse)
async def revoke_sessions(
    user_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorActionResponse:
    _require(context, service, "users.sessions.revoke", elevated=True)
    count = await service.revoke_sessions(user_id)
    await service.audit(
        user.id,
        context,
        "user.sessions.revoke_all",
        "user",
        str(user_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"revoked_count": count},
    )
    return OperatorActionResponse(status="completed", target_id=str(user_id), detail=str(count))


@router.post("/users/{user_id}/resend-verification", response_model=OperatorActionResponse)
async def resend_verification(
    user_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    auth: AuthServiceDependency,
    service: OperatorServiceDependency,
) -> OperatorActionResponse:
    _require(context, service, "users.verification.resend", elevated=True)
    try:
        result = await auth.resend_verification(user_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await service.audit(
        user.id,
        context,
        "user.verification.resend",
        "user",
        str(user_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"delivery_status": result},
    )
    return OperatorActionResponse(status="completed", target_id=str(user_id), detail=result)


@router.post(
    "/invite-batches",
    response_model=OperatorInviteBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite_batch(
    payload: OperatorInviteBatchCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorInviteBatchResponse:
    _require(context, service, "invites.manage", elevated=True)
    result = await service.generate_invites(
        count=payload.count,
        expires_in_days=payload.expires_in_days,
        name=payload.name,
        actor=user.id,
    )
    await service.audit(
        user.id,
        context,
        "invite.batch.create",
        "registration_invite_batch",
        str(result.batch_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"count": payload.count, "expires_in_days": payload.expires_in_days},
    )
    return result


@router.post(
    "/users/{user_id}/access-codes",
    response_model=OperatorAccessCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_access_code(
    user_id: UUID,
    payload: OperatorAccessCodeCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorAccessCodeResponse:
    _require(context, service, "access_codes.manage", elevated=True)
    try:
        result = await service.issue_access_code(
            user_id,
            term=payload.term,
            expires_in_days=payload.expires_in_days,
            actor=user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await service.audit(
        user.id,
        context,
        "access_code.issue",
        "user",
        str(user_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"term": payload.term, "expires_in_days": payload.expires_in_days},
    )
    return result


@router.get("/feedback", response_model=OperatorFeedbackListResponse)
async def list_feedback(
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
    feedback_status: Literal["new", "triaged", "resolved"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> OperatorFeedbackListResponse:
    _require(context, service, "feedback.manage")
    items = await service.list_feedback(feedback_status, limit)
    return OperatorFeedbackListResponse(items=items, total=len(items))


@router.patch("/feedback/{feedback_id}", response_model=OperatorActionResponse)
async def update_feedback(
    feedback_id: UUID,
    payload: OperatorFeedbackUpdate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorActionResponse:
    _require(context, service, "feedback.manage")
    try:
        updated = await service.update_feedback(feedback_id, payload.status)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not updated:
        raise HTTPException(status_code=404, detail="feedback_not_found")
    await service.audit(
        user.id,
        context,
        "feedback.status.update",
        "beta_feedback",
        str(feedback_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"status": payload.status},
    )
    return OperatorActionResponse(status="completed", target_id=str(feedback_id))


@router.get("/audit", response_model=OperatorAuditListResponse)
async def list_audit(
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> OperatorAuditListResponse:
    _require(context, service, "audit.read")
    return OperatorAuditListResponse(items=await service.list_audit(limit))


@router.get("/providers", response_model=ProviderStatusListResponse)
async def provider_statuses(
    context: OperatorContextDependency, service: OperatorServiceDependency
) -> ProviderStatusListResponse:
    _require(context, service, "providers.read")
    return ProviderStatusListResponse(items=await service.provider_statuses())


@router.post("/providers/{provider}/diagnose", response_model=ProviderStatusListResponse)
async def diagnose_provider(
    provider: Literal["deepseek", "resend"],
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> ProviderStatusListResponse:
    _require(context, service, "providers.diagnose", elevated=True)
    result = await service.diagnose_provider(provider, user.id)
    await service.audit(
        user.id,
        context,
        "provider.diagnose",
        "provider",
        provider,
        request_id=request.headers.get("x-request-id"),
        metadata={"status": result.status, "reason_code": result.reason_code},
    )
    return ProviderStatusListResponse(items=[result])


@router.post("/coverage/plans", response_model=BackfillRunResponse)
async def plan_coverage(
    _csrf: CSRFSafe,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
    coverage: CoverageServiceDependency,
) -> BackfillRunResponse:
    _require(context, service, "coverage.run")
    return await coverage.plan_backfill()


@router.post("/coverage/backfills/{run_id}", response_model=OperatorActionResponse, status_code=202)
async def run_backfill(
    run_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
) -> OperatorActionResponse:
    _require(context, service, "coverage.run", elevated=True)
    _dispatcher().send_task("coverage.run_backfill", args=[str(run_id)])
    await service.audit(
        user.id,
        context,
        "coverage.backfill.enqueue",
        "coverage_backfill_run",
        str(run_id),
        request_id=request.headers.get("x-request-id"),
    )
    return OperatorActionResponse(status="accepted", target_id=str(run_id))


@router.post("/ai/stock-health/{symbol}", response_model=OperatorActionResponse, status_code=202)
async def generate_stock_health(
    symbol: str,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    service: OperatorServiceDependency,
    retry_failed: bool = False,
) -> OperatorActionResponse:
    _require(context, service, "ai.run", elevated=True)
    _dispatcher().send_task("ai_research.generate_stock_health", args=[symbol, retry_failed])
    await service.audit(
        user.id,
        context,
        "ai.stock_health.enqueue",
        "stock",
        symbol,
        request_id=request.headers.get("x-request-id"),
        metadata={"retry_failed": retry_failed},
    )
    return OperatorActionResponse(status="accepted", target_id=symbol)
