from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Literal, cast
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.service import AccessControlService
from zhaoniu_api.ai_research.litellm_gateway import LiteLLMGateway
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    AccessActivationCodeRecord,
    BetaFeedbackItemRecord,
    CoverageBackfillRunRecord,
    LLMCallRecord,
    OperatorAuditEventRecord,
    OperatorMembershipRecord,
    ProviderDiagnosticRunRecord,
    RegistrationInviteRecord,
    ResearchCoverageMemberRecord,
    ResearchCoverageSnapshotRecord,
    SavedScreenRecord,
    SubscriptionRecord,
    TransactionalEmailDeliveryRecord,
    User,
    UserSessionRecord,
    WatchlistRecord,
)
from zhaoniu_api.operations import evaluate_beta_readiness
from zhaoniu_api.operations_console.models import (
    OperatorAccessCodeResponse,
    OperatorAuditItem,
    OperatorContext,
    OperatorDashboardResponse,
    OperatorFeedbackItem,
    OperatorInviteBatchResponse,
    OperatorRole,
    OperatorUserDetail,
    OperatorUserSummary,
    ProviderStatusView,
)
from zhaoniu_api.ports.providers import LLMGatewayError
from zhaoniu_api.system import MIGRATION_HEAD

CAPABILITIES: dict[str, frozenset[str]] = {
    "viewer": frozenset({"dashboard.read", "coverage.read", "providers.read", "audit.read"}),
    "support": frozenset(
        {
            "dashboard.read",
            "users.read",
            "users.sessions.revoke",
            "users.verification.resend",
            "invites.manage",
            "access_codes.manage",
            "feedback.manage",
            "providers.read",
            "audit.read",
        }
    ),
    "operations": frozenset(
        {
            "dashboard.read",
            "coverage.read",
            "coverage.run",
            "ai.read",
            "ai.run",
            "feedback.manage",
            "providers.read",
            "providers.diagnose",
            "audit.read",
        }
    ),
    "security_admin": frozenset(
        {
            "dashboard.read",
            "users.read",
            "users.status.manage",
            "users.sessions.revoke",
            "users.verification.resend",
            "invites.manage",
            "access_codes.manage",
            "feedback.manage",
            "coverage.read",
            "coverage.run",
            "ai.read",
            "ai.run",
            "providers.read",
            "providers.diagnose",
            "audit.read",
        }
    ),
}


class OperatorAuthorizationError(PermissionError):
    pass


