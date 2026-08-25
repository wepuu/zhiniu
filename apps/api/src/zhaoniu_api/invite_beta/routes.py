from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from zhaoniu_api.dependencies import (
    CSRFSafe,
    CurrentUser,
    InviteBetaServiceDependency,
    OperatorContextDependency,
    OperatorServiceDependency,
)
from zhaoniu_api.invite_beta.models import (
    BetaCohortCreate,
    BetaCohortList,
    BetaCohortPause,
    BetaCohortView,
    BetaOnboardingUpdate,
    BetaOnboardingView,
    BetaRecipientsAdd,
)
from zhaoniu_api.invite_beta.service import InviteBetaError
from zhaoniu_api.operations_console.models import OperatorContext
from zhaoniu_api.operations_console.service import OperatorAuthorizationError

admin_router = APIRouter(prefix="/api/v1/admin/beta", tags=["invite beta operations"])
me_router = APIRouter(prefix="/api/v1/me/beta-onboarding", tags=["invite beta onboarding"])


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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


def _error(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@admin_router.get("/cohorts", response_model=BetaCohortList)
async def list_cohorts(
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> BetaCohortList:
    _require(context, operators, "beta.cohorts.read")
    return BetaCohortList(items=await service.list_cohorts(limit))


@admin_router.post("/cohorts", response_model=BetaCohortView, status_code=201)
async def create_cohort(
    payload: BetaCohortCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    _require(context, operators, "beta.cohorts.manage", elevated=True)
    result = await service.create_cohort(
        name=payload.name,
        target_size=payload.target_size,
        expires_in_days=payload.expires_in_days,
        actor_user_id=user.id,
    )
    await operators.audit(
        user.id,
        context,
        "beta.cohort.create",
        "beta_invite_cohort",
        str(result.id),
        request_id=request.headers.get("x-request-id"),
        metadata={"target_size": result.target_size},
    )
    return result


@admin_router.get("/cohorts/{cohort_id}", response_model=BetaCohortView)
async def get_cohort(
    cohort_id: UUID,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    _require(context, operators, "beta.cohorts.read")
    try:
        return await service.get_cohort(cohort_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@admin_router.post("/cohorts/{cohort_id}/recipients", response_model=BetaCohortView)
async def add_recipients(
    cohort_id: UUID,
    payload: BetaRecipientsAdd,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    _require(context, operators, "beta.cohorts.manage", elevated=True)
    try:
        result = await service.add_recipients(cohort_id, payload.emails)
    except (InviteBetaError, LookupError) as error:
        raise _error(error) from error
    await operators.audit(
        user.id,
        context,
        "beta.cohort.recipients.add",
        "beta_invite_cohort",
        str(cohort_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"count": len(payload.emails)},
    )
    return result


async def _cohort_action(
    action: str,
    cohort_id: UUID,
    request: Request,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
    reason_code: str | None = None,
) -> BetaCohortView:
    _require(context, operators, "beta.cohorts.manage", elevated=True)
    try:
        if action == "approve":
            result = await service.approve(cohort_id, user.id)
        elif action == "dispatch":
            result = await service.dispatch(cohort_id)
        elif action == "pause":
            result = await service.pause(cohort_id, reason_code or "operator_paused")
        else:
            result = await service.close(cohort_id)
    except (InviteBetaError, LookupError) as error:
        raise _error(error) from error
    await operators.audit(
        user.id,
        context,
        f"beta.cohort.{action}",
        "beta_invite_cohort",
        str(cohort_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"status": result.status, **({"reason_code": reason_code} if reason_code else {})},
    )
    return result


@admin_router.post("/cohorts/{cohort_id}/approve", response_model=BetaCohortView)
async def approve_cohort(
    cohort_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    return await _cohort_action(
        "approve", cohort_id, request, user, context, operators, service
    )


@admin_router.post("/cohorts/{cohort_id}/dispatch", response_model=BetaCohortView)
async def dispatch_cohort(
    cohort_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    return await _cohort_action(
        "dispatch", cohort_id, request, user, context, operators, service
    )


@admin_router.post("/cohorts/{cohort_id}/pause", response_model=BetaCohortView)
async def pause_cohort(
    cohort_id: UUID,
    payload: BetaCohortPause,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    return await _cohort_action(
        "pause",
        cohort_id,
        request,
        user,
        context,
        operators,
        service,
        payload.reason_code,
    )


@admin_router.post("/cohorts/{cohort_id}/close", response_model=BetaCohortView)
async def close_cohort(
    cohort_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    service: InviteBetaServiceDependency,
) -> BetaCohortView:
    return await _cohort_action("close", cohort_id, request, user, context, operators, service)


@me_router.get("", response_model=BetaOnboardingView)
async def get_onboarding(
    user: CurrentUser, service: InviteBetaServiceDependency
) -> BetaOnboardingView:
    return await service.onboarding(user.id)


@me_router.post("", response_model=BetaOnboardingView)
async def update_onboarding(
    payload: BetaOnboardingUpdate,
    _csrf: CSRFSafe,
    user: CurrentUser,
    service: InviteBetaServiceDependency,
) -> BetaOnboardingView:
    try:
        return await service.update_onboarding(user.id, payload.action)
    except InviteBetaError as error:
        raise _error(error) from error
