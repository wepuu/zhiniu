from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EffectiveEntitlements(BaseModel):
    access_status: Literal["basic", "enabled", "expired"]
    valid_until: datetime | None = None
    features: dict[str, bool]
    limits: dict[str, int]


class AccessEnvelope(EffectiveEntitlements):
    activation_available: bool
    support_contact_url: str | None = None


class AccessActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activation_code: str = Field(min_length=8, max_length=80)


class AccessActivationResponse(AccessEnvelope):
    redemption_id: UUID
    reused: bool = False


class GeneratedCodeBatch(BaseModel):
    batch_id: UUID
    codes: list[str]
    expires_at: datetime


class IssuedAccessCode(BaseModel):
    batch_id: UUID
    assigned_user_id: UUID
    code: str
    expires_at: datetime
