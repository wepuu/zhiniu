from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from urllib.parse import quote
from uuid import UUID, uuid4

from celery import Celery  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.codes import code_hmac, code_prefix, generate_code
from zhaoniu_api.auth.email import TransactionalEmail
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    BetaFeedbackItemRecord,
    BetaInviteCohortRecord,
    BetaInviteRecipientRecord,
    BetaOnboardingStateRecord,
    ProviderAcceptanceRunRecord,
    ProviderDiagnosticRunRecord,
    RegistrationInviteBatchRecord,
    RegistrationInviteRecord,
    TransactionalEmailDeliveryRecord,
    User,
    WatchlistItemRecord,
    WatchlistRecord,
)
from zhaoniu_api.invite_beta.models import (
    BetaCohortView,
    BetaOnboardingView,
    BetaRecipientView,
    ProgramKind,
    UsageScope,
)
from zhaoniu_api.invite_beta.security import recipient_email_hmac, validate_recipient_email
from zhaoniu_api.provider_configuration.models import ResendConfiguration
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService
from zhaoniu_api.stock_readiness import StockReadinessService

ONBOARDING_SCHEMA_VERSION = "private-evaluation-onboarding-v2"
ACTIVE_RECIPIENT_STATUSES = {"staged", "queued", "registered"}
PRIVATE_EVALUATION_NOTICE_VERSION = "private-evaluation-v1"
CONTROLLED_BETA_NOTICE_VERSION = "controlled-beta-v1"


class InviteBetaError(ValueError):
    pass


def program_gate_reasons(
    settings: Settings,
    program_kind: ProgramKind,
    acceptance: ProviderAcceptanceRunRecord | None,
    *,
    now: datetime,
) -> list[str]:
    reasons: list[str] = []
    if program_kind == "controlled_beta":
        if acceptance is None:
            reasons.append("provider_acceptance_missing")
        else:
            if acceptance.status != "passed":
                reasons.append("provider_acceptance_failed")
            if not acceptance.beta_eligible:
                reasons.append("provider_data_policy_not_beta_eligible")
            if acceptance.finished_at < now - timedelta(
                hours=settings.provider_acceptance_max_age_hours
            ):
                reasons.append("provider_acceptance_stale")
        if settings.coverage_usage_scope != "production":
            reasons.append("controlled_beta_usage_scope_mismatch")
    else:
        if settings.coverage_usage_scope != "development_evaluation":
            reasons.append("private_evaluation_usage_scope_mismatch")
        if settings.automation_hard_disabled:
            reasons.append("automation_hard_disabled")
        if not settings.watchlist_preparation_enabled:
            reasons.append("watchlist_preparation_disabled")
    return reasons


