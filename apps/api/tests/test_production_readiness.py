import pytest
from pydantic import ValidationError
from zhaoniu_api.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "public_base_url": "https://research.example.com",
        "trusted_hosts": "research.example.com",
        "allowed_origins": "https://research.example.com",
        "auth_cookie_secure": True,
        "database_url": "postgresql+asyncpg://zhaoniu:secret@postgres:5432/zhaoniu",
        "redis_url": "redis://redis:6379/0",
        "registration_invite_hmac_secret": "i" * 40,
        "access_activation_hmac_secret": "a" * 40,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_secure_production_configuration_is_accepted() -> None:
    production_settings().validate_runtime_security()


@pytest.mark.parametrize(
    ("overrides", "error_code"),
    [
        ({"auth_cookie_secure": False}, "production_auth_cookie_must_be_secure"),
        ({"public_base_url": "http://research.example.com"}, "must_use_https"),
        ({"trusted_hosts": "*"}, "trusted_hosts_must_be_explicit"),
        ({"database_url": "postgresql+asyncpg://x@localhost/db"}, "must_not_use_localhost"),
    ],
)
def test_insecure_production_configuration_fails_closed(
    overrides: dict[str, object], error_code: str
) -> None:
    with pytest.raises(ValueError, match=error_code):
        production_settings(**overrides).validate_runtime_security()


def test_settings_reject_invalid_beta_capacity() -> None:
    with pytest.raises(ValidationError):
        Settings(beta_max_active_users=0)
