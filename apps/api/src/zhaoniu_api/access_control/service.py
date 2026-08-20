from calendar import monthrange
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.codes import code_hmac, code_prefix, generate_code
from zhaoniu_api.access_control.models import (
    AccessActivationResponse,
    AccessEnvelope,
    EffectiveEntitlements,
    GeneratedCodeBatch,
    IssuedAccessCode,
)
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    AccessActivationBatchRecord,
    AccessActivationCodeRecord,
    AccessActivationRedemptionRecord,
    PlanVersionRecord,
    RegistrationInviteBatchRecord,
    RegistrationInviteRecord,
    SubscriptionRecord,
    User,
)

LEGACY_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000001")
BASIC_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000002")
ADVANCED_PLAN_VERSION_ID = UUID("10000000-0000-4000-8000-000000000003")


class AccessControlError(ValueError):
    pass


class AccessControlService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def activation_available(self) -> bool:
        if not self._settings.access_activation_enabled:
            return False
        if self._settings.app_env != "production":
            return True
        return self._settings.commercialization_status == "approved"

    async def effective_entitlements(
        self, user_id: UUID, *, now: datetime | None = None
    ) -> EffectiveEntitlements:
        effective_at = now or datetime.now(UTC)
        user = await self._session.get(User, user_id)
        if user is None:
            raise LookupError("user_not_found")
        base = await self._session.get(PlanVersionRecord, user.base_plan_version_id)
        if base is None:
            raise LookupError("base_plan_version_not_found")
        subscription = await self._session.scalar(
            select(SubscriptionRecord).where(SubscriptionRecord.user_id == user_id)
        )
        selected = base
        status: Literal["basic", "enabled", "expired"] = "basic"
        valid_until = None
        if subscription is not None:
            valid_until = subscription.current_period_end
            if (
                subscription.status == "active"
                and subscription.revoked_at is None
                and subscription.current_period_start <= effective_at
                and effective_at < subscription.current_period_end
            ):
                advanced = await self._session.get(PlanVersionRecord, subscription.plan_version_id)
                if advanced is None:
                    raise LookupError("subscription_plan_version_not_found")
                selected = advanced
                status = "enabled"
            elif effective_at >= subscription.current_period_end:
                status = "expired"
        return EffectiveEntitlements(
            access_status=status,
            valid_until=valid_until,
            features={key: bool(value) for key, value in selected.features.items()},
            limits={key: int(value) for key, value in selected.limits.items()},
        )

    async def access_envelope(self, user_id: UUID) -> AccessEnvelope:
        entitlements = await self.effective_entitlements(user_id)
        return AccessEnvelope(
            **entitlements.model_dump(),
            activation_available=self.activation_available(),
            support_contact_url=self._settings.support_contact_url or None,
        )

    async def generate_registration_invites(
        self,
        *,
        count: int,
        expires_in_days: int,
        operator: str,
        name: str | None = None,
    ) -> GeneratedCodeBatch:
        if not 1 <= count <= 500:
            raise AccessControlError("invalid_invite_count")
        if not 1 <= expires_in_days <= 90:
            raise AccessControlError("invalid_invite_expiry")
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days)
        batch = RegistrationInviteBatchRecord(
            id=uuid4(),
            name=name or f"Invite batch {now:%Y-%m-%d %H:%M}",
            quantity=count,
            expires_at=expires_at,
            created_by_operator=operator,
        )
        self._session.add(batch)
        codes: list[str] = []
        for _ in range(count):
            code = generate_code("INV")
            codes.append(code)
            self._session.add(
                RegistrationInviteRecord(
                    id=uuid4(),
                    batch_id=batch.id,
                    code_hmac=code_hmac(
                        code, "INV", self._settings.registration_invite_hmac_secret
                    ),
                    code_prefix=code_prefix(code),
                    expires_at=expires_at,
                )
            )
        await self._session.commit()
        return GeneratedCodeBatch(batch_id=batch.id, codes=codes, expires_at=expires_at)

    async def issue_access_code(
        self,
        *,
        user_email: str,
        term_kind: Literal["month", "year"],
        expires_in_days: int,
        operator: str,
    ) -> IssuedAccessCode:
        if not 1 <= expires_in_days <= 90:
            raise AccessControlError("invalid_activation_expiry")
        user = await self._session.scalar(
            select(User).where(User.email == user_email.strip().lower())
        )
        if user is None:
            raise LookupError("user_not_found")
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days)
        batch = AccessActivationBatchRecord(
            id=uuid4(),
            name=f"Assigned {term_kind} access {now:%Y-%m-%d %H:%M}",
            plan_version_id=ADVANCED_PLAN_VERSION_ID,
            term_kind=term_kind,
            quantity=1,
            expires_at=expires_at,
            created_by_operator=operator,
        )
        self._session.add(batch)
        code = generate_code("ACT")
        self._session.add(
            AccessActivationCodeRecord(
                id=uuid4(),
                batch_id=batch.id,
                code_hmac=code_hmac(code, "ACT", self._settings.access_activation_hmac_secret),
                code_prefix=code_prefix(code),
                assigned_user_id=user.id,
                expires_at=expires_at,
            )
        )
        await self._session.commit()
        return IssuedAccessCode(
            batch_id=batch.id,
            assigned_user_id=user.id,
            code=code,
            expires_at=expires_at,
        )

    async def activate(
        self, user_id: UUID, code: str, *, now: datetime | None = None
    ) -> AccessActivationResponse:
        if not self.activation_available():
            raise AccessControlError("access_activation_unavailable")
        effective_at = now or datetime.now(UTC)
        user = await self._session.get(User, user_id)
        if user is None:
            raise AccessControlError("activation_code_unavailable")
        if user.email_verified_at is None:
            raise AccessControlError("email_verification_required")
        try:
            digest = code_hmac(code, "ACT", self._settings.access_activation_hmac_secret)
        except ValueError as error:
            raise AccessControlError("activation_code_unavailable") from error
        activation = await self._session.scalar(
            select(AccessActivationCodeRecord)
            .where(AccessActivationCodeRecord.code_hmac == digest)
            .with_for_update()
        )
        if activation is None or activation.assigned_user_id != user_id:
            raise AccessControlError("activation_code_unavailable")
        existing = await self._session.scalar(
            select(AccessActivationRedemptionRecord).where(
                AccessActivationRedemptionRecord.activation_code_id == activation.id,
                AccessActivationRedemptionRecord.user_id == user_id,
            )
        )
        if existing is not None:
            access = await self.access_envelope(user_id)
            return AccessActivationResponse(
                **access.model_dump(), redemption_id=existing.id, reused=True
            )
        batch = await self._session.get(AccessActivationBatchRecord, activation.batch_id)
        if (
            batch is None
            or activation.redeemed_at is not None
            or activation.revoked_at is not None
            or batch.revoked_at is not None
            or activation.expires_at <= effective_at
            or batch.expires_at <= effective_at
        ):
            raise AccessControlError("activation_code_unavailable")
        subscription = await self._session.scalar(
            select(SubscriptionRecord)
            .where(SubscriptionRecord.user_id == user_id)
            .with_for_update()
        )
        previous_end = subscription.current_period_end if subscription else None
        period_start = max(effective_at, previous_end) if previous_end else effective_at
        if batch.term_kind not in ("month", "year"):
            raise AccessControlError("activation_code_unavailable")
        term_kind: Literal["month", "year"] = "month" if batch.term_kind == "month" else "year"
        period_end = add_calendar_term(period_start, term_kind)
        if subscription is None:
            subscription = SubscriptionRecord(
                id=uuid4(),
                user_id=user_id,
                plan_code="advanced",
                plan_version_id=batch.plan_version_id,
                status="active",
                current_period_start=period_start,
                current_period_end=period_end,
                activation_source="activation_code",
            )
            self._session.add(subscription)
        else:
            subscription.plan_code = "advanced"
            subscription.plan_version_id = batch.plan_version_id
            subscription.status = "active"
            subscription.current_period_start = (
                subscription.current_period_start
                if previous_end is not None and previous_end > effective_at
                else effective_at
            )
            subscription.current_period_end = period_end
            subscription.activation_source = "activation_code"
            subscription.revoked_at = None
        redemption = AccessActivationRedemptionRecord(
            id=uuid4(),
            activation_code_id=activation.id,
            user_id=user_id,
            plan_version_id=batch.plan_version_id,
            term_kind=term_kind,
            previous_period_end=previous_end,
            new_period_start=period_start,
            new_period_end=period_end,
            redeemed_at=effective_at,
        )
        self._session.add(redemption)
        activation.redeemed_by_user_id = user_id
        activation.redeemed_at = effective_at
        await self._session.commit()
        access = await self.access_envelope(user_id)
        return AccessActivationResponse(
            **access.model_dump(), redemption_id=redemption.id, reused=False
        )


def add_calendar_term(value: datetime, term_kind: Literal["month", "year"]) -> datetime:
    if term_kind == "year":
        year = value.year + 1
        day = min(value.day, monthrange(year, value.month)[1])
        return value.replace(year=year, day=day)
    month_index = value.month
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
