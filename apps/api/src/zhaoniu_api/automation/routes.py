from typing import Annotated
from uuid import UUID, uuid4

from celery import Celery  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException, Query, Request, status

from zhaoniu_api.automation.models import (
    AutomationPolicyListResponse,
    AutomationPolicyUpdate,
    AutomationPolicyView,
    AutomationRunDetail,
    AutomationRunListResponse,
    AutomationTriggerResponse,
)
from zhaoniu_api.automation.service import POLICY_KEY
from zhaoniu_api.config import get_settings
from zhaoniu_api.dependencies import (
    AutomationServiceDependency,
    CSRFSafe,
    CurrentUser,
    OperatorContextDependency,
    OperatorServiceDependency,
)
from zhaoniu_api.operations_console.models import OperatorContext
from zhaoniu_api.operations_console.service import OperatorAuthorizationError

router = APIRouter(prefix="/api/v1/admin/automation", tags=["automation operations"])


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
        raise HTTPException(status_code=403, detail=str(error)) from error


def _dispatcher() -> Celery:
    settings = get_settings()
    return Celery(
        "zhaoniu-automation-dispatch",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )


@router.get("/policies", response_model=AutomationPolicyListResponse)
async def list_policies(
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationPolicyListResponse:
    _require(context, operators, "automation.read")
    return AutomationPolicyListResponse(items=await automation.list_policies())


@router.patch("/policies/{policy_key}", response_model=AutomationPolicyView)
async def update_policy(
    policy_key: str,
    payload: AutomationPolicyUpdate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationPolicyView:
    _require(context, operators, "automation.manage", elevated=True)
    try:
        result = await automation.update_policy(
            policy_key,
            enabled=payload.enabled,
            configuration=payload.configuration,
            actor_user_id=user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    await operators.audit(
        user.id,
        context,
        "automation.policy.update",
        "automation_policy",
        policy_key,
        request_id=request.headers.get("x-request-id"),
        metadata={
            "enabled": payload.enabled,
            "configuration_hash": result.configuration_hash,
            "revision": result.revision,
        },
    )
    return result


@router.get("/runs", response_model=AutomationRunListResponse)
async def list_runs(
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationRunListResponse:
    _require(context, operators, "automation.read")
    items = await automation.list_runs(limit)
    return AutomationRunListResponse(items=items, total=len(items))


@router.get("/runs/{run_id}", response_model=AutomationRunDetail)
async def run_detail(
    run_id: UUID,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationRunDetail:
    _require(context, operators, "automation.read")
    try:
        return await automation.run_detail(run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/policies/{policy_key}/run",
    response_model=AutomationTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_now(
    policy_key: str,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationTriggerResponse:
    _require(context, operators, "automation.run", elevated=True)
    result = await automation.trigger_run(
        policy_key,
        request_key=request.headers.get("idempotency-key") or str(uuid4()),
    )
    if result.status == "accepted":
        _dispatcher().send_task("automation.execute_run", args=[str(result.run_id)])
    await operators.audit(
        user.id,
        context,
        "automation.run.enqueue",
        "automation_run",
        str(result.run_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"policy_key": policy_key, "status": result.status},
    )
    return result


@router.post(
    "/runs/{run_id}/resume",
    response_model=AutomationTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_run(
    run_id: UUID,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationTriggerResponse:
    _require(context, operators, "automation.resume", elevated=True)
    try:
        result = await automation.resume_run(run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if result.status == "accepted":
        _dispatcher().send_task("automation.execute_run", args=[str(run_id)])
    await operators.audit(
        user.id,
        context,
        "automation.run.resume",
        "automation_run",
        str(run_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"status": result.status},
    )
    return result


@router.post(
    "/stocks/{symbol}/refresh",
    response_model=AutomationTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_stock(
    symbol: str,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operators: OperatorServiceDependency,
    automation: AutomationServiceDependency,
) -> AutomationTriggerResponse:
    _require(context, operators, "automation.run", elevated=True)
    try:
        result = await automation.trigger_run(
            POLICY_KEY,
            request_key=request.headers.get("idempotency-key"),
            symbols=(symbol,),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result.status == "accepted":
        _dispatcher().send_task("automation.execute_run", args=[str(result.run_id)])
    await operators.audit(
        user.id,
        context,
        "automation.stock.refresh",
        "stock",
        symbol,
        request_id=request.headers.get("x-request-id"),
        metadata={"run_id": str(result.run_id), "status": result.status},
    )
    return result
