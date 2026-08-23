from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

ProviderName = Literal["deepseek", "resend"]
ALLOWED_DEEPSEEK_MODELS = (
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
)


class DeepSeekRouteConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    models: list[str] = Field(
        default_factory=lambda: [ALLOWED_DEEPSEEK_MODELS[0]], min_length=1, max_length=2
    )
    max_attempts: int = Field(default=1, ge=1, le=2)
    timeout_seconds: float = Field(default=60, ge=10, le=180)
    deadline_seconds: float = Field(default=90, ge=15, le=240)
    max_output_tokens: int = Field(default=1200, ge=128, le=4000)

    @model_validator(mode="after")
    def validate_route(self) -> DeepSeekRouteConfiguration:
        if any(model not in ALLOWED_DEEPSEEK_MODELS for model in self.models):
            raise ValueError("deepseek_model_not_allowed")
        if len(set(self.models)) != len(self.models):
            raise ValueError("duplicate_deepseek_model")
        if self.max_attempts > len(self.models):
            raise ValueError("attempts_exceed_model_count")
        if self.deadline_seconds < self.timeout_seconds:
            raise ValueError("deadline_must_cover_timeout")
        return self


class DeepSeekConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    max_concurrency: int = Field(default=2, ge=1, le=16)
    daily_call_limit: int = Field(default=100, ge=1, le=10000)
    stock_health: DeepSeekRouteConfiguration = Field(default_factory=DeepSeekRouteConfiguration)
    screen_parser: DeepSeekRouteConfiguration = Field(default_factory=DeepSeekRouteConfiguration)
    research_assistant: DeepSeekRouteConfiguration = Field(
        default_factory=lambda: DeepSeekRouteConfiguration(
            models=[ALLOWED_DEEPSEEK_MODELS[0]],
            max_attempts=1,
            timeout_seconds=60,
            deadline_seconds=90,
            max_output_tokens=1200,
        )
    )
    comparison_explanation: DeepSeekRouteConfiguration = Field(
        default_factory=lambda: DeepSeekRouteConfiguration(
            models=[ALLOWED_DEEPSEEK_MODELS[0]],
            max_attempts=1,
            timeout_seconds=60,
            deadline_seconds=90,
            max_output_tokens=1200,
        )
    )

    @model_validator(mode="after")
    def lock_research_assistant(self) -> DeepSeekConfiguration:
        route = self.research_assistant
        if route.models != [ALLOWED_DEEPSEEK_MODELS[0]] or route.max_attempts != 1:
            raise ValueError("research_assistant_profile_locked")
        comparison = self.comparison_explanation
        if comparison.models != [ALLOWED_DEEPSEEK_MODELS[0]] or comparison.max_attempts != 1:
            raise ValueError("comparison_explanation_profile_locked")
        return self


def deepseek_route_available(
    configuration: DeepSeekConfiguration,
    credentials: Mapping[str, str],
    route: Literal["stock_health", "screen_parser", "research_assistant", "comparison_explanation"]
    | None = None,
) -> bool:
    if not configuration.enabled or not credentials.get("api_key"):
        return False
    return route is None or bool(getattr(configuration, route).enabled)


class ResendConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    from_name: str = Field(default="知牛研究", max_length=80)
    from_email: str = Field(default="", max_length=320)
    sending_domain: str = Field(default="", max_length=253)

    @model_validator(mode="after")
    def validate_sender(self) -> ResendConfiguration:
        if self.enabled:
            domain = self.sending_domain.strip().lower()
            email = self.from_email.strip().lower()
            if not domain or not email.endswith(f"@{domain}"):
                raise ValueError("resend_sender_domain_mismatch")
        return self


class DeepSeekDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_row_version: int = Field(ge=0)
    configuration: DeepSeekConfiguration
    api_key: SecretStr | None = None


class ResendDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_row_version: int = Field(ge=0)
    configuration: ResendConfiguration
    api_key: SecretStr | None = None
    webhook_secret: SecretStr | None = None


ProviderDraftUpdate = Annotated[
    DeepSeekDraftUpdate | ResendDraftUpdate, Field(union_mode="left_to_right")
]


class ProviderRevisionView(BaseModel):
    revision: int
    status: Literal["draft", "active", "retired"]
    configuration: dict[str, object]
    configuration_hash: str
    credential_generation: int | None = None
    created_at: datetime
    published_at: datetime | None = None


class ProviderConfigurationView(BaseModel):
    provider: ProviderName
    environment: str
    source: Literal["environment", "database", "disabled"]
    row_version: int
    credential_state: Literal["missing", "environment", "encrypted"]
    credential_rotated_at: datetime | None = None
    active: ProviderRevisionView | None = None
    draft: ProviderRevisionView | None = None
    diagnostic_status: Literal["not_run", "healthy", "unavailable"]
    diagnostic_checked_at: datetime | None = None
    webhook_verified_at: datetime | None = None


class ProviderConfigurationListResponse(BaseModel):
    items: list[ProviderConfigurationView]


class ProviderDraftDiagnoseResponse(BaseModel):
    provider: ProviderName
    status: Literal["healthy", "unavailable"]
    reason_code: str | None = None
    latency_ms: int
    checked_at: datetime


class ProviderMutationResponse(BaseModel):
    status: Literal["draft_saved", "draft_discarded", "published", "credentials_removed"]
    configuration: ProviderConfigurationView


class ProviderVersionRequest(BaseModel):
    expected_row_version: int = Field(ge=0)
