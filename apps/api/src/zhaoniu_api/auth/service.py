from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.db import User, UserSessionRecord, WatchlistRecord
from zhaoniu_api.domain.models import UserAccount, UserSession

DEFAULT_WATCHLIST_NAME = "核心观察"
FREE_ENTITLEMENT_PLAN = "internal_beta"
FREE_ENTITLEMENT_LIMITS = {
    "watchlist_groups": 5,
    "watchlist_memberships_total": 30,
}


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    user: UserAccount
    session: UserSession
    token: str


class AuthenticationError(ValueError):
    pass


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._password_hash = PasswordHash.recommended()

    @property
    def session_max_age_seconds(self) -> int:
        return int(timedelta(days=self._settings.auth_session_days).total_seconds())

    async def register(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthenticatedSession:
        normalized_email = normalize_email(email)
        validate_password(password, min_length=self._settings.auth_password_min_length)
        now = datetime.now(UTC)
        user = User(
            email=normalized_email,
            password_hash=self._password_hash.hash(password),
            status="active",
            last_login_at=now,
        )
        self._session.add(user)
        await self._session.flush()
        self._session.add(
            WatchlistRecord(user_id=user.id, name=DEFAULT_WATCHLIST_NAME, is_default=True)
        )
        try:
            auth = await self._create_session_record(user, user_agent, ip_address, now)
            await self._session.commit()
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

    async def _create_session_record(
        self,
        user: User,
        user_agent: str | None,
        ip_address: str | None,
        now: datetime,
    ) -> AuthenticatedSession:
        token = token_urlsafe(48)
        record = UserSessionRecord(
            user_id=user.id,
            token_hash=hash_token(token),
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
