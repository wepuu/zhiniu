from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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


class AutomationTriggerResponse(BaseModel):
    status: Literal["accepted", "skipped", "blocked"]
    run_id: UUID
    run_status: AutomationRunStatus


class AutomationTickResult(BaseModel):
    status: Literal["disabled", "idle", "scheduled"]
    run_ids: list[UUID] = Field(default_factory=list)
