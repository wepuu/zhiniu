from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderAcceptanceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    dataset: str
    symbol: str | None = None
    scenario: str
    requirement: Literal["mandatory", "conditional", "optional"]
    status: Literal["passed", "failed", "blocked", "unsupported"]
    reason_code: str | None = None
    observed_count: int = 0
    latest_artifact_at: datetime | None = None
    detail: dict[str, object] = Field(default_factory=dict)
    evidence_fingerprint: str


class ProviderAcceptanceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    environment: str
    profile_version: str
    policy_version: str
    usage_scope: str
    knowledge_cutoff: datetime
    status: Literal["passed", "failed", "blocked"]
    mandatory_items: int
    succeeded_items: int
    failed_items: int
    blocked_items: int
    unsupported_items: int
    beta_eligible: bool
    result_fingerprint: str
    started_at: datetime
    finished_at: datetime
    items: list[ProviderAcceptanceItem] = Field(default_factory=list)


class ProviderAcceptanceRunList(BaseModel):
    items: list[ProviderAcceptanceRun]
