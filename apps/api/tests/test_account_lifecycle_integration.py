import os
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.access_control.service import AccessControlService
from zhaoniu_api.auth.email import EmailDeliveryResult, TransactionalEmail
from zhaoniu_api.auth.service import AuthService
from zhaoniu_api.config import Settings

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@dataclass(slots=True)
class CapturingEmailGateway:
    provider_name: str = "test"
    messages: list[TransactionalEmail] = field(default_factory=list)

    async def send(self, message: TransactionalEmail) -> EmailDeliveryResult:
        self.messages.append(message)
        return EmailDeliveryResult(provider="test", message_id=f"test-{len(self.messages)}")


def token_from_message(message: TransactionalEmail) -> str:
    link = next(line for line in message.text_body.splitlines() if "?token=" in line)
    return parse_qs(urlparse(link).query)["token"][0]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_invited_user_can_verify_and_recover_account() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        registration_invite_hmac_secret="integration-invite-secret-1234567890",
        access_activation_hmac_secret="integration-activation-secret-123456",
        public_base_url="http://testserver",
        beta_max_active_users=100000,
    )
    gateway = CapturingEmailGateway()
    async with factory() as session:
        invites = await AccessControlService(session, settings).generate_registration_invites(
            count=1, expires_in_days=1, operator="integration-test", name="phase12"
        )
        auth = AuthService(session, settings, gateway)
        created = await auth.register(
            email="phase12-integration@example.com",
            password="initial-password-123",
            invitation_code=invites.codes[0],
            legal_acceptances={
                "terms_of_service": "2026-08-v1",
                "privacy_policy": "2026-08-v1",
            },
            user_agent="pytest",
            ip_address="127.0.0.1",
        )
        verification_token = token_from_message(gateway.messages[-1])
        assert await auth.verify_email(verification_token) == "verified"

        await auth.request_password_reset(created.user.email)
        reset_token = token_from_message(gateway.messages[-1])
        await auth.confirm_password_reset(reset_token, "replacement-password-123")
        assert await auth.authenticate(created.token) is None

        logged_in = await auth.login(
            email=created.user.email,
            password="replacement-password-123",
            user_agent="pytest",
            ip_address="127.0.0.1",
        )
        assert logged_in.user.email_verified_at is not None
    await engine.dispose()