class OperatorService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._access = AccessControlService(session, settings)

    async def context(
        self, user_id: UUID, elevated_until: datetime | None = None
    ) -> OperatorContext | None:
        membership = await self._session.scalar(
            select(OperatorMembershipRecord).where(
                OperatorMembershipRecord.user_id == user_id,
                OperatorMembershipRecord.revoked_at.is_(None),
            )
        )
        if membership is None:
            return None
        role = cast(OperatorRole, membership.role)
        elevated = bool(elevated_until and elevated_until > datetime.now(UTC))
        return OperatorContext(
            role=role,
            capabilities=sorted(CAPABILITIES[role]),
            elevated_until=elevated_until,
            elevated=elevated,
        )

    @staticmethod
    def require(context: OperatorContext, capability: str, *, elevated: bool = False) -> None:
        if capability not in context.capabilities:
            raise OperatorAuthorizationError("operator_capability_required")
        if elevated and not context.elevated:
            raise OperatorAuthorizationError("operator_step_up_required")

    async def grant_operator(
        self,
        email: str,
        role: OperatorRole,
        *,
        created_by_user_id: UUID | None = None,
    ) -> OperatorMembershipRecord:
        user = await self._session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise LookupError("user_not_found")
        existing = await self._session.scalar(
            select(OperatorMembershipRecord).where(
                OperatorMembershipRecord.user_id == user.id,
                OperatorMembershipRecord.revoked_at.is_(None),
            )
        )
        if existing is not None and existing.role == role:
            return existing
        now = datetime.now(UTC)
        if existing is not None:
            existing.revoked_at = now
        membership = OperatorMembershipRecord(
            id=uuid4(),
            user_id=user.id,
            role=role,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(membership)
        await self._session.commit()
        return membership

    async def revoke_operator(self, email: str) -> bool:
        user_id = await self._session.scalar(
            select(User.id).where(User.email == email.strip().lower())
        )
        if user_id is None:
            return False
        now = datetime.now(UTC)
        membership = await self._session.scalar(
            select(OperatorMembershipRecord).where(
                OperatorMembershipRecord.user_id == user_id,
                OperatorMembershipRecord.revoked_at.is_(None),
            )
        )
        if membership is None:
            return False
        membership.revoked_at = now
        await self._session.execute(
            update(UserSessionRecord)
            .where(UserSessionRecord.user_id == user_id)
            .values(operator_elevated_until=None)
        )
        await self._session.commit()
        return True

    async def list_operators(self) -> list[tuple[OperatorMembershipRecord, str]]:
        rows = (
            await self._session.execute(
                select(OperatorMembershipRecord, User.email)
                .join(User, User.id == OperatorMembershipRecord.user_id)
                .where(OperatorMembershipRecord.revoked_at.is_(None))
                .order_by(OperatorMembershipRecord.created_at)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def audit(
        self,
        actor_user_id: UUID,
        context: OperatorContext,
        action_key: str,
        target_type: str,
        target_id: str | None,
        *,
        result: Literal["succeeded", "denied", "failed"] = "succeeded",
        reason_code: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            OperatorAuditEventRecord(
                id=uuid4(),
                actor_user_id=actor_user_id,
                actor_role=context.role,
                action_key=action_key,
                target_type=target_type,
                target_id=target_id,
                request_id=request_id,
                result=result,
                reason_code=reason_code,
                metadata_json=metadata or {},
            )
        )
        await self._session.commit()

    async def dashboard(self) -> OperatorDashboardResponse:
        now = datetime.now(UTC)
        since = now - timedelta(hours=24)
        users_total = int(await self._session.scalar(select(func.count()).select_from(User)) or 0)
        users_active = int(
            await self._session.scalar(
                select(func.count()).select_from(User).where(User.status == "active")
            )
            or 0
        )
        users_verified = int(
            await self._session.scalar(
                select(func.count()).select_from(User).where(User.email_verified_at.is_not(None))
            )
            or 0
        )
        advanced = int(
            await self._session.scalar(
                select(func.count())
                .select_from(SubscriptionRecord)
                .where(
                    SubscriptionRecord.status == "active",
                    SubscriptionRecord.revoked_at.is_(None),
                    SubscriptionRecord.current_period_end > now,
                )
            )
            or 0
        )
        invite_available = int(
            await self._session.scalar(
                select(func.count())
                .select_from(RegistrationInviteRecord)
                .where(
                    RegistrationInviteRecord.consumed_at.is_(None),
                    RegistrationInviteRecord.revoked_at.is_(None),
                    RegistrationInviteRecord.expires_at > now,
                )
            )
            or 0
        )
        activation_available = int(
            await self._session.scalar(
                select(func.count())
                .select_from(AccessActivationCodeRecord)
                .where(
                    AccessActivationCodeRecord.redeemed_at.is_(None),
                    AccessActivationCodeRecord.revoked_at.is_(None),
                    AccessActivationCodeRecord.expires_at > now,
                )
            )
            or 0
        )
        llm_calls = int(
            await self._session.scalar(
                select(func.count())
                .select_from(LLMCallRecord)
                .where(LLMCallRecord.created_at >= since)
            )
            or 0
        )
        llm_failures = int(
            await self._session.scalar(
                select(func.count())
                .select_from(LLMCallRecord)
                .where(LLMCallRecord.created_at >= since, LLMCallRecord.status != "succeeded")
            )
            or 0
        )
        email_submitted = int(
            await self._session.scalar(
                select(func.count())
                .select_from(TransactionalEmailDeliveryRecord)
                .where(
                    TransactionalEmailDeliveryRecord.created_at >= since,
                    TransactionalEmailDeliveryRecord.status.in_(("sent", "submitted", "delivered")),
                )
            )
            or 0
        )
        email_failures = int(
            await self._session.scalar(
                select(func.count())
                .select_from(TransactionalEmailDeliveryRecord)
                .where(
                    TransactionalEmailDeliveryRecord.created_at >= since,
                    TransactionalEmailDeliveryRecord.status.in_(
                        ("failed", "bounced", "suppressed", "complained")
                    ),
                )
            )
            or 0
        )
        latest_coverage = await self._session.scalar(
            select(ResearchCoverageSnapshotRecord).order_by(
                ResearchCoverageSnapshotRecord.evaluated_at.desc()
            )
        )
        coverage_members = 0
        if latest_coverage is not None:
            coverage_members = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(ResearchCoverageMemberRecord)
                    .where(ResearchCoverageMemberRecord.snapshot_id == latest_coverage.id)
                )
                or 0
            )
        latest_backfill = await self._session.scalar(
            select(CoverageBackfillRunRecord).order_by(CoverageBackfillRunRecord.created_at.desc())
        )
        readiness = await evaluate_beta_readiness(self._session, self._settings)
        return OperatorDashboardResponse(
            generated_at=now,
            environment=self._settings.app_env,
            users={"total": users_total, "active": users_active, "verified": users_verified},
            access={
                "advanced_active": advanced,
                "invites_available": invite_available,
                "activation_codes_available": activation_available,
            },
            ai={
                "enabled": str(self._settings.llm_enabled).lower(),
                "calls_24h": llm_calls,
                "failures_24h": llm_failures,
            },
            email={
                "provider": self._settings.email_delivery_mode,
                "configured": self._settings.email_delivery_mode != "disabled",
                "submitted_24h": email_submitted,
                "failures_24h": email_failures,
            },
            coverage={
                "snapshot_id": str(latest_coverage.id) if latest_coverage else None,
                "universe_size": coverage_members,
                "latest_backfill_status": latest_backfill.status if latest_backfill else None,
                "latest_backfill_failed": latest_backfill.failed_items if latest_backfill else 0,
            },
            system={
                "migration_head": MIGRATION_HEAD,
                "beta_readiness": readiness.status,
                "active_users": readiness.active_users,
                "blocking_reasons": readiness.blocking_reasons,
                "data_use_status": self._settings.data_use_status,
                "legal_review_status": self._settings.legal_review_status,
            },
        )

    async def list_users(self, query: str, limit: int) -> list[OperatorUserSummary]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        statement = select(User).order_by(User.created_at.desc()).limit(limit)
        try:
            user_id = UUID(normalized)
        except ValueError:
            statement = statement.where(User.email == normalized)
        else:
            statement = statement.where(User.id == user_id)
        rows = (await self._session.scalars(statement)).all()
        return [await self._user_summary(row) for row in rows]

    async def user_detail(self, user_id: UUID) -> OperatorUserDetail | None:
        user = await self._session.get(User, user_id)
        if user is None:
            return None
        summary = await self._user_summary(user)
        now = datetime.now(UTC)
        active_sessions = int(
            await self._session.scalar(
                select(func.count())
                .select_from(UserSessionRecord)
                .where(
                    UserSessionRecord.user_id == user_id,
                    UserSessionRecord.revoked_at.is_(None),
                    UserSessionRecord.expires_at > now,
                )
            )
            or 0
        )
        watchlists = int(
            await self._session.scalar(
                select(func.count())
                .select_from(WatchlistRecord)
                .where(WatchlistRecord.user_id == user_id)
            )
            or 0
        )
        saved = int(
            await self._session.scalar(
                select(func.count())
                .select_from(SavedScreenRecord)
                .where(SavedScreenRecord.user_id == user_id)
            )
            or 0
        )
        return OperatorUserDetail(
            **summary.model_dump(),
            active_sessions=active_sessions,
            watchlist_count=watchlists,
            saved_screen_count=saved,
        )

    async def set_user_status(self, user_id: UUID, status: Literal["active", "disabled"]) -> bool:
        user = await self._session.get(User, user_id)
        if user is None:
            return False
        user.status = status
        if status == "disabled":
            await self._session.execute(
                update(UserSessionRecord)
                .where(UserSessionRecord.user_id == user_id, UserSessionRecord.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC), operator_elevated_until=None)
            )
        await self._session.commit()
        return True

    async def revoke_sessions(self, user_id: UUID) -> int:
        result = await self._session.execute(
            update(UserSessionRecord)
            .where(UserSessionRecord.user_id == user_id, UserSessionRecord.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), operator_elevated_until=None)
        )
        await self._session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def generate_invites(
        self, *, count: int, expires_in_days: int, name: str | None, actor: UUID
    ) -> OperatorInviteBatchResponse:
        result = await self._access.generate_registration_invites(
            count=count,
            expires_in_days=expires_in_days,
            operator=str(actor),
            name=name,
        )
        return OperatorInviteBatchResponse(
            batch_id=result.batch_id, codes=result.codes, expires_at=result.expires_at
        )

    async def issue_access_code(
        self,
        user_id: UUID,
        *,
        term: Literal["month", "year"],
        expires_in_days: int,
        actor: UUID,
    ) -> OperatorAccessCodeResponse:
        user = await self._session.get(User, user_id)
        if user is None:
            raise LookupError("user_not_found")
        result = await self._access.issue_access_code(
            user_email=user.email,
            term_kind=term,
            expires_in_days=expires_in_days,
            operator=str(actor),
        )
        return OperatorAccessCodeResponse(
            batch_id=result.batch_id,
            assigned_user_id=result.assigned_user_id,
            code=result.code,
            expires_at=result.expires_at,
        )

    async def list_feedback(self, status: str | None, limit: int) -> list[OperatorFeedbackItem]:
        statement = select(BetaFeedbackItemRecord).order_by(
            BetaFeedbackItemRecord.created_at.desc()
        )
        if status:
            statement = statement.where(BetaFeedbackItemRecord.status == status)
        rows = (await self._session.scalars(statement.limit(limit))).all()
        return [OperatorFeedbackItem.model_validate(row) for row in rows]

    async def update_feedback(self, feedback_id: UUID, status: str) -> bool:
        row = await self._session.get(BetaFeedbackItemRecord, feedback_id)
        if row is None:
            return False
        if status == "resolved" and row.status == "new":
            raise ValueError("feedback_must_be_triaged_first")
        row.status = status
        await self._session.commit()
        return True

    async def list_audit(self, limit: int) -> list[OperatorAuditItem]:
        rows = (
            await self._session.scalars(
                select(OperatorAuditEventRecord)
                .order_by(OperatorAuditEventRecord.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            OperatorAuditItem(
                id=row.id,
                actor_user_id=row.actor_user_id,
                actor_role=row.actor_role,
                action_key=row.action_key,
                target_type=row.target_type,
                target_id=row.target_id,
                result=row.result,
                reason_code=row.reason_code,
                metadata=row.metadata_json,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def provider_statuses(self) -> list[ProviderStatusView]:
        configured = {
            "deepseek": self._settings.llm_enabled
            and any(item.startswith("deepseek/") for item in self._settings.llm_models),
            "resend": self._settings.email_delivery_mode == "resend",
            "market_data": True,
            "disclosure": True,
        }
        capabilities = {
            "deepseek": "structured_generation",
            "resend": "transactional_email",
            "market_data": "collection",
            "disclosure": "collection",
        }
        output: list[ProviderStatusView] = []
        for provider, is_configured in configured.items():
            latest = await self._session.scalar(
                select(ProviderDiagnosticRunRecord)
                .where(ProviderDiagnosticRunRecord.provider == provider)
                .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            )
            latest_status = cast(
                Literal["disabled", "unknown", "healthy", "degraded", "unavailable"],
                (latest.status if latest else "unknown") if is_configured else "disabled",
            )
            output.append(
                ProviderStatusView(
                    provider=provider,
                    capability=capabilities[provider],
                    status=latest_status,
                    configured=is_configured,
                    checked_at=latest.checked_at if latest else None,
                    latency_ms=latest.latency_ms if latest else None,
                    reason_code=latest.reason_code if latest else None,
                )
            )
        return output

    async def diagnose_provider(self, provider: str, actor: UUID) -> ProviderStatusView:
        started = perf_counter()
        status: Literal["disabled", "unknown", "healthy", "degraded", "unavailable"]
        reason: str | None = None
        configured = False
        capability = "unknown"
        if provider == "deepseek":
            capability = "structured_generation"
            model = next(
                (item for item in self._settings.llm_models if item.startswith("deepseek/")),
                None,
            )
            configured = bool(self._settings.llm_enabled and model)
            if not configured or model is None:
                status = "disabled"
            else:
                try:
                    gateway = LiteLLMGateway(
                        self._settings.llm_structured_output_mode,
                        redis_url=self._settings.redis_url,
                        max_concurrency=self._settings.llm_provider_max_concurrency,
                        daily_call_limit=self._settings.llm_provider_daily_call_limit,
                    )
                    await gateway.generate_structured(
                        model=model,
                        task_type="provider_diagnostic",
                        system_prompt=(
                            "Return a JSON object that confirms structured output availability."
                        ),
                        input_data={"probe": "zhaoniu-provider-diagnostic"},
                        response_schema={
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                            "required": ["ok"],
                            "additionalProperties": False,
                        },
                        timeout_seconds=min(self._settings.llm_per_model_timeout_seconds, 30),
                    )
                    status = "healthy"
                except LLMGatewayError as error:
                    status = "unavailable"
                    reason = error.code
        elif provider == "resend":
            capability = "transactional_email"
            configured = self._settings.email_delivery_mode == "resend"
            if not configured:
                status = "disabled"
            else:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(
                            "https://api.resend.com/domains",
                            headers={"Authorization": f"Bearer {self._settings.resend_api_key}"},
                        )
                    if response.status_code >= 400:
                        status = "unavailable"
                        reason = (
                            "provider_auth"
                            if response.status_code in {401, 403}
                            else "provider_unavailable"
                        )
                    else:
                        domains = response.json().get("data", [])
                        target = next(
                            (
                                item
                                for item in domains
                                if item.get("name") == self._settings.resend_sending_domain
                            ),
                            None,
                        )
                        status = (
                            "healthy"
                            if target and target.get("status") == "verified"
                            else "degraded"
                        )
                        reason = None if status == "healthy" else "sending_domain_not_verified"
                except (httpx.HTTPError, ValueError):
                    status = "unavailable"
                    reason = "provider_unavailable"
        else:
            raise ValueError("provider_diagnostic_unsupported")

        checked_at = datetime.now(UTC)
        latency_ms = int((perf_counter() - started) * 1000)
        row = ProviderDiagnosticRunRecord(
            id=uuid4(),
            provider=provider,
            capability=capability,
            status=status,
            latency_ms=latency_ms,
            reason_code=reason,
            checked_at=checked_at,
            requested_by_user_id=actor,
        )
        self._session.add(row)
        await self._session.commit()
        return ProviderStatusView(
            provider=provider,
            capability=capability,
            status=status,
            configured=configured,
            checked_at=checked_at,
            latency_ms=latency_ms,
            reason_code=reason,
        )

    async def _user_summary(self, user: User) -> OperatorUserSummary:
        entitlements = await self._access.effective_entitlements(user.id)
        return OperatorUserSummary(
            id=user.id,
            email=user.email,
            status=user.status,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            access_status=entitlements.access_status,
            access_valid_until=entitlements.valid_until,
        )
