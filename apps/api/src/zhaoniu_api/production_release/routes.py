from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from zhaoniu_api.dependencies import (
    CSRFSafe,
    CurrentUser,
    OperatorContextDependency,
    OperatorServiceDependency,
    ProductionReleaseServiceDependency,
)
from zhaoniu_api.operations_console.service import OperatorAuthorizationError
from zhaoniu_api.production_release.models import (
    ProductionDeploymentEventCreate,
    ProductionReleaseApprovalCreate,
    ProductionReleaseCandidate,
    ProductionReleaseCandidateCreate,
    ProductionReleaseCandidateList,
    ProductionReleaseGateRequest,
    ProductionReleaseGateRun,
)
from zhaoniu_api.production_release.service import (
    ProductionReleaseConflict,
    ProductionReleaseError,
)

router = APIRouter(prefix="/api/v1/admin/releases", tags=["production releases"])


def _require(context, service: OperatorServiceDependency, capability: str, *, elevated=False):  # type: ignore[no-untyped-def]
    try:
        service.require(context, capability, elevated=elevated)
    except OperatorAuthorizationError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


def _release_error(error: Exception) -> HTTPException:
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ProductionReleaseConflict):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("", response_model=ProductionReleaseCandidateList)
async def list_candidates(
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
) -> ProductionReleaseCandidateList:
    _require(context, operator, "releases.read")
    return ProductionReleaseCandidateList(items=await service.list_candidates(limit))


@router.get("/{candidate_id}", response_model=ProductionReleaseCandidate)
async def get_candidate(
    candidate_id: UUID,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
) -> ProductionReleaseCandidate:
    _require(context, operator, "releases.read")
    try:
        return await service.get(candidate_id)
    except LookupError as error:
        raise _release_error(error) from error


@router.post("", response_model=ProductionReleaseCandidate, status_code=201)
async def create_candidate(
    payload: ProductionReleaseCandidateCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
) -> ProductionReleaseCandidate:
    _require(context, operator, "releases.manage", elevated=True)
    try:
        result = await service.create(payload, user.id)
    except ProductionReleaseError as error:
        raise _release_error(error) from error
    await operator.audit(
        user.id,
        context,
        "production_release.create",
        "production_release_candidate",
        str(result.id),
        request_id=request.headers.get("x-request-id"),
        metadata={"commit_sha": result.commit_sha, "status": result.status},
    )
    return result


@router.post("/{candidate_id}/gates", response_model=ProductionReleaseGateRun)
async def evaluate_gate(
    candidate_id: UUID,
    payload: ProductionReleaseGateRequest,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
) -> ProductionReleaseGateRun:
    _require(context, operator, "releases.manage", elevated=True)
    try:
        result = await service.evaluate(candidate_id, payload.gate_type)
    except (LookupError, ProductionReleaseError) as error:
        raise _release_error(error) from error
    await operator.audit(
        user.id,
        context,
        "production_release.gate.evaluate",
        "production_release_candidate",
        str(candidate_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"gate_type": result.gate_type, "status": result.status},
    )
    return result


@router.post("/{candidate_id}/approvals", response_model=ProductionReleaseCandidate)
async def create_approval(
    candidate_id: UUID,
    payload: ProductionReleaseApprovalCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
) -> ProductionReleaseCandidate:
    _require(context, operator, "releases.approve", elevated=True)
    try:
        result = await service.approve(candidate_id, payload, user.id, context.role)
    except (LookupError, ProductionReleaseError) as error:
        raise _release_error(error) from error
    await operator.audit(
        user.id,
        context,
        "production_release.approval.record",
        "production_release_candidate",
        str(candidate_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"approval_role": payload.approval_role, "decision": payload.decision},
    )
    return result


@router.post("/{candidate_id}/deployment-events", response_model=ProductionReleaseCandidate)
async def record_deployment_event(
    candidate_id: UUID,
    payload: ProductionDeploymentEventCreate,
    request: Request,
    _csrf: CSRFSafe,
    user: CurrentUser,
    context: OperatorContextDependency,
    operator: OperatorServiceDependency,
    service: ProductionReleaseServiceDependency,
) -> ProductionReleaseCandidate:
    _require(context, operator, "releases.record", elevated=True)
    try:
        result = await service.record_event(candidate_id, payload, user.id)
    except (LookupError, ProductionReleaseError) as error:
        raise _release_error(error) from error
    await operator.audit(
        user.id,
        context,
        "production_release.deployment.record",
        "production_release_candidate",
        str(candidate_id),
        request_id=request.headers.get("x-request-id"),
        metadata={"event_type": payload.event_type, "deployment_ref": payload.deployment_ref},
    )
    return result
