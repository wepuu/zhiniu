import base64
import os

import pytest
from pydantic import ValidationError
from zhaoniu_api.config import Settings, _configure_outbound_http_proxy
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
from zhaoniu_api.provider_configuration.service import _diagnostic_reason_code


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
