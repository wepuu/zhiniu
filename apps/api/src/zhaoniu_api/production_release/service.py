from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    BetaFeedbackItemRecord,
    ProductionDeploymentEventRecord,
    ProductionReleaseApprovalRecord,
    ProductionReleaseCandidateRecord,
    ProductionReleaseGateItemRecord,
    ProductionReleaseGateRunRecord,
    ProviderAcceptanceRunRecord,
    ProviderDiagnosticRunRecord,
    TransactionalEmailDeliveryRecord,
    TransactionalEmailProviderEventRecord,
    User,
)
from zhaoniu_api.production_release.models import (
    ApprovalDecision,
    ApprovalRole,
    ArtifactStatus,
    DeploymentEventType,
    GateItemStatus,
    GateStatus,
    GateType,
    ProductionDeploymentEvent,
    ProductionDeploymentEventCreate,
    ProductionReleaseApproval,
    ProductionReleaseApprovalCreate,
    ProductionReleaseCandidate,
    ProductionReleaseCandidateCreate,
    ProductionReleaseGateItem,
    ProductionReleaseGateRun,
    ReleaseStatus,
)
from zhaoniu_api.provider_configuration.models import ResendConfiguration
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService
from zhaoniu_api.system import MIGRATION_HEAD

RULE_SET_VERSION = "phase22-production-release-v1"
INVITE_EVIDENCE_MAX_AGE = timedelta(hours=24)
RESTORE_EVIDENCE_MAX_AGE = timedelta(hours=72)


class ProductionReleaseError(ValueError):
    pass


class ProductionReleaseConflict(ProductionReleaseError):
    pass


@dataclass(frozen=True, slots=True)
class GateCheck:
    key: str
    category: str
    passed: bool
    reason_code: str | None
    evidence: dict[str, object]
    expires_at: datetime | None = None
    mandatory: bool = True


def evidence_fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def approval_role_allowed(operator_role: str, approval_role: ApprovalRole) -> bool:
    if approval_role == "product_operations":
        return operator_role == "operations"
    return operator_role == "security_admin"