class InviteBetaService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def create_cohort(
        self,
        *,
        name: str,
        program_kind: ProgramKind,
        target_size: int,
        expires_in_days: int,
        actor_user_id: UUID,
    ) -> BetaCohortView:
        now = datetime.now(UTC)
        if program_kind == "private_evaluation" and target_size > 10:
            raise InviteBetaError("private_evaluation_target_exceeded")
        acceptance = await self._latest_acceptance() if program_kind == "controlled_beta" else None
        record = BetaInviteCohortRecord(
            id=uuid4(),
            name=name.strip(),
            program_kind=program_kind,
            usage_scope=(
                "development_evaluation" if program_kind == "private_evaluation" else "production"
            ),
            notice_version=(
                PRIVATE_EVALUATION_NOTICE_VERSION
                if program_kind == "private_evaluation"
                else CONTROLLED_BETA_NOTICE_VERSION
            ),
            status="draft",
            target_size=target_size,
            expires_at=now + timedelta(days=expires_in_days),
            acceptance_run_id=acceptance.id if acceptance else None,
            created_by_user_id=actor_user_id,
        )
        self._session.add(record)
        await self._session.commit()
        return await self.get_cohort(record.id)

    async def add_recipients(self, cohort_id: UUID, emails: list[str]) -> BetaCohortView:
        cohort = await self._locked_cohort(cohort_id)
        if cohort.status != "draft":
            raise InviteBetaError("beta_cohort_not_draft")
        current = int(
            await self._session.scalar(
                select(func.count(BetaInviteRecipientRecord.id)).where(
                    BetaInviteRecipientRecord.cohort_id == cohort.id,
                    BetaInviteRecipientRecord.status != "withdrawn",
                )
            )
            or 0
        )
        normalized = [validate_recipient_email(email) for email in emails]
        if len(set(normalized)) != len(normalized):
            raise InviteBetaError("duplicate_recipient_email")
        if current + len(normalized) > cohort.target_size:
            raise InviteBetaError("beta_cohort_target_exceeded")
        for email in normalized:
            digest = recipient_email_hmac(email, self._settings.registration_invite_hmac_secret)
            duplicate = await self._session.scalar(
                select(BetaInviteRecipientRecord.id).where(
                    BetaInviteRecipientRecord.email_hmac == digest,
                    BetaInviteRecipientRecord.status.in_(ACTIVE_RECIPIENT_STATUSES),
                )
            )
            existing_user = await self._session.scalar(select(User.id).where(User.email == email))
            if duplicate is not None:
                raise InviteBetaError("recipient_already_invited")
            if existing_user is not None:
                raise InviteBetaError("recipient_already_registered")
            self._session.add(
                BetaInviteRecipientRecord(
                    id=uuid4(),
                    cohort_id=cohort.id,
                    normalized_email=email,
                    email_hmac=digest,
                    status="staged",
                )
            )
        await self._session.commit()
        return await self.get_cohort(cohort.id)

    async def approve(self, cohort_id: UUID, actor_user_id: UUID) -> BetaCohortView:
        cohort = await self._locked_cohort(cohort_id)
        if cohort.status != "draft":
            raise InviteBetaError("beta_cohort_not_draft")
        recipient_count = int(
            await self._session.scalar(
                select(func.count(BetaInviteRecipientRecord.id)).where(
                    BetaInviteRecipientRecord.cohort_id == cohort.id,
                    BetaInviteRecipientRecord.status == "staged",
                )
            )
            or 0
        )
        if recipient_count == 0:
            raise InviteBetaError("beta_cohort_has_no_recipients")
        reasons = await self.gate_reasons(cast(ProgramKind, cohort.program_kind))
        if reasons:
            cohort.reason_code = reasons[0]
            await self._session.commit()
            raise InviteBetaError(reasons[0])
        if cohort.program_kind == "controlled_beta":
            acceptance = await self._latest_acceptance()
            assert acceptance is not None
            cohort.acceptance_run_id = acceptance.id
        cohort.status = "approved"
        cohort.reason_code = None
        cohort.approved_by_user_id = actor_user_id
        cohort.approved_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_cohort(cohort.id)

    async def dispatch(self, cohort_id: UUID) -> BetaCohortView:
        cohort = await self._locked_cohort(cohort_id)
        if cohort.status != "approved":
            raise InviteBetaError("beta_cohort_not_approved")
        reasons = await self.gate_reasons(cast(ProgramKind, cohort.program_kind))
        if reasons:
            cohort.reason_code = reasons[0]
            await self._session.commit()
            raise InviteBetaError(reasons[0])
        recipients = list(
            await self._session.scalars(
                select(BetaInviteRecipientRecord).where(
                    BetaInviteRecipientRecord.cohort_id == cohort.id,
                    BetaInviteRecipientRecord.status == "staged",
                )
            )
        )
        if not recipients:
            raise InviteBetaError("beta_cohort_has_no_staged_recipients")
        now = datetime.now(UTC)
        batch = RegistrationInviteBatchRecord(
            id=uuid4(),
            name=f"{cohort.program_kind} cohort {cohort.name}",
            quantity=len(recipients),
            expires_at=cohort.expires_at,
            created_by_operator=str(cohort.created_by_user_id),
        )
        self._session.add(batch)
        cohort.invite_batch_id = batch.id
        cohort.status = "dispatching"
        messages: list[tuple[TransactionalEmailDeliveryRecord, TransactionalEmail]] = []
        for recipient in recipients:
            code = generate_code("INV")
            invite = RegistrationInviteRecord(
                id=uuid4(),
                batch_id=batch.id,
                code_hmac=code_hmac(code, "INV", self._settings.registration_invite_hmac_secret),
                code_prefix=code_prefix(code),
                expires_at=cohort.expires_at,
            )
            delivery = TransactionalEmailDeliveryRecord(
                id=uuid4(),
                user_id=None,
                template_key="beta_invitation",
                template_version="v1",
                provider="resend",
                logical_delivery_key=f"beta_invitation/{recipient.id}",
                status="pending",
            )
            self._session.add_all([invite, delivery])
            recipient.invite_id = invite.id
            recipient.delivery_id = delivery.id
            recipient.status = "queued"
            recipient.attempt_count += 1
            recipient.queued_at = now
            link = (
                f"{self._settings.public_base_url.rstrip('/')}/register"
                f"?invite={quote(code)}&email={quote(recipient.normalized_email)}"
            )
            private_evaluation = cohort.program_kind == "private_evaluation"
            invitation_intro = (
                "你受邀参加知牛研究的小范围、非商用私有评估。\n\n"
                if private_evaluation
                else "你受邀参加知牛研究受控 Beta。\n\n"
            )
            registration_line = (
                f"请在 {cohort.expires_at:%Y-%m-%d} 前使用一次性链接注册：\n{link}\n\n"
            )
            scope_notice = (
                "评估环境继续使用公开免费数据源，数据可能延迟、不完整，"
                if private_evaluation
                else "受控 Beta 仅使用已通过准入门禁的生产数据范围，"
            )
            email_body = (
                invitation_intro
                + registration_line
                + ("知牛是证据驱动的 A 股研究工具，不提供买卖建议、目标价或收益预测。")
                + scope_notice
                + (
                    "部分研究会显示为 partial 或 unsupported，"
                    "请以页面证据与限制说明为准。\n\n"
                    "如果你没有申请体验，请忽略本邮件。"
                )
            )
            messages.append(
                (
                    delivery,
                    TransactionalEmail(
                        recipient=recipient.normalized_email,
                        subject=(
                            "知牛研究私有评估邀请"
                            if private_evaluation
                            else "知牛研究受控 Beta 邀请"
                        ),
                        text_body=email_body,
                        template_key="beta_invitation",
                        idempotency_key=delivery.logical_delivery_key,
                    ),
                )
            )
        await self._session.commit()

        dispatcher = Celery(
            "zhaoniu-beta-invite-dispatch",
            broker=self._settings.celery_broker_url,
            backend=self._settings.celery_result_backend,
        )
        dispatch_failed = False
        for delivery, message in messages:
            try:
                dispatcher.send_task(
                    "transactional_email.deliver", args=[str(delivery.id), asdict(message)]
                )
            except Exception:
                dispatch_failed = True
                delivery.status = "failed"
                delivery.error_code = "email_dispatch_unavailable"
                failed_recipient = await self._session.scalar(
                    select(BetaInviteRecipientRecord).where(
                        BetaInviteRecipientRecord.delivery_id == delivery.id
                    )
                )
                if failed_recipient:
                    failed_recipient.status = "failed"
                    failed_recipient.last_error_code = "email_dispatch_unavailable"
        cohort.status = "paused" if dispatch_failed else "active"
        cohort.reason_code = "email_dispatch_unavailable" if dispatch_failed else None
        cohort.dispatched_at = now
        cohort.paused_at = now if dispatch_failed else None
        await self._session.commit()
        return await self.get_cohort(cohort.id)

    async def pause(self, cohort_id: UUID, reason_code: str) -> BetaCohortView:
        cohort = await self._locked_cohort(cohort_id)
        if cohort.status in {"closed", "cancelled"}:
            raise InviteBetaError("beta_cohort_terminal")
        cohort.status = "paused"
        cohort.reason_code = reason_code[:120]
        cohort.paused_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_cohort(cohort.id)

    async def close(self, cohort_id: UUID) -> BetaCohortView:
        cohort = await self._locked_cohort(cohort_id)
        now = datetime.now(UTC)
        recipients = list(
            await self._session.scalars(
                select(BetaInviteRecipientRecord).where(
                    BetaInviteRecipientRecord.cohort_id == cohort.id,
                    BetaInviteRecipientRecord.status.in_({"staged", "queued", "failed"}),
                )
            )
        )
        for recipient in recipients:
            recipient.status = "withdrawn"
            recipient.withdrawn_at = now
            if recipient.invite_id:
                invite = await self._session.get(RegistrationInviteRecord, recipient.invite_id)
                if invite and invite.consumed_at is None:
                    invite.revoked_at = now
        cohort.status = "closed"
        cohort.closed_at = now
        await self._session.commit()
        return await self.get_cohort(cohort.id)

    async def gate_reasons(self, program_kind: ProgramKind = "controlled_beta") -> list[str]:
        now = datetime.now(UTC)
        acceptance = await self._latest_acceptance() if program_kind == "controlled_beta" else None
        reasons = program_gate_reasons(
            self._settings,
            program_kind,
            acceptance,
            now=now,
        )
        if self._settings.registration_mode != "invite_only":
            reasons.append("registration_not_invite_only")
        if self._settings.legal_review_status != "approved":
            reasons.append("legal_review_not_approved")
        if self._settings.data_use_status != "approved":
            reasons.append("data_use_not_approved")
        if self._settings.email_delivery_mode == "disabled":
            reasons.append("transactional_email_disabled")
        runtime = await ProviderConfigurationService(self._session, self._settings).runtime(
            "resend"
        )
        resend = ResendConfiguration.model_validate(runtime.configuration)
        if not resend.enabled or not runtime.credentials.get("api_key"):
            reasons.append("resend_active_configuration_unavailable")
        diagnostic = await self._session.scalar(
            select(ProviderDiagnosticRunRecord)
            .where(
                ProviderDiagnosticRunRecord.provider == "resend",
                ProviderDiagnosticRunRecord.target == "active",
            )
            .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            .limit(1)
        )
        if diagnostic is None or diagnostic.status != "healthy":
            reasons.append("resend_active_diagnostic_unhealthy")
        active_users = int(
            await self._session.scalar(select(func.count(User.id)).where(User.status == "active"))
            or 0
        )
        if active_users >= self._settings.beta_max_active_users:
            reasons.append("beta_capacity_reached")
        return list(dict.fromkeys(reasons))

    async def list_cohorts(self, limit: int = 30) -> list[BetaCohortView]:
        records = list(
            await self._session.scalars(
                select(BetaInviteCohortRecord)
                .order_by(BetaInviteCohortRecord.created_at.desc())
                .limit(limit)
            )
        )
        return [await self._view(record, include_recipients=False) for record in records]

    async def get_cohort(self, cohort_id: UUID) -> BetaCohortView:
        record = await self._session.get(BetaInviteCohortRecord, cohort_id)
        if record is None:
            raise LookupError("beta_cohort_not_found")
        return await self._view(record, include_recipients=True)

    async def onboarding(self, user_id: UUID) -> BetaOnboardingView:
        recipient = await self._session.scalar(
            select(BetaInviteRecipientRecord).where(BetaInviteRecipientRecord.user_id == user_id)
        )
        if recipient is None:
            return BetaOnboardingView(enrolled=False)
        cohort = await self._session.get(BetaInviteCohortRecord, recipient.cohort_id)
        user = await self._session.get(User, user_id)
        state = await self._session.get(BetaOnboardingStateRecord, user_id)
        readiness = await self._user_research_progress(user_id)
        feedback_submitted = bool(
            await self._session.scalar(
                select(func.count(BetaFeedbackItemRecord.id)).where(
                    BetaFeedbackItemRecord.user_id == user_id
                )
            )
        )
        return BetaOnboardingView(
            enrolled=True,
            program_kind=cast(ProgramKind, cohort.program_kind) if cohort else None,
            usage_scope=cast(UsageScope, cohort.usage_scope) if cohort else None,
            notice_version=cohort.notice_version if cohort else None,
            email_verified=bool(user and user.email_verified_at),
            watchlist_started=readiness[0],
            first_value_symbol=readiness[1],
            market_ready=readiness[2],
            deterministic_ready=readiness[3],
            ai_terminal=readiness[4],
            feedback_submitted=feedback_submitted,
            acknowledged=bool(state and state.acknowledged_at),
            dismissed=bool(state and state.dismissed_at),
        )

    async def update_onboarding(
        self, user_id: UUID, action: Literal["acknowledge", "dismiss"]
    ) -> BetaOnboardingView:
        recipient = await self._session.scalar(
            select(BetaInviteRecipientRecord).where(BetaInviteRecipientRecord.user_id == user_id)
        )
        if recipient is None:
            raise InviteBetaError("beta_onboarding_not_enrolled")
        state = await self._session.get(BetaOnboardingStateRecord, user_id)
        if state is None:
            state = BetaOnboardingStateRecord(
                user_id=user_id,
                recipient_id=recipient.id,
                schema_version=ONBOARDING_SCHEMA_VERSION,
            )
            self._session.add(state)
        now = datetime.now(UTC)
        if action == "acknowledge":
            state.acknowledged_at = state.acknowledged_at or now
        else:
            state.dismissed_at = state.dismissed_at or now
        await self._session.commit()
        return await self.onboarding(user_id)

    async def _view(
        self, record: BetaInviteCohortRecord, *, include_recipients: bool
    ) -> BetaCohortView:
        recipients = list(
            await self._session.scalars(
                select(BetaInviteRecipientRecord)
                .where(BetaInviteRecipientRecord.cohort_id == record.id)
                .order_by(BetaInviteRecipientRecord.created_at)
            )
        )
        views: list[BetaRecipientView] = []
        funnel = {
            "staged": len(recipients),
            "submitted": 0,
            "delivered": 0,
            "bounced": 0,
            "complained": 0,
            "registered": 0,
            "verified": 0,
            "watchlist_started": 0,
            "market_ready": 0,
            "deterministic_ready": 0,
            "ai_terminal": 0,
            "feedback_submitted": 0,
        }
        for recipient in recipients:
            delivery = (
                await self._session.get(TransactionalEmailDeliveryRecord, recipient.delivery_id)
                if recipient.delivery_id
                else None
            )
            user = await self._session.get(User, recipient.user_id) if recipient.user_id else None
            watchlist_started = False
            first_value_symbol: str | None = None
            market_ready = False
            deterministic_ready = False
            ai_terminal = False
            feedback_submitted = False
            if user:
                (
                    watchlist_started,
                    first_value_symbol,
                    market_ready,
                    deterministic_ready,
                    ai_terminal,
                ) = await self._user_research_progress(user.id)
                feedback_submitted = bool(
                    await self._session.scalar(
                        select(func.count(BetaFeedbackItemRecord.id)).where(
                            BetaFeedbackItemRecord.user_id == user.id
                        )
                    )
                )
            if delivery and delivery.status in funnel:
                funnel[delivery.status] += 1
            if user:
                funnel["registered"] += 1
            if user and user.email_verified_at:
                funnel["verified"] += 1
            if watchlist_started:
                funnel["watchlist_started"] += 1
            if market_ready:
                funnel["market_ready"] += 1
            if deterministic_ready:
                funnel["deterministic_ready"] += 1
            if ai_terminal:
                funnel["ai_terminal"] += 1
            if feedback_submitted:
                funnel["feedback_submitted"] += 1
            if include_recipients:
                views.append(
                    BetaRecipientView(
                        id=recipient.id,
                        email=recipient.normalized_email,
                        status=cast(
                            Literal[
                                "staged",
                                "queued",
                                "registered",
                                "withdrawn",
                                "expired",
                                "failed",
                            ],
                            recipient.status,
                        ),
                        delivery_status=delivery.status if delivery else None,
                        email_verified=bool(user and user.email_verified_at),
                        first_watchlist_item=watchlist_started,
                        first_value_symbol=first_value_symbol,
                        market_ready=market_ready,
                        deterministic_ready=deterministic_ready,
                        ai_terminal=ai_terminal,
                        feedback_submitted=feedback_submitted,
                        last_error_code=recipient.last_error_code
                        or (delivery.error_code if delivery else None),
                        created_at=recipient.created_at,
                    )
                )
        return BetaCohortView(
            id=record.id,
            name=record.name,
            program_kind=cast(ProgramKind, record.program_kind),
            usage_scope=cast(UsageScope, record.usage_scope),
            notice_version=record.notice_version,
            status=cast(
                Literal[
                    "draft",
                    "approved",
                    "dispatching",
                    "active",
                    "paused",
                    "closed",
                    "cancelled",
                ],
                record.status,
            ),
            target_size=record.target_size,
            expires_at=record.expires_at,
            acceptance_run_id=record.acceptance_run_id,
            reason_code=record.reason_code,
            approved_at=record.approved_at,
            dispatched_at=record.dispatched_at,
            created_at=record.created_at,
            gate_reasons=await self.gate_reasons(cast(ProgramKind, record.program_kind)),
            funnel=funnel,
            recipients=views,
        )

    async def _user_research_progress(
        self, user_id: UUID
    ) -> tuple[bool, str | None, bool, bool, bool]:
        symbols = list(
            await self._session.scalars(
                select(WatchlistItemRecord.symbol)
                .join(WatchlistRecord, WatchlistRecord.id == WatchlistItemRecord.watchlist_id)
                .where(WatchlistRecord.user_id == user_id)
                .order_by(WatchlistItemRecord.created_at)
            )
        )
        if not symbols:
            return False, None, False, False, False
        readiness = await StockReadinessService(self._session, self._settings).get_many(symbols)
        market_ready = any(
            any(stage.key == "market" and stage.status == "ready" for stage in item.stages)
            for item in readiness
        )
        deterministic_ready = any(
            any(
                stage.key == "deterministic_research" and stage.status == "ready"
                for stage in item.stages
            )
            for item in readiness
        )
        ai_terminal_statuses = {"ready", "failed", "paused", "unsupported"}
        ai_terminal = any(
            any(
                stage.key == "ai_research" and stage.status in ai_terminal_statuses
                for stage in item.stages
            )
            for item in readiness
        )
        first_ready = next(
            (
                item.canonical_symbol
                for item in readiness
                if any(
                    stage.key == "deterministic_research" and stage.status == "ready"
                    for stage in item.stages
                )
            ),
            readiness[0].canonical_symbol,
        )
        return True, first_ready, market_ready, deterministic_ready, ai_terminal

    async def _latest_acceptance(self) -> ProviderAcceptanceRunRecord | None:
        result = await self._session.scalar(
            select(ProviderAcceptanceRunRecord)
            .where(ProviderAcceptanceRunRecord.environment == self._settings.app_env)
            .order_by(ProviderAcceptanceRunRecord.created_at.desc())
            .limit(1)
        )
        return result

    async def _locked_cohort(self, cohort_id: UUID) -> BetaInviteCohortRecord:
        cohort = await self._session.scalar(
            select(BetaInviteCohortRecord)
            .where(BetaInviteCohortRecord.id == cohort_id)
            .with_for_update()
        )
        if cohort is None:
            raise LookupError("beta_cohort_not_found")
        return cohort
