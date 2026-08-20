from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.access_control.codes import code_hmac
from zhaoniu_api.access_control.service import BASIC_PLAN_VERSION_ID
from zhaoniu_api.auth.email import (
    TransactionalEmail,
    TransactionalEmailError,
    TransactionalEmailGateway,
    build_email_gateway,
)
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    EmailVerificationTokenRecord,
    PasswordResetTokenRecord,
    RegistrationInviteBatchRecord,
    RegistrationInviteRecord,
    TransactionalEmailDeliveryRecord,
    User,
    UserLegalAcceptanceRecord,
    UserResearchAlertSettingsRecord,
    UserSessionRecord,
    WatchlistRecord,
)
from zhaoniu_api.domain.models import UserAccount, UserSession
from zhaoniu_api.legal import legal_document, required_registration_documents

DEFAULT_WATCHLIST_NAME = "核心观察"


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    user: UserAccount
    session: UserSession
    token: str
    csrf_token: str


class AuthenticationError(ValueError):
    pass


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        email_gateway: TransactionalEmailGateway | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._password_hash = PasswordHash.recommended()
        self._email = email_gateway or build_email_gateway(settings)

    @property
    def session_max_age_seconds(self) -> int:
        return int(timedelta(days=self._settings.auth_session_days).total_seconds())

    async def register(
        self,
        *,
        email: str,
        password: str,
        invitation_code: str,
        legal_acceptances: dict[str, str],
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthenticatedSession:
        normalized_email = normalize_email(email)
        validate_password(password, min_length=self._settings.auth_password_min_length)
        if self._settings.registration_mode != "invite_only":
            raise AuthenticationError("registration_closed")
        validate_registration_acceptances(legal_acceptances)
        now = datetime.now(UTC)
        if self._settings.beta_mode == "controlled":
            await self._session.execute(text("SELECT pg_advisory_xact_lock(120012)"))
            active_users = await self._session.scalar(
                select(func.count()).select_from(User).where(User.status == "active")
            )
            if int(active_users or 0) >= self._settings.beta_max_active_users:
                raise AuthenticationError("beta_capacity_reached")
        try:
            invite_digest = code_hmac(
                invitation_code,
                "INV",
                self._settings.registration_invite_hmac_secret,
            )
        except ValueError as error:
            raise AuthenticationError("invalid_or_unavailable_invitation") from error
        invite = await self._session.scalar(
            select(RegistrationInviteRecord)
            .where(RegistrationInviteRecord.code_hmac == invite_digest)
            .with_for_update()
        )
        batch = (
            await self._session.get(RegistrationInviteBatchRecord, invite.batch_id)
            if invite is not None
            else None
        )
        if (
            invite is None
            or batch is None
            or invite.consumed_at is not None
            or invite.revoked_at is not None
            or batch.revoked_at is not None
            or invite.expires_at <= now
            or batch.expires_at <= now
        ):
            raise AuthenticationError("invalid_or_unavailable_invitation")
        user = User(
            email=normalized_email,
            password_hash=self._password_hash.hash(password),
            base_plan_version_id=BASIC_PLAN_VERSION_ID,
            status="active",
            last_login_at=now,
        )
        self._session.add(user)
        await self._session.flush()
        self._session.add(
            WatchlistRecord(user_id=user.id, name=DEFAULT_WATCHLIST_NAME, is_default=True)
        )
        self._session.add(UserResearchAlertSettingsRecord(user_id=user.id))
        for document_type, version in legal_acceptances.items():
            document = legal_document(document_type)
            if document is None:
                continue
            self._session.add(
                UserLegalAcceptanceRecord(
                    user_id=user.id,
                    document_type=document_type,
                    document_version=version,
                    content_hash=document.content_hash,
                    accepted_at=now,
                )
            )
        invite.consumed_by_user_id = user.id
        invite.consumed_at = now
        try:
            auth = await self._create_session_record(user, user_agent, ip_address, now)
            verification_token, delivery = await self._create_email_verification(user, now)
            await self._session.commit()
            await self._deliver_email(
                delivery,
                TransactionalEmail(
                    recipient=user.email,
                    subject="验证你的知牛研究邮箱",
                    text_body=(
                        "请使用以下链接验证邮箱：\n"
                        f"{self._settings.public_base_url.rstrip('/')}/verify-email?token={verification_token}\n"
                        "如果不是你发起的注册，请忽略此邮件。"
                    ),
                    template_key="verify_email",
                ),
            )
            return auth
        except IntegrityError as error:
            await self._session.rollback()
            raise AuthenticationError("email_already_registered") from error
        except Exception:
            await self._session.rollback()
            raise

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthenticatedSession:
        normalized_email = normalize_email(email)
        user = await self._session.scalar(select(User).where(User.email == normalized_email))
        if user is None or user.status != "active":
            raise AuthenticationError("invalid_credentials")
        if not self._password_hash.verify(password, user.password_hash):
            raise AuthenticationError("invalid_credentials")
        now = datetime.now(UTC)
        user.last_login_at = now
        try:
            auth = await self._create_session_record(user, user_agent, ip_address, now)
            await self._session.commit()
            return auth
        except Exception:
            await self._session.rollback()
            raise

    async def authenticate(self, token: str | None) -> UserAccount | None:
        if not token:
            return None
        now = datetime.now(UTC)
        token_hash = hash_token(token)
        row = await self._session.scalar(
            select(UserSessionRecord).where(UserSessionRecord.token_hash == token_hash)
        )
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            return None
        user = await self._session.get(User, row.user_id)
        if user is None or user.status != "active":
            return None
        if (now - row.last_used_at) > timedelta(minutes=10):
            row.last_used_at = now
            await self._session.commit()
        return user_to_domain(user)

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        now = datetime.now(UTC)
        await self._session.execute(
            update(UserSessionRecord)
            .where(
                UserSessionRecord.token_hash == hash_token(token),
                UserSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.commit()

    async def validate_csrf(self, token: str | None, csrf_token: str | None) -> bool:
        if not token or not csrf_token:
            return False
        expected = await self._session.scalar(
            select(UserSessionRecord.csrf_token_hash).where(
                UserSessionRecord.token_hash == hash_token(token),
                UserSessionRecord.revoked_at.is_(None),
                UserSessionRecord.expires_at > datetime.now(UTC),
            )
        )
        return expected is not None and expected == hash_token(csrf_token)

    async def list_sessions(self, user_id: UUID, current_token: str | None) -> list[UserSession]:
        current_hash = hash_token(current_token) if current_token else None
        rows = (
            await self._session.scalars(
                select(UserSessionRecord)
                .where(UserSessionRecord.user_id == user_id)
                .order_by(UserSessionRecord.created_at.desc())
            )
        ).all()
        return [
            session_to_domain(row, is_current=row.token_hash == current_hash)
            for row in rows
            if row.revoked_at is None and row.expires_at > datetime.now(UTC)
        ]

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> bool:
        existing = await self._session.scalar(
            select(UserSessionRecord.id).where(
                UserSessionRecord.id == session_id,
                UserSessionRecord.user_id == user_id,
                UserSessionRecord.revoked_at.is_(None),
            )
        )
        if existing is None:
            return False
        await self._session.execute(
            update(UserSessionRecord)
            .where(
                UserSessionRecord.id == session_id,
                UserSessionRecord.user_id == user_id,
                UserSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()
        return True

    async def verify_email(self, token: str) -> str:
        now = datetime.now(UTC)
        row = await self._session.scalar(
            select(EmailVerificationTokenRecord)
            .where(EmailVerificationTokenRecord.token_hash == hash_token(token))
            .with_for_update()
        )
        if row is None or row.revoked_at is not None:
            raise AuthenticationError("email_verification_invalid")
        user = await self._session.get(User, row.user_id)
        if user is None:
            raise AuthenticationError("email_verification_invalid")
        if row.consumed_at is not None or user.email_verified_at is not None:
            return "already_verified"
        if row.expires_at <= now or row.email_snapshot != user.email:
            raise AuthenticationError("email_verification_expired")
        row.consumed_at = now
        user.email_verified_at = now
        await self._session.execute(
            update(EmailVerificationTokenRecord)
            .where(
                EmailVerificationTokenRecord.user_id == user.id,
                EmailVerificationTokenRecord.id != row.id,
                EmailVerificationTokenRecord.consumed_at.is_(None),
                EmailVerificationTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.commit()
        return "verified"

    async def resend_verification(self, user_id: UUID) -> str:
        user = await self._session.get(User, user_id)
        if user is None:
            raise AuthenticationError("user_not_found")
        if user.email_verified_at is not None:
            return "already_verified"
        now = datetime.now(UTC)
        await self._session.execute(
            update(EmailVerificationTokenRecord)
            .where(
                EmailVerificationTokenRecord.user_id == user.id,
                EmailVerificationTokenRecord.consumed_at.is_(None),
                EmailVerificationTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        token, delivery = await self._create_email_verification(user, now)
        await self._session.commit()
        delivered = await self._deliver_email(
            delivery,
            TransactionalEmail(
                recipient=user.email,
                subject="验证你的知牛研究邮箱",
                text_body=(
                    "请使用以下链接验证邮箱：\n"
                    f"{self._settings.public_base_url.rstrip('/')}/verify-email?token={token}"
                ),
                template_key="verify_email",
            ),
        )
        return "sent" if delivered else "delivery_unavailable"

    async def request_password_reset(self, email: str) -> None:
        user = await self._session.scalar(
            select(User).where(User.email == normalize_email(email), User.status == "active")
        )
        if user is None:
            self._password_hash.hash("zhaoniu-dummy-password-reset")
            return
        now = datetime.now(UTC)
        await self._session.execute(
            update(PasswordResetTokenRecord)
            .where(
                PasswordResetTokenRecord.user_id == user.id,
                PasswordResetTokenRecord.consumed_at.is_(None),
                PasswordResetTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        token = token_urlsafe(48)
        self._session.add(
            PasswordResetTokenRecord(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(minutes=self._settings.password_reset_ttl_minutes),
            )
        )
        delivery = TransactionalEmailDeliveryRecord(
            user_id=user.id,
            template_key="reset_password",
            template_version="v1",
            provider=self._email.provider_name,
            status="pending",
        )
        self._session.add(delivery)
        await self._session.commit()
        await self._deliver_email(
            delivery,
            TransactionalEmail(
                recipient=user.email,
                subject="重置你的知牛研究密码",
                text_body=(
                    "请使用以下链接重置密码：\n"
                    f"{self._settings.public_base_url.rstrip('/')}/reset-password?token={token}\n"
                    "链接将在短时间后失效。"
                ),
                template_key="reset_password",
            ),
        )

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        validate_password(new_password, min_length=self._settings.auth_password_min_length)
        now = datetime.now(UTC)
        row = await self._session.scalar(
            select(PasswordResetTokenRecord)
            .where(PasswordResetTokenRecord.token_hash == hash_token(token))
            .with_for_update()
        )
        if row is None or row.consumed_at is not None or row.revoked_at is not None:
            raise AuthenticationError("password_reset_invalid")
        if row.expires_at <= now:
            raise AuthenticationError("password_reset_expired")
        user = await self._session.get(User, row.user_id)
        if user is None or user.status != "active":
            raise AuthenticationError("password_reset_invalid")
        user.password_hash = self._password_hash.hash(new_password)
        user.password_changed_at = now
        row.consumed_at = now
        await self._session.execute(
            update(PasswordResetTokenRecord)
            .where(
                PasswordResetTokenRecord.user_id == user.id,
                PasswordResetTokenRecord.id != row.id,
                PasswordResetTokenRecord.consumed_at.is_(None),
                PasswordResetTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.execute(
            update(UserSessionRecord)
            .where(UserSessionRecord.user_id == user.id, UserSessionRecord.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._session.commit()

    async def accept_legal_documents(
        self, user_id: UUID, acceptances: dict[str, str]
    ) -> list[str]:
        now = datetime.now(UTC)
        for document_type, version in acceptances.items():
            document = legal_document(document_type)
            if document is None or document.version != version:
                raise AuthenticationError("legal_document_version_invalid")
            existing = await self._session.scalar(
                select(UserLegalAcceptanceRecord.id).where(
                    UserLegalAcceptanceRecord.user_id == user_id,
                    UserLegalAcceptanceRecord.document_type == document_type,
                    UserLegalAcceptanceRecord.document_version == version,
                )
            )
            if existing is None:
                self._session.add(
                    UserLegalAcceptanceRecord(
                        user_id=user_id,
                        document_type=document_type,
                        document_version=version,
                        content_hash=document.content_hash,
                        accepted_at=now,
                    )
                )
        await self._session.commit()
        return await self.required_legal_acceptances(user_id)

    async def required_legal_acceptances(self, user_id: UUID) -> list[str]:
        accepted = set(
            (
                await self._session.execute(
                    select(
                        UserLegalAcceptanceRecord.document_type,
                        UserLegalAcceptanceRecord.document_version,
                    ).where(UserLegalAcceptanceRecord.user_id == user_id)
                )
            ).all()
        )
        return [
            item.document_type
            for item in required_registration_documents()
            if (item.document_type, item.version) not in accepted
        ]

    async def _create_email_verification(
        self, user: User, now: datetime
    ) -> tuple[str, TransactionalEmailDeliveryRecord]:
        token = token_urlsafe(48)
        self._session.add(
            EmailVerificationTokenRecord(
                user_id=user.id,
                token_hash=hash_token(token),
                email_snapshot=user.email,
                expires_at=now + timedelta(hours=self._settings.email_verification_ttl_hours),
            )
        )
        delivery = TransactionalEmailDeliveryRecord(
            user_id=user.id,
            template_key="verify_email",
            template_version="v1",
            provider=self._email.provider_name,
            status="pending",
        )
        self._session.add(delivery)
        return token, delivery

    async def _deliver_email(
        self, delivery: TransactionalEmailDeliveryRecord, message: TransactionalEmail
    ) -> bool:
        try:
            result = await self._email.send(message)
            delivery.provider = result.provider
            delivery.provider_message_id = result.message_id[:200]
            delivery.status = "sent"
            delivery.sent_at = datetime.now(UTC)
            delivery.error_code = None
            await self._session.commit()
            return True
        except TransactionalEmailError as error:
            delivery.status = "failed"
            delivery.error_code = str(error)[:80]
            await self._session.commit()
            return False

    async def _create_session_record(
        self,
        user: User,
        user_agent: str | None,
        ip_address: str | None,
        now: datetime,
    ) -> AuthenticatedSession:
        token = token_urlsafe(48)
        csrf_token = token_urlsafe(32)
        record = UserSessionRecord(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token_hash=hash_token(csrf_token),
            user_agent=(user_agent or "")[:240] or None,
            ip_address=(ip_address or "")[:80] or None,
            last_used_at=now,
            expires_at=now + timedelta(days=self._settings.auth_session_days),
        )
        self._session.add(record)
        await self._session.flush()
        return AuthenticatedSession(
            user=user_to_domain(user),
            session=session_to_domain(record, is_current=True),
            token=token,
            csrf_token=csrf_token,
        )


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_password(value: str, *, min_length: int) -> None:
    if len(value) < min_length:
        raise AuthenticationError("password_too_short")
    if len(value) > 128:
        raise AuthenticationError("password_too_long")


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def user_to_domain(user: User) -> UserAccount:
    return UserAccount(
        id=user.id,
        email=user.email,
        status=user.status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        email_verified_at=user.email_verified_at,
        password_changed_at=user.password_changed_at,
    )


def session_to_domain(row: UserSessionRecord, *, is_current: bool) -> UserSession:
    return UserSession(
        id=row.id,
        user_id=row.user_id,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        user_agent=row.user_agent,
        is_current=is_current,
    )


def validate_registration_acceptances(acceptances: dict[str, str]) -> None:
    for document in required_registration_documents():
        if acceptances.get(document.document_type) != document.version:
            raise AuthenticationError("required_legal_acceptance_missing")
