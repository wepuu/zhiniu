from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.db import ProviderAcceptanceRunRecord, User
from zhaoniu_api.system import MIGRATION_HEAD


@dataclass(frozen=True, slots=True)
class BetaReadinessReport:
    status: str
    active_users: int
    capacity: int
    blocking_reasons: list[str]


async def evaluate_beta_readiness(session: AsyncSession, settings: Settings) -> BetaReadinessReport:
    blocking: list[str] = []
    current = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    if current != MIGRATION_HEAD:
        blocking.append("migration_not_at_head")
    active_users = int(
        await session.scalar(select(func.count()).select_from(User).where(User.status == "active"))
        or 0
    )
    if active_users >= settings.beta_max_active_users:
        blocking.append("beta_capacity_reached")
    if settings.registration_mode != "invite_only":
        blocking.append("registration_not_invite_only")
    if settings.email_delivery_mode == "disabled":
        blocking.append("transactional_email_disabled")
    if settings.legal_review_status != "approved":
        blocking.append("legal_review_not_approved")
    if settings.data_use_status != "approved":
        blocking.append("data_use_not_approved")
    if current == MIGRATION_HEAD:
        acceptance = await session.scalar(
            select(ProviderAcceptanceRunRecord)
            .where(ProviderAcceptanceRunRecord.environment == settings.app_env)
            .order_by(ProviderAcceptanceRunRecord.created_at.desc())
            .limit(1)
        )
        if acceptance is None:
            blocking.append("provider_acceptance_missing")
        else:
            if acceptance.status != "passed":
                blocking.append("provider_acceptance_failed")
            if acceptance.finished_at < datetime.now(UTC) - timedelta(
                hours=settings.provider_acceptance_max_age_hours
            ):
                blocking.append("provider_acceptance_stale")
            if not acceptance.beta_eligible:
                blocking.append("provider_data_policy_not_beta_eligible")
    if settings.access_activation_enabled and settings.commercialization_status != "approved":
        blocking.append("commercial_activation_not_approved")
    if settings.app_env != "production":
        status = "ready_for_internal" if not blocking else "not_ready"
    else:
        status = "ready_for_invited_beta" if not blocking else "blocked"
    return BetaReadinessReport(
        status=status,
        active_users=active_users,
        capacity=settings.beta_max_active_users,
        blocking_reasons=blocking,
    )
