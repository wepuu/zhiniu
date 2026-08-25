from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zhaoniu_api.invite_beta.security import validate_recipient_email

CohortStatus = Literal[
    "draft", "approved", "dispatching", "active", "paused", "closed", "cancelled"
]
RecipientStatus = Literal["staged", "queued", "registered", "withdrawn", "expired", "failed"]


class BetaCohortCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    target_size: int = Field(ge=1, le=100)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class BetaRecipientsAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emails: list[str] = Field(min_length=1, max_length=100)

    @field_validator("emails")
    @classmethod
    def normalize_emails(cls, values: list[str]) -> list[str]:
        normalized = [validate_recipient_email(value) for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate_recipient_email")
        return normalized


class BetaCohortPause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=3, max_length=120)


class BetaRecipientView(BaseModel):
    id: UUID
    email: str
    status: RecipientStatus
    delivery_status: str | None = None
    email_verified: bool = False
    first_watchlist_item: bool = False
    feedback_submitted: bool = False
    last_error_code: str | None = None
    created_at: datetime


class BetaCohortView(BaseModel):
    id: UUID
    name: str
    status: CohortStatus
    target_size: int
    expires_at: datetime
    acceptance_run_id: UUID | None = None
    reason_code: str | None = None
    approved_at: datetime | None = None
    dispatched_at: datetime | None = None
    created_at: datetime
    gate_reasons: list[str] = Field(default_factory=list)
    funnel: dict[str, int] = Field(default_factory=dict)
    recipients: list[BetaRecipientView] = Field(default_factory=list)


class BetaCohortList(BaseModel):
    items: list[BetaCohortView]


class BetaOnboardingView(BaseModel):
    enrolled: bool
    schema_version: str = "invite-beta-onboarding-v1"
    email_verified: bool = False
    watchlist_started: bool = False
    feedback_submitted: bool = False
    acknowledged: bool = False
    dismissed: bool = False


class BetaOnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["acknowledge", "dismiss"]
