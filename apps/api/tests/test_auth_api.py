from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from zhaoniu_api.access_control.models import EffectiveEntitlements
from zhaoniu_api.auth.service import AuthenticatedSession, AuthenticationError
from zhaoniu_api.dependencies import get_access_control_service, get_auth_service
from zhaoniu_api.domain.models import UserAccount, UserSession
from zhaoniu_api.main import create_app


class FakeAuthService:
    session_max_age_seconds = 3600

    def __init__(self) -> None:
        self.user = UserAccount(
            id=UUID("00000000-0000-4000-8000-000000000101"),
            email="analyst@example.com",
            status="active",
            created_at=datetime(2026, 8, 19, tzinfo=UTC),
            last_login_at=datetime(2026, 8, 19, tzinfo=UTC),
        )
        self.session = UserSession(
            id=uuid4(),
            user_id=self.user.id,
            created_at=datetime(2026, 8, 19, tzinfo=UTC),
            last_used_at=datetime(2026, 8, 19, tzinfo=UTC),
            expires_at=datetime(2026, 8, 19, tzinfo=UTC) + timedelta(days=30),
            revoked_at=None,
            user_agent="test",
            is_current=True,
        )
        self.logged_out = False

    async def register(
        self,
        *,
        email: str,
        password: str,
        invitation_code: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthenticatedSession:
        return AuthenticatedSession(
            user=self.user,
            session=self.session,
            token="valid-token",
            csrf_token="valid-csrf-token",
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthenticatedSession:
        if password != "correct-password-123":
            raise AuthenticationError("invalid_credentials")
        return AuthenticatedSession(
            user=self.user,
            session=self.session,
            token="valid-token",
            csrf_token="valid-csrf-token",
        )

    async def authenticate(self, token: str | None) -> UserAccount | None:
        return self.user if token == "valid-token" else None

    async def logout(self, token: str | None) -> None:
        self.logged_out = token == "valid-token"

    async def validate_csrf(self, token: str | None, csrf_token: str | None) -> bool:
        return token == "valid-token" and csrf_token == "valid-csrf-token"

    async def list_sessions(self, user_id: UUID, current_token: str | None) -> list[UserSession]:
        return [self.session]

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> bool:
        return session_id == self.session.id


class FakeAccessControlService:
    async def effective_entitlements(self, user_id: UUID) -> EffectiveEntitlements:
        return EffectiveEntitlements(
            access_status="enabled",
            features={"natural_language_screening": True},
            limits={
                "watchlist_groups": 5,
                "watchlist_memberships_total": 30,
                "saved_screens": 10,
                "screen_parses_daily": 30,
                "concurrent_screen_parses": 1,
            },
        )


def test_auth_routes_issue_cookie_and_read_current_user() -> None:
    app = create_app()
    fake = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: fake
    app.dependency_overrides[get_access_control_service] = lambda: FakeAccessControlService()
    client = TestClient(app)

    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst@example.com",
            "password": "long-password-123",
            "invitation_code": "INV-TEST-CODE",
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["email"] == "analyst@example.com"
    assert "httponly" in created.headers["set-cookie"].lower()

    me = client.get("/api/v1/me", cookies={"zhaoniu_session": "valid-token"})
    assert me.status_code == 200
    assert me.json()["entitlements"]["limits"]["watchlist_groups"] == 5

    sessions = client.get("/api/v1/me/sessions", cookies={"zhaoniu_session": "valid-token"})
    assert sessions.status_code == 200
    assert sessions.json()["total"] == 1

    logout = client.post(
        "/api/v1/auth/logout",
        cookies={
            "zhaoniu_session": "valid-token",
            "zhaoniu_csrf": "valid-csrf-token",
        },
        headers={"X-CSRF-Token": "valid-csrf-token"},
    )
    assert logout.status_code == 204
    assert fake.logged_out is True


def test_login_rejects_invalid_credentials() -> None:
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@example.com", "password": "wrong-password-123"},
    )
    assert response.status_code == 401
