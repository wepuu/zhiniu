from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "zhaoniu"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://zhaoniu:zhaoniu@localhost:5432/zhaoniu"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    auth_cookie_name: str = "zhaoniu_session"
    auth_csrf_cookie_name: str = "zhaoniu_csrf"
    auth_cookie_secure: bool = False
    allowed_origins: str = "http://localhost:3000"
    auth_session_days: int = Field(default=30, ge=1, le=90)
    auth_password_min_length: int = Field(default=15, ge=15, le=128)
    public_base_url: str = "http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    registration_mode: Literal["invite_only", "closed"] = "invite_only"
    beta_mode: Literal["controlled", "internal"] = "controlled"
    beta_max_active_users: int = Field(default=500, ge=1, le=100000)
    registration_invite_hmac_secret: str = "development-invite-secret-change-me"
    access_activation_hmac_secret: str = "development-activation-secret-change-me"
    access_activation_enabled: bool = False
    support_contact_url: str = ""
    access_operator_id: str = "local-cli"
    commercialization_status: Literal["review_required", "approved", "blocked"] = "review_required"
    legal_review_status: Literal["review_required", "approved", "blocked"] = "review_required"
    data_use_status: Literal["review_required", "approved", "blocked"] = "review_required"
    email_delivery_mode: Literal["disabled", "smtp", "resend"] = "disabled"
    email_from_address: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    resend_api_key: str = ""
    resend_from_name: str = "知牛研究"
    resend_from_email: str = ""
    resend_sending_domain: str = ""
    resend_webhook_secret: str = ""
    email_diagnostic_recipient: str = ""
    email_verification_ttl_hours: int = Field(default=24, ge=1, le=168)
    password_reset_ttl_minutes: int = Field(default=30, ge=10, le=120)
    market_data_provider: Literal["akshare"] = "akshare"
    disclosure_provider: Literal["akshare"] = "akshare"
    llm_enabled: bool = False
    llm_model_chain: str = ""
    llm_max_attempts: int = Field(default=4, ge=1, le=4)
    llm_per_model_timeout_seconds: float = Field(default=75, gt=0, le=180)
    llm_run_deadline_seconds: float = Field(default=240, gt=0, le=600)
    llm_structured_output_mode: Literal["json_schema", "json_object"] = "json_schema"
    llm_provider_max_concurrency: int = Field(default=2, ge=1, le=16)
    llm_provider_daily_call_limit: int = Field(default=100, ge=1, le=10000)
    screen_parser_enabled: bool = False
    screen_parser_model_chain: str = ""
    screen_parser_max_attempts: int = Field(default=2, ge=1, le=2)
    screen_parser_per_model_timeout_seconds: float = Field(default=30, gt=0, le=60)
    screen_parser_run_deadline_seconds: float = Field(default=75, gt=0, le=120)
    screen_parser_hmac_secret: str = "development-only-change-me"
    screen_parser_input_ttl_seconds: int = Field(default=600, ge=60, le=1800)
    coverage_usage_scope: Literal[
        "development_evaluation", "internal_beta", "external_beta", "production"
    ] = "development_evaluation"
    coverage_policy_version: str = "coverage-policy-v1"
    coverage_operator_pinned_symbols: str = "600519,300750,300376,000001"
    coverage_acceptance_symbols: str = "600519,300750,300376,000001"
    coverage_backfill_batch_size: int = Field(default=10, ge=1, le=50)
    coverage_backfill_max_concurrency: int = Field(default=2, ge=1, le=8)
    coverage_provider_rate_limit: int = Field(default=30, ge=1, le=600)
    beta_feedback_rate_limit: int = Field(default=5, ge=1, le=30)
    beta_learning_min_group_size: int = Field(default=3, ge=2, le=20)
    operator_elevation_minutes: int = Field(default=15, ge=5, le=30)
    operator_user_search_rate_limit: int = Field(default=30, ge=5, le=120)
    automation_hard_disabled: bool = True
    automation_tick_seconds: int = Field(default=60, ge=30, le=300)
    automation_max_universe_size: int = Field(default=100, ge=1, le=500)
    automation_max_concurrency: int = Field(default=4, ge=1, le=16)
    automation_catchup_window_minutes: int = Field(default=360, ge=0, le=1440)
    automation_lease_minutes: int = Field(default=30, ge=5, le=120)
    automation_ai_enabled: bool = False
    automation_ai_max_calls_per_run: int = Field(default=10, ge=0, le=100)
    automation_ai_concurrency: int = Field(default=1, ge=1, le=4)

    @property
    def llm_models(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.llm_model_chain.split(",") if item.strip())

    @property
    def screen_parser_models(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.screen_parser_model_chain.split(",") if item.strip()
        )

    @property
    def coverage_pinned_symbols(self) -> tuple[str, ...]:
        return tuple(
            item.strip()
            for item in self.coverage_operator_pinned_symbols.split(",")
            if item.strip()
        )

    @property
    def coverage_reference_symbols(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.coverage_acceptance_symbols.split(",") if item.strip()
        )

    @property
    def origin_allowlist(self) -> tuple[str, ...]:
        return tuple(
            item.strip().rstrip("/") for item in self.allowed_origins.split(",") if item.strip()
        )

    @property
    def trusted_host_list(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.trusted_hosts.split(",") if item.strip())

    def validate_runtime_security(self) -> None:
        if self.app_env != "production":
            return
        if not self.auth_cookie_secure:
            raise ValueError("production_auth_cookie_must_be_secure")
        if "*" in self.origin_allowlist:
            raise ValueError("production_allowed_origins_must_be_explicit")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("production_public_base_url_must_use_https")
        if not self.trusted_host_list or "*" in self.trusted_host_list:
            raise ValueError("production_trusted_hosts_must_be_explicit")
        if "localhost" in self.database_url or "localhost" in self.redis_url:
            raise ValueError("production_dependencies_must_not_use_localhost")
        unsafe_secrets = {
            "development-invite-secret-change-me",
            "development-activation-secret-change-me",
        }
        if (
            self.registration_invite_hmac_secret in unsafe_secrets
            or self.access_activation_hmac_secret in unsafe_secrets
            or len(self.registration_invite_hmac_secret) < 32
            or len(self.access_activation_hmac_secret) < 32
        ):
            raise ValueError("production_access_code_secrets_are_unsafe")
        if self.access_activation_enabled and self.commercialization_status != "approved":
            raise ValueError("production_access_activation_requires_approval")
        if self.email_delivery_mode == "smtp" and (
            not self.smtp_host or not self.email_from_address
        ):
            raise ValueError("production_email_configuration_incomplete")
        if self.email_delivery_mode == "resend" and (
            not self.resend_api_key
            or not self.resend_from_email
            or not self.resend_sending_domain
            or not self.resend_webhook_secret
        ):
            raise ValueError("production_resend_configuration_incomplete")
        if self.screen_parser_enabled and (
            len(self.screen_parser_hmac_secret) < 32
            or self.screen_parser_hmac_secret == "development-only-change-me"
        ):
            raise ValueError("production_screen_parser_secret_is_unsafe")


@lru_cache
def get_settings() -> Settings:
    return Settings()
