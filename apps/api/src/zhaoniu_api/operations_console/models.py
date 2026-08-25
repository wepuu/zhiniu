from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OperatorRole = Literal["viewer", "support", "operations", "security_admin"]


class OperatorContext(BaseModel):
    role: OperatorRole
    capabilities: list[str]
    elevated_until: datetime | None = None
    elevated: bool = False


class OperatorElevateRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class OperatorMembershipView(BaseModel):
    user_id: UUID
    email: str
    role: OperatorRole
    created_at: datetime


class OperatorDashboardResponse(BaseModel):
    generated_at: datetime
    environment: str
    users: dict[str, int]
    access: dict[str, int]
    ai: dict[str, int | str | None]
    email: dict[str, int | str | bool | None]
    coverage: dict[str, int | str | None]
    system: dict[str, str | int | bool | list[str] | None]


class OperatorUserSummary(BaseModel):
    id: UUID
    email: str
    status: str
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None
    access_status: str
    access_valid_until: datetime | None


class OperatorUserListResponse(BaseModel):
    items: list[OperatorUserSummary]
    total: int


class OperatorUserDetail(OperatorUserSummary):
    active_sessions: int
    watchlist_count: int
    saved_screen_count: int


class OperatorActionResponse(BaseModel):
    status: Literal["completed", "accepted", "skipped"]
    target_id: str | None = None
    detail: str | None = None


class OperatorInviteBatchCreate(BaseModel):
    count: int = Field(ge=1, le=100)
    expires_in_days: int = Field(default=14, ge=1, le=90)
    name: str | None = Field(default=None, max_length=120)


class OperatorInviteBatchResponse(BaseModel):
    batch_id: UUID
    codes: list[str]
    expires_at: datetime
    plaintext_retrievable: Literal[False] = False


class OperatorAccessCodeCreate(BaseModel):
    term: Literal["month", "year"]
    expires_in_days: int = Field(default=7, ge=1, le=90)


class OperatorAccessCodeResponse(BaseModel):
    batch_id: UUID
    assigned_user_id: UUID
    code: str
    expires_at: datetime
    plaintext_retrievable: Literal[False] = False


class OperatorFeedbackUpdate(BaseModel):
    status: Literal["triaged", "resolved"] | None = None
    severity: Literal["P0", "P1", "P2", "P3"] | None = None
    assigned_operator_user_id: UUID | None = None
    due_at: datetime | None = None
    resolution_code: str | None = Field(default=None, max_length=64)
    internal_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_change(self) -> "OperatorFeedbackUpdate":
        if not self.model_fields_set:
            raise ValueError("feedback_update_empty")
        if self.status == "resolved" and not self.resolution_code:
            raise ValueError("feedback_resolution_code_required")
        return self


class OperatorFeedbackItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    feature_key: str
    category: str
    message: str
    status: str
    severity: Literal["P0", "P1", "P2", "P3"]
    assigned_operator_user_id: UUID | None = None
    due_at: datetime | None = None
    resolution_code: str | None = None
    internal_note: str | None = None
    created_at: datetime
    updated_at: datetime


class OperatorFeedbackListResponse(BaseModel):
    items: list[OperatorFeedbackItem]
    total: int


class OperatorAuditItem(BaseModel):
    id: UUID
    actor_user_id: UUID
    actor_role: str
    action_key: str
    target_type: str
    target_id: str | None
    result: str
    reason_code: str | None
    metadata: dict[str, object]
    created_at: datetime


class OperatorAuditListResponse(BaseModel):
    items: list[OperatorAuditItem]


class ProviderStatusView(BaseModel):
    provider: str
    capability: str
    status: Literal["disabled", "unknown", "healthy", "degraded", "unavailable"]
    configured: bool
    checked_at: datetime | None = None
    latency_ms: int | None = None
    reason_code: str | None = None


class ProviderStatusListResponse(BaseModel):
    items: list[ProviderStatusView]
