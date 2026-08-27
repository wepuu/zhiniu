import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from zhaoniu_api.config import Settings, _configure_outbound_http_proxy
from zhaoniu_api.db import (
    PlanVersionRecord,
    ProviderConfigurationRecord,
    ProviderConfigurationRevisionRecord,
    ProviderDiagnosticRunRecord,
    User,
)
from zhaoniu_api.ports.providers import LLMGatewayError
from zhaoniu_api.provider_configuration.crypto import (
    CredentialVault,
    CredentialVaultError,
    generate_key,
)
from zhaoniu_api.provider_configuration.models import (
    ALLOWED_DEEPSEEK_MODELS,
    DeepSeekConfiguration,
    DeepSeekRouteConfiguration,
    ResendConfiguration,
    deepseek_route_available,
)
from zhaoniu_api.provider_configuration.service import (
    ProviderConfigurationService,
    _diagnostic_reason_code,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def test_credential_vault_round_trip_and_aad_binding() -> None:
    key = generate_key()
    vault = CredentialVault({"v1": key}, "v1")
    encrypted = vault.encrypt({"api_key": "secret-value"}, aad="deepseek:1")

    assert encrypted.key_id == "v1"
    assert "secret-value" not in encrypted.ciphertext
    assert vault.decrypt(
        encrypted.ciphertext, encrypted.nonce, encrypted.key_id, aad="deepseek:1"
    ) == {"api_key": "secret-value"}

    with pytest.raises(CredentialVaultError, match="provider_credential_decryption_failed"):
        vault.decrypt(encrypted.ciphertext, encrypted.nonce, encrypted.key_id, aad="resend:1")


def test_credential_vault_supports_key_ring_rotation() -> None:
    old_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    old_vault = CredentialVault({"v1": old_key}, "v1")
    encrypted = old_vault.encrypt({"api_key": "rotate-me"}, aad="deepseek:2")
    rotating_vault = CredentialVault({"v1": old_key, "v2": new_key}, "v2")

    assert (
        rotating_vault.decrypt(
            encrypted.ciphertext, encrypted.nonce, encrypted.key_id, aad="deepseek:2"
        )["api_key"]
        == "rotate-me"
    )
    replacement = rotating_vault.encrypt({"api_key": "rotate-me"}, aad="deepseek:2")
    assert replacement.key_id == "v2"


def test_deepseek_allowlist_and_locked_assistant_profile() -> None:
    with pytest.raises(ValidationError, match="deepseek_model_not_allowed"):
        DeepSeekRouteConfiguration(models=["openai/not-allowed"])

    with pytest.raises(ValidationError, match="research_assistant_profile_locked"):
        DeepSeekConfiguration(
            research_assistant=DeepSeekRouteConfiguration(models=[ALLOWED_DEEPSEEK_MODELS[1]])
        )


def test_managed_deepseek_routes_require_published_credentials_and_route_enablement() -> None:
    configuration = DeepSeekConfiguration(
        enabled=True,
        stock_health=DeepSeekRouteConfiguration(enabled=True),
        research_assistant=DeepSeekRouteConfiguration(enabled=False),
    )

    assert deepseek_route_available(configuration, {"api_key": "configured"})
    assert deepseek_route_available(configuration, {"api_key": "configured"}, "stock_health")
    assert not deepseek_route_available(
        configuration, {"api_key": "configured"}, "research_assistant"
    )
    assert not deepseek_route_available(configuration, {}, "stock_health")


def test_resend_sender_must_match_configured_domain_when_enabled() -> None:
    with pytest.raises(ValidationError, match="resend_sender_domain_mismatch"):
        ResendConfiguration(
            enabled=True,
            from_email="security@example.net",
            sending_domain="example.com",
        )


def test_provider_proxy_configures_standard_httpx_environment(monkeypatch) -> None:
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    settings = Settings(provider_outbound_http_proxy_url="http://127.0.0.1:10808")

    _configure_outbound_http_proxy(settings)

    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:10808"
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:10808"


def test_diagnostic_reason_uses_safe_gateway_classification() -> None:
    error = LLMGatewayError(
        "provider_connection",
        "InternalServerError containing provider implementation details",
    )

    assert _diagnostic_reason_code(error) == "provider_connection"


@pytest.mark.integration
@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
async def test_published_revision_retains_exact_diagnostic_status() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    checked_at = datetime(2026, 8, 27, 12, 39, 44, tzinfo=UTC)

    async with sessions() as session:
        plan_version_id = await session.scalar(select(PlanVersionRecord.id).limit(1))
        assert plan_version_id is not None
        actor = User(
            id=uuid4(),
            email=f"provider-diagnostic-{uuid4()}@example.test",
            password_hash="not-used",
            base_plan_version_id=plan_version_id,
            status="active",
            email_verified_at=checked_at,
        )
        configuration = ProviderConfigurationRecord(
            id=uuid4(),
            provider="deepseek",
            environment="test",
            active_revision=5,
            draft_revision=None,
            row_version=7,
        )
        active = ProviderConfigurationRevisionRecord(
            id=uuid4(),
            configuration_id=configuration.id,
            revision=5,
            status="active",
            configuration_json={"enabled": True},
            configuration_hash="a" * 64,
            credential_generation=4,
            created_by_user_id=actor.id,
            published_by_user_id=actor.id,
            published_at=checked_at + timedelta(seconds=4),
        )
        healthy_draft_diagnostic = ProviderDiagnosticRunRecord(
            id=uuid4(),
            provider="deepseek",
            capability="structured_generation",
            status="healthy",
            latency_ms=120,
            reason_code=None,
            checked_at=checked_at,
            requested_by_user_id=actor.id,
            configuration_revision_id=active.id,
            credential_generation=4,
            target="draft",
        )
        unrelated_diagnostic = ProviderDiagnosticRunRecord(
            id=uuid4(),
            provider="deepseek",
            capability="structured_generation",
            status="unavailable",
            latency_ms=80,
            reason_code="provider_auth",
            checked_at=checked_at + timedelta(minutes=1),
            requested_by_user_id=actor.id,
            configuration_revision_id=active.id,
            credential_generation=3,
            target="active",
        )
        session.add(actor)
        await session.flush()
        session.add(configuration)
        await session.flush()
        session.add_all([active, healthy_draft_diagnostic, unrelated_diagnostic])
        await session.flush()

        service = ProviderConfigurationService(
            session,
            Settings(database_url=TEST_DATABASE_URL, app_env="test"),
        )
        published = await service.get_configuration("deepseek")

        assert published.active is not None
        assert published.active.revision == 5
        assert published.draft is None
        assert published.diagnostic_status == "healthy"
        assert published.diagnostic_checked_at == checked_at

        draft = ProviderConfigurationRevisionRecord(
            id=uuid4(),
            configuration_id=configuration.id,
            revision=6,
            status="draft",
            configuration_json={"enabled": True},
            configuration_hash="b" * 64,
            credential_generation=4,
            created_by_user_id=actor.id,
        )
        session.add(draft)
        configuration.draft_revision = 6
        await session.flush()

        unpublished = await service.get_configuration("deepseek")

        assert unpublished.draft is not None
        assert unpublished.draft.revision == 6
        assert unpublished.diagnostic_status == "not_run"
        assert unpublished.diagnostic_checked_at is None

        await session.rollback()

    await engine.dispose()
