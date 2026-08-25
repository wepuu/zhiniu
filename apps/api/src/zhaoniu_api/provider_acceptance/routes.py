from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from zhaoniu_api.dependencies import (
    CSRFSafe,
    CurrentUser,
    OperatorContextDependency,
    OperatorServiceDependency,
    ProviderAcceptanceServiceDependency,
)
from zhaoniu_api.operations_console.service import OperatorAuthorizationError
from zhaoniu_api.provider_acceptance.models import (
    ProviderAcceptanceRun,
    ProviderAcceptanceRunList,
)

router = APIRouter(prefix="/api/v1/admin/provider-acceptance", tags=["provider acceptance"])


def _require(context, service: OperatorServiceDependency, capability: str, *, elevated=False):  # type: ignore[no-untyped-def]
    try:
        service.require(context, capability, elevated=elevated)
    except OperatorAuthorizationError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/runs", response_model=ProviderAcceptanceRunList)
async def list_runs(
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProviderAcceptanceServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
) -> ProviderAcceptanceRunList:
    _require(context, operator, "coverage.read")
    return ProviderAcceptanceRunList(items=await service.list(limit))


@router.get("/runs/latest", response_model=ProviderAcceptanceRun)
async def latest_run(
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProviderAcceptanceServiceDependency,
) -> ProviderAcceptanceRun:
    _require(context, operator, "coverage.read")
    result = await service.latest()
    if result is None:
        raise HTTPException(status_code=404, detail="provider_acceptance_run_not_found")
    return result


@router.get("/runs/{run_id}", response_model=ProviderAcceptanceRun)
async def get_run(
    run_id: UUID,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProviderAcceptanceServiceDependency,
) -> ProviderAcceptanceRun:
    _require(context, operator, "coverage.read")
    try:
        return await service.get(run_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/runs", response_model=ProviderAcceptanceRun, status_code=201)
async def create_run(
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProviderAcceptanceServiceDependency,
) -> ProviderAcceptanceRun:
    _require(context, operator, "coverage.run", elevated=True)
    result = await service.run(requested_by_user_id=user.id)
    await operator.audit(
        user.id,
        context,
        "provider_acceptance.run",
        "provider_acceptance_run",
        str(result.id),
        request_id=request.headers.get("x-request-id"),
        metadata={"status": result.status, "beta_eligible": result.beta_eligible},
    )
    return result
