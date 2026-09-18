from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AutomationRunStatus = Literal[
    "pending",
    "running",
    "succeeded",
    "succeeded_with_warnings",
    "partial",
    "failed",
    "blocked",
    "skipped",
]
AutomationStepStatus = Literal["pending", "running", "succeeded", "failed", "skipped", "blocked"]


class AutomationPolicyConfiguration(BaseModel):
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    daily_time: str = "19:30"
    max_universe_size: int = Field(default=100, ge=1, le=500)
    financial_reporting_interval_hours: int = Field(default=72, ge=24, le=168)
    financial_normal_interval_hours: int = Field(default=168, ge=72, le=720)
    event_pipeline_enabled: bool = True
    peer_research_enabled: bool = True
    ai_research_enabled: bool = False

    @field_validator("daily_time")
    @classmethod
    def validate_daily_time(cls, value: str) -> str:
        try:
            hour, minute = (int(part) for part in value.split(":"))
        except (ValueError, TypeError) as error:
            raise ValueError("daily_time_must_be_hh_mm") from error
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("daily_time_must_be_hh_mm")
        return f"{hour:02d}:{minute:02d}"


class AutomationPolicyUpdate(BaseModel):
    enabled: bool
    configuration: AutomationPolicyConfiguration


class AutomationPolicyView(BaseModel):
    id: UUID
    policy_key: str
    display_name: str
    enabled: bool
    hard_disabled: bool
    revision: int
    configuration: AutomationPolicyConfiguration
    configuration_hash: str
    next_due_at: datetime | None
    last_evaluated_at: datetime | None
    updated_at: datetime


class AutomationPolicyListResponse(BaseModel):
    items: list[AutomationPolicyView]


class AutomationStepView(BaseModel):
    id: UUID
    scope_type: Literal["run", "symbol", "industry"]
    scope_key: str
    symbol: str | None
    step_key: str
    dependency_order: int
    status: AutomationStepStatus
    attempt_count: int
    changed: bool
    provider_call_count: int
    rows_received: int
    rows_written: int
    duration_ms: int | None
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


class AutomationRunSummary(BaseModel):
    id: UUID
    policy_key: str
    trigger_kind: Literal["scheduled", "manual", "resume", "watchlist"]
    scheduled_for: datetime
    status: AutomationRunStatus
    universe_size: int
    total_steps: int
    succeeded_steps: int
    failed_steps: int
    skipped_steps: int
    warning_steps: int
    provider_call_count: int
    rows_received: int
    rows_written: int
    signal_count: int
    alert_count: int
    ai_output_count: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AutomationRunDetail(AutomationRunSummary):
    policy_revision: int
    policy_hash: str
    universe_hash: str | None
    universe_symbols: list[str]
    steps: list[AutomationStepView]


class AutomationRunListResponse(BaseModel):
    items: list[AutomationRunSummary]
    total: int


AutomationSLOMetricKey = Literal[
    "queue_start",
    "market_ready",
    "deterministic_ready",
    "ai_terminal",
]


class AutomationSLOMetric(BaseModel):
    key: AutomationSLOMetricKey
    target_ms: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    p95_ms: int | None = Field(default=None, ge=0)
    met: bool | None = None


class AutomationSLOSnapshot(BaseModel):
    generated_at: datetime
    window_started_at: datetime
    window_hours: int = Field(ge=1, le=168)
    total_watchlist_runs: int = Field(ge=0)
    terminal_runs: int = Field(ge=0)
    acceptable_terminal_runs: int = Field(ge=0)
    acceptable_terminal_rate_percent: float | None = Field(default=None, ge=0, le=100)
    pending_runs: int = Field(ge=0)
    running_runs: int = Field(ge=0)
    stale_active_runs: int = Field(ge=0)
    unclassified_failure_count: int = Field(ge=0)
    minimum_sample_count: int = Field(ge=1)
    release_gate_met: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    metrics: list[AutomationSLOMetric]
    failure_reasons: dict[str, int]


CalendarHealthStatus = Literal["healthy", "stale", "unknown"]


class TradingCalendarHealth(BaseModel):
    exchange: Literal["SSE", "SZSE"]
    status: CalendarHealthStatus
    source: str | None = None
    calendar_version: str | None = None
    latest_trade_date: date | None = None
    checked_at: datetime | None = None
    reason_code: str | None = None


BetaObservationStatus = Literal["passed", "failed"]


class BetaReliabilityObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment: Literal["staging", "production"]
    window_hours: Literal[24, 48] = 48
    release_commit: str = Field(min_length=40, max_length=64)
    api_image_digest: str = Field(min_length=71, max_length=71)
    web_image_digest: str = Field(min_length=71, max_length=71)
    configuration_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("release_commit")
    @classmethod
    def validate_commit(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) not in {40, 64} or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("release_commit_must_be_hex")
        return normalized

    @field_validator("configuration_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("configuration_fingerprint_must_be_sha256")
        return normalized

    @field_validator("api_image_digest", "web_image_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        normalized = value.strip().lower()
        digest = normalized.removeprefix("sha256:")
        if (
            not normalized.startswith("sha256:")
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("image_digest_must_be_sha256")
        return normalized


class BetaReliabilityObservation(BaseModel):
    id: UUID
    environment: Literal["staging", "production"]
    status: BetaObservationStatus
    rule_set_version: str
    release_commit: str
    api_image_digest: str
    web_image_digest: str
    migration_head: str
    configuration_fingerprint: str
    window_started_at: datetime
    window_ended_at: datetime
    slo_snapshot: AutomationSLOSnapshot
    calendar_health: list[TradingCalendarHealth]
    blocking_reasons: list[str]
    result_fingerprint: str
    created_by_user_id: UUID
    created_at: datetime


class BetaReliabilityObservationList(BaseModel):
    items: list[BetaReliabilityObservation]


class AutomationTriggerResponse(BaseModel):
    status: Literal["accepted", "skipped", "blocked"]
    run_id: UUID
    run_status: AutomationRunStatus


class AutomationTickResult(BaseModel):
    status: Literal["disabled", "idle", "scheduled"]
    run_ids: list[UUID] = Field(default_factory=list)