class ProductionReleaseService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._providers = ProviderConfigurationService(session, settings)

    async def create(
        self, request: ProductionReleaseCandidateCreate, actor_user_id: UUID
    ) -> ProductionReleaseCandidate:
        row = ProductionReleaseCandidateRecord(
            id=uuid4(),
            target_environment="production",
            status="draft",
            created_by_user_id=actor_user_id,
            **request.model_dump(),
        )
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ProductionReleaseConflict("release_candidate_already_exists") from error
        return await self.get(row.id)

    async def list_candidates(self, limit: int = 20) -> list[ProductionReleaseCandidate]:
        rows = list(
            (
                await self._session.scalars(
                    select(ProductionReleaseCandidateRecord)
                    .order_by(ProductionReleaseCandidateRecord.created_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        return [await self._view(row) for row in rows]

    async def get(self, candidate_id: UUID) -> ProductionReleaseCandidate:
        row = await self._session.get(ProductionReleaseCandidateRecord, candidate_id)
        if row is None:
            raise LookupError("release_candidate_not_found")
        return await self._view(row)

    async def evaluate(self, candidate_id: UUID, gate_type: GateType) -> ProductionReleaseGateRun:
        candidate = await self._locked_candidate(candidate_id)
        if candidate.status in {"released", "rolled_back", "rejected"}:
            raise ProductionReleaseConflict("release_candidate_terminal")
        if gate_type == "closed_deployment" and candidate.status not in {
            "draft",
            "blocked",
            "ready_closed",
        }:
            raise ProductionReleaseConflict("closed_deployment_gate_invalid_state")
        if gate_type == "invite_activation" and candidate.status not in {
            "deployed_observing",
            "ready_invites",
        }:
            raise ProductionReleaseConflict("invite_activation_gate_invalid_state")
        started_at = datetime.now(UTC)
        checks = (
            await self._closed_deployment_checks(candidate, started_at)
            if gate_type == "closed_deployment"
            else await self._invite_activation_checks(candidate, started_at)
        )
        status = (
            "passed" if all(not item.mandatory or item.passed for item in checks) else "blocked"
        )
        result = {
            "candidate_id": str(candidate.id),
            "gate_type": gate_type,
            "rule_set_version": RULE_SET_VERSION,
            "status": status,
            "items": [
                {
                    "key": item.key,
                    "status": "passed" if item.passed else "failed",
                    "evidence": item.evidence,
                    "reason_code": item.reason_code,
                }
                for item in checks
            ],
        }
        finished_at = datetime.now(UTC)
        run = ProductionReleaseGateRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            gate_type=gate_type,
            status=status,
            rule_set_version=RULE_SET_VERSION,
            result_fingerprint=evidence_fingerprint(result),
            started_at=started_at,
            finished_at=finished_at,
        )
        self._session.add(run)
        for item in checks:
            evidence = dict(item.evidence)
            self._session.add(
                ProductionReleaseGateItemRecord(
                    id=uuid4(),
                    run_id=run.id,
                    check_key=item.key,
                    category=item.category,
                    mandatory=item.mandatory,
                    status="passed" if item.passed else "failed",
                    reason_code=item.reason_code,
                    evidence_json=evidence,
                    evidence_fingerprint=evidence_fingerprint(evidence),
                    checked_at=finished_at,
                    expires_at=item.expires_at,
                )
            )
        if gate_type == "closed_deployment":
            candidate.status = "ready_closed" if status == "passed" else "blocked"
        elif status == "passed":
            candidate.status = "ready_invites"
        await self._session.commit()
        return await self._gate_view(run)

    async def approve(
        self,
        candidate_id: UUID,
        request: ProductionReleaseApprovalCreate,
        actor_user_id: UUID,
        operator_role: str,
    ) -> ProductionReleaseCandidate:
        candidate = await self._locked_candidate(candidate_id)
        if candidate.status in {"released", "rolled_back", "rejected"}:
            raise ProductionReleaseConflict("release_candidate_terminal")
        if candidate.created_by_user_id == actor_user_id:
            raise ProductionReleaseConflict("release_creator_cannot_approve")
        if not approval_role_allowed(operator_role, request.approval_role):
            raise ProductionReleaseError("release_approval_role_not_allowed")
        self._session.add(
            ProductionReleaseApprovalRecord(
                id=uuid4(),
                candidate_id=candidate.id,
                approval_role=request.approval_role,
                decision=request.decision,
                actor_user_id=actor_user_id,
                note=request.note,
            )
        )
        if request.decision == "rejected":
            candidate.status = "rejected"
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ProductionReleaseConflict("release_approval_already_recorded") from error
        return await self.get(candidate.id)

    async def record_event(
        self,
        candidate_id: UUID,
        request: ProductionDeploymentEventCreate,
        actor_user_id: UUID,
    ) -> ProductionReleaseCandidate:
        candidate = await self._locked_candidate(candidate_id)
        self._assert_event_transition(candidate.status, request.event_type)
        now = datetime.now(UTC)
        if request.event_type == "deployed":
            checks = await self._closed_deployment_checks(candidate, now)
            if not all(not item.mandatory or item.passed for item in checks):
                raise ProductionReleaseConflict("closed_deployment_gate_no_longer_passes")
        elif request.event_type == "released":
            checks = await self._invite_activation_checks(candidate, now)
            if not all(not item.mandatory or item.passed for item in checks):
                raise ProductionReleaseConflict("invite_activation_gate_no_longer_passes")
        self._session.add(
            ProductionDeploymentEventRecord(
                id=uuid4(),
                candidate_id=candidate.id,
                event_type=request.event_type,
                deployment_ref=request.deployment_ref.strip(),
                reason_code=request.reason_code,
                recorded_by_user_id=actor_user_id,
            )
        )
        candidate.status = {
            "deployed": "deployed_observing",
            "released": "released",
            "failed": "rolled_back",
            "rolled_back": "rolled_back",
        }[request.event_type]
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise ProductionReleaseConflict("deployment_event_already_recorded") from error
        return await self.get(candidate.id)

    @staticmethod
    def _assert_event_transition(status: str, event_type: DeploymentEventType) -> None:
        allowed = {
            "deployed": {"ready_closed"},
            "released": {"ready_invites"},
            "failed": {"ready_closed", "deployed_observing", "ready_invites"},
            "rolled_back": {"deployed_observing", "ready_invites", "released"},
        }
        if status not in allowed[event_type]:
            raise ProductionReleaseConflict("deployment_event_invalid_transition")

    async def _locked_candidate(self, candidate_id: UUID) -> ProductionReleaseCandidateRecord:
        row = await self._session.scalar(
            select(ProductionReleaseCandidateRecord)
            .where(ProductionReleaseCandidateRecord.id == candidate_id)
            .with_for_update()
        )
        if row is None:
            raise LookupError("release_candidate_not_found")
        return row

    async def _closed_deployment_checks(
        self, candidate: ProductionReleaseCandidateRecord, now: datetime
    ) -> list[GateCheck]:
        current = await self._session.scalar(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        runtime_reason: str | None = None
        try:
            self._settings.validate_runtime_security()
            await self._providers.validate_production_runtime()
        except ValueError as error:
            runtime_reason = str(error)
        engineering_approval = await self._approval(candidate.id, "engineering")
        restore_expires_at = candidate.restore_verified_at + RESTORE_EVIDENCE_MAX_AGE
        return [
            self._check(
                "environment.production",
                "runtime",
                self._settings.app_env == "production",
                {"app_env": self._settings.app_env},
                "release_environment_not_production",
            ),
            self._check(
                "runtime.security",
                "security",
                runtime_reason is None,
                {"validation": "passed" if runtime_reason is None else "failed"},
                runtime_reason,
            ),
            self._check(
                "migration.database_head",
                "database",
                current == MIGRATION_HEAD,
                {"current": current or "missing", "expected": MIGRATION_HEAD},
                "migration_not_at_head",
            ),
            self._check(
                "migration.candidate_head",
                "database",
                candidate.migration_head == MIGRATION_HEAD,
                {"candidate": candidate.migration_head, "expected": MIGRATION_HEAD},
                "candidate_migration_not_at_head",
            ),
            self._check(
                "artifact.quality_gate",
                "engineering",
                candidate.quality_gate_status == "passed",
                {"status": candidate.quality_gate_status},
                "quality_gate_failed",
            ),
            self._check(
                "artifact.e2e",
                "engineering",
                candidate.e2e_status == "passed",
                {"status": candidate.e2e_status},
                "e2e_failed",
            ),
            self._check(
                "artifact.security_scan",
                "security",
                candidate.security_scan_status == "passed",
                {"status": candidate.security_scan_status},
                "security_scan_failed",
            ),
            self._check(
                "backup.restore_fresh",
                "recovery",
                restore_expires_at >= now,
                {"verified_at": candidate.restore_verified_at.isoformat(), "max_age_hours": 72},
                "restore_evidence_stale",
                restore_expires_at,
            ),
            self._check(
                "registration.closed",
                "access",
                self._settings.registration_mode == "closed",
                {"registration_mode": self._settings.registration_mode},
                "registration_not_closed",
            ),
            self._check(
                "automation.hard_disabled",
                "automation",
                self._settings.automation_hard_disabled,
                {"hard_disabled": self._settings.automation_hard_disabled},
                "automation_not_hard_disabled",
            ),
            self._check(
                "approval.engineering",
                "approval",
                engineering_approval is not None and engineering_approval.decision == "approved",
                {"decision": engineering_approval.decision if engineering_approval else "missing"},
                "engineering_approval_missing",
            ),
        ]

    async def _invite_activation_checks(
        self, candidate: ProductionReleaseCandidateRecord, now: datetime
    ) -> list[GateCheck]:
        acceptance = await self._session.scalar(
            select(ProviderAcceptanceRunRecord)
            .where(ProviderAcceptanceRunRecord.environment == "production")
            .order_by(ProviderAcceptanceRunRecord.created_at.desc())
            .limit(1)
        )
        acceptance_fresh = bool(
            acceptance and acceptance.finished_at >= now - INVITE_EVIDENCE_MAX_AGE
        )
        diagnostic = await self._session.scalar(
            select(ProviderDiagnosticRunRecord)
            .where(
                ProviderDiagnosticRunRecord.provider == "resend",
                ProviderDiagnosticRunRecord.target == "active",
            )
            .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            .limit(1)
        )
        diagnostic_fresh = bool(
            diagnostic and diagnostic.checked_at >= now - INVITE_EVIDENCE_MAX_AGE
        )
        delivery = await self._session.scalar(
            select(TransactionalEmailDeliveryRecord)
            .where(TransactionalEmailDeliveryRecord.status == "delivered")
            .order_by(TransactionalEmailDeliveryRecord.delivered_at.desc())
            .limit(1)
        )
        event = await self._session.scalar(
            select(TransactionalEmailProviderEventRecord)
            .where(
                TransactionalEmailProviderEventRecord.provider == "resend",
                TransactionalEmailProviderEventRecord.status == "processed",
            )
            .order_by(TransactionalEmailProviderEventRecord.received_at.desc())
            .limit(1)
        )
        email_fresh = bool(
            delivery
            and delivery.delivered_at
            and delivery.delivered_at >= now - INVITE_EVIDENCE_MAX_AGE
        )
        webhook_fresh = bool(event and event.received_at >= now - INVITE_EVIDENCE_MAX_AGE)
        email_runtime_ok = False
        email_runtime_source = "unavailable"
        try:
            runtime = await self._providers.runtime("resend")
            configuration = ResendConfiguration.model_validate(runtime.configuration)
            email_runtime_source = runtime.source
            email_runtime_ok = bool(
                configuration.enabled
                and runtime.credentials.get("api_key")
                and runtime.credentials.get("webhook_secret")
            )
        except ValueError:
            pass
        approvals = {
            role: await self._approval(candidate.id, role)
            for role in ("engineering", "data_compliance", "product_operations")
        }
        active_users = int(
            await self._session.scalar(
                select(func.count()).select_from(User).where(User.status == "active")
            )
            or 0
        )
        severe_feedback = int(
            await self._session.scalar(
                select(func.count())
                .select_from(BetaFeedbackItemRecord)
                .where(
                    BetaFeedbackItemRecord.severity.in_(("P0", "P1")),
                    BetaFeedbackItemRecord.status.notin_(("resolved", "closed")),
                )
            )
            or 0
        )
        acceptance_expiry = acceptance.finished_at + INVITE_EVIDENCE_MAX_AGE if acceptance else None
        diagnostic_expiry = diagnostic.checked_at + INVITE_EVIDENCE_MAX_AGE if diagnostic else None
        delivery_expiry = (
            delivery.delivered_at + INVITE_EVIDENCE_MAX_AGE
            if delivery and delivery.delivered_at
            else None
        )
        webhook_expiry = event.received_at + INVITE_EVIDENCE_MAX_AGE if event else None
        return [
            self._check(
                "deployment.observing",
                "deployment",
                candidate.status in {"deployed_observing", "ready_invites"},
                {"status": candidate.status},
                "closed_deployment_not_recorded",
            ),
            self._check(
                "registration.invite_only",
                "access",
                self._settings.registration_mode == "invite_only",
                {"registration_mode": self._settings.registration_mode},
                "registration_not_invite_only",
            ),
            self._check(
                "approval.legal",
                "compliance",
                self._settings.legal_review_status == "approved",
                {"status": self._settings.legal_review_status},
                "legal_review_not_approved",
            ),
            self._check(
                "approval.data_use",
                "compliance",
                self._settings.data_use_status == "approved",
                {"status": self._settings.data_use_status},
                "data_use_not_approved",
            ),
            self._check(
                "provider.acceptance",
                "provider",
                bool(
                    acceptance
                    and acceptance.status == "passed"
                    and acceptance.beta_eligible
                    and acceptance.usage_scope == "production"
                    and acceptance_fresh
                ),
                {
                    "run_id": str(acceptance.id) if acceptance else None,
                    "status": acceptance.status if acceptance else "missing",
                    "usage_scope": acceptance.usage_scope if acceptance else None,
                    "fresh": acceptance_fresh,
                },
                "production_provider_acceptance_unavailable",
                acceptance_expiry,
            ),
            self._check(
                "email.runtime",
                "email",
                email_runtime_ok,
                {"source": email_runtime_source, "enabled": email_runtime_ok},
                "production_resend_runtime_unavailable",
            ),
            self._check(
                "email.diagnostic",
                "email",
                bool(diagnostic and diagnostic.status == "healthy" and diagnostic_fresh),
                {
                    "status": diagnostic.status if diagnostic else "missing",
                    "fresh": diagnostic_fresh,
                },
                "resend_diagnostic_unhealthy",
                diagnostic_expiry,
            ),
            self._check(
                "email.delivered",
                "email",
                email_fresh,
                {"delivery_id": str(delivery.id) if delivery else None, "fresh": email_fresh},
                "recent_delivered_email_missing",
                delivery_expiry,
            ),
            self._check(
                "email.webhook",
                "email",
                webhook_fresh,
                {"event_id": str(event.id) if event else None, "fresh": webhook_fresh},
                "recent_resend_webhook_missing",
                webhook_expiry,
            ),
            self._check(
                "feedback.p0_p1_zero",
                "quality",
                severe_feedback == 0,
                {"open_p0_p1": severe_feedback},
                "open_p0_p1_feedback",
            ),
            self._check(
                "capacity.available",
                "access",
                active_users < self._settings.beta_max_active_users,
                {"active_users": active_users, "capacity": self._settings.beta_max_active_users},
                "beta_capacity_reached",
            ),
            self._check(
                "automation.hard_disabled",
                "automation",
                self._settings.automation_hard_disabled,
                {"hard_disabled": self._settings.automation_hard_disabled},
                "automation_not_hard_disabled",
            ),
            *[
                self._check(
                    f"approval.{role}",
                    "approval",
                    approval is not None and approval.decision == "approved",
                    {"decision": approval.decision if approval else "missing"},
                    f"{role}_approval_missing",
                )
                for role, approval in approvals.items()
            ],
        ]

    @staticmethod
    def _check(
        key: str,
        category: str,
        passed: bool,
        evidence: dict[str, object],
        reason_code: str | None,
        expires_at: datetime | None = None,
    ) -> GateCheck:
        return GateCheck(
            key=key,
            category=category,
            passed=passed,
            reason_code=None if passed else reason_code,
            evidence=evidence,
            expires_at=expires_at,
        )

    async def _approval(
        self, candidate_id: UUID, role: str
    ) -> ProductionReleaseApprovalRecord | None:
        result = await self._session.scalar(
            select(ProductionReleaseApprovalRecord).where(
                ProductionReleaseApprovalRecord.candidate_id == candidate_id,
                ProductionReleaseApprovalRecord.approval_role == role,
            )
        )
        return result

    async def _view(self, row: ProductionReleaseCandidateRecord) -> ProductionReleaseCandidate:
        approvals = list(
            (
                await self._session.scalars(
                    select(ProductionReleaseApprovalRecord)
                    .where(ProductionReleaseApprovalRecord.candidate_id == row.id)
                    .order_by(ProductionReleaseApprovalRecord.created_at)
                )
            ).all()
        )
        events = list(
            (
                await self._session.scalars(
                    select(ProductionDeploymentEventRecord)
                    .where(ProductionDeploymentEventRecord.candidate_id == row.id)
                    .order_by(ProductionDeploymentEventRecord.created_at)
                )
            ).all()
        )
        runs = list(
            (
                await self._session.scalars(
                    select(ProductionReleaseGateRunRecord)
                    .where(ProductionReleaseGateRunRecord.candidate_id == row.id)
                    .order_by(ProductionReleaseGateRunRecord.started_at.desc())
                )
            ).all()
        )
        latest: dict[str, ProductionReleaseGateRunRecord] = {}
        for run in runs:
            latest.setdefault(run.gate_type, run)
        return ProductionReleaseCandidate(
            id=row.id,
            target_environment="production",
            status=cast(ReleaseStatus, row.status),
            commit_sha=row.commit_sha,
            migration_head=row.migration_head,
            api_image_digest=row.api_image_digest,
            web_image_digest=row.web_image_digest,
            configuration_fingerprint=row.configuration_fingerprint,
            sbom_sha256=row.sbom_sha256,
            backup_sha256=row.backup_sha256,
            restore_verified_at=row.restore_verified_at,
            quality_gate_status=cast(ArtifactStatus, row.quality_gate_status),
            e2e_status=cast(ArtifactStatus, row.e2e_status),
            security_scan_status=cast(ArtifactStatus, row.security_scan_status),
            created_by_user_id=row.created_by_user_id,
            created_at=row.created_at,
            approvals=[
                ProductionReleaseApproval(
                    id=item.id,
                    approval_role=cast(ApprovalRole, item.approval_role),
                    decision=cast(ApprovalDecision, item.decision),
                    actor_user_id=item.actor_user_id,
                    note=item.note,
                    created_at=item.created_at,
                )
                for item in approvals
            ],
            latest_gates=[await self._gate_view(item) for item in latest.values()],
            deployment_events=[
                ProductionDeploymentEvent(
                    id=item.id,
                    event_type=cast(DeploymentEventType, item.event_type),
                    deployment_ref=item.deployment_ref,
                    reason_code=item.reason_code,
                    recorded_by_user_id=item.recorded_by_user_id,
                    created_at=item.created_at,
                )
                for item in events
            ],
        )

    async def _gate_view(self, run: ProductionReleaseGateRunRecord) -> ProductionReleaseGateRun:
        items = list(
            (
                await self._session.scalars(
                    select(ProductionReleaseGateItemRecord)
                    .where(ProductionReleaseGateItemRecord.run_id == run.id)
                    .order_by(ProductionReleaseGateItemRecord.check_key)
                )
            ).all()
        )
        return ProductionReleaseGateRun(
            id=run.id,
            gate_type=cast(GateType, run.gate_type),
            status=cast(GateStatus, run.status),
            rule_set_version=run.rule_set_version,
            result_fingerprint=run.result_fingerprint,
            started_at=run.started_at,
            finished_at=run.finished_at,
            items=[
                ProductionReleaseGateItem(
                    check_key=item.check_key,
                    category=item.category,
                    mandatory=item.mandatory,
                    status=cast(GateItemStatus, item.status),
                    reason_code=item.reason_code,
                    evidence=item.evidence_json,
                    evidence_fingerprint=item.evidence_fingerprint,
                    checked_at=item.checked_at,
                    expires_at=item.expires_at,
                )
                for item in items
            ],
        )
