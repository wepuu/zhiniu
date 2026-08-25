from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReleaseStatus = Literal[
    "draft",
    "blocked",
    "ready_closed",
    "deployed_observing",
    "ready_invites",
    "released",
    "rolled_back",
    "rejected",
]
GateType = Literal["closed_deployment", "invite_activation"]
ApprovalRole = Literal["engineering", "data_compliance", "product_operations"]
ApprovalDecision = Literal["approved", "rejected"]
DeploymentEventType = Literal["deployed", "released", "failed", "rolled_back"]
GateStatus = Literal["passed", "blocked"]
GateItemStatus = Literal["passed", "failed", "not_applicable"]
ArtifactStatus = Literal["passed", "failed"]


class ProductionReleaseCandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commit_sha: str = Field(min_length=40, max_length=64)
    migration_head: str = Field(min_length=1, max_length=32)
    api_image_digest: str = Field(min_length=71, max_length=71)
    web_image_digest: str = Field(min_length=71, max_length=71)
    configuration_fingerprint: str = Field(min_length=64, max_length=64)
    sbom_sha256: str = Field(min_length=64, max_length=64)
    backup_sha256: str = Field(min_length=64, max_length=64)
    restore_verified_at: datetime
    quality_gate_status: ArtifactStatus
    e2e_status: ArtifactStatus
    security_scan_status: ArtifactStatus

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) not in {40, 64} or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError("commit_sha_must_be_40_or_64_hex")
        return normalized

    @field_validator("configuration_fingerprint", "sbom_sha256", "backup_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError("value_must_be_sha256_hex")
        return normalized

    @field_validator("api_image_digest", "web_image_digest")
    @classmethod
    def validate_image_digest(cls, value: str) -> str:
        normalized = value.strip().lower()
        digest = normalized.removeprefix("sha256:")
        if (
            not normalized.startswith("sha256:")
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("image_digest_must_be_sha256")
        return normalized

    @field_validator("restore_verified_at")
    @classmethod
    def validate_restore_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("restore_verified_at_must_include_timezone")
        return value.astimezone(UTC)


class ProductionReleaseGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_type: GateType


class ProductionReleaseApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_role: ApprovalRole
    decision: ApprovalDecision
    note: str | None = Field(default=None, max_length=500)


class ProductionDeploymentEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: DeploymentEventType
    deployment_ref: str = Field(min_length=1, max_length=160)
    reason_code: str | None = Field(default=None, max_length=120)


class ProductionReleaseGateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_key: str
    category: str
    mandatory: bool
    status: GateItemStatus
    reason_code: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)
    evidence_fingerprint: str
    checked_at: datetime
    expires_at: datetime | None = None


class ProductionReleaseGateRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    gate_type: GateType
    status: GateStatus
    rule_set_version: str
    result_fingerprint: str
    started_at: datetime
    finished_at: datetime
    items: list[ProductionReleaseGateItem] = Field(default_factory=list)


class ProductionReleaseApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    approval_role: ApprovalRole
    decision: ApprovalDecision
    actor_user_id: UUID
    note: str | None = None
    created_at: datetime


class ProductionDeploymentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    event_type: DeploymentEventType
    deployment_ref: str
    reason_code: str | None = None
    recorded_by_user_id: UUID
    created_at: datetime


class ProductionReleaseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    target_environment: Literal["production"]
    status: ReleaseStatus
    commit_sha: str
    migration_head: str
    api_image_digest: str
    web_image_digest: str
    configuration_fingerprint: str
    sbom_sha256: str
    backup_sha256: str
    restore_verified_at: datetime
    quality_gate_status: ArtifactStatus
    e2e_status: ArtifactStatus
    security_scan_status: ArtifactStatus
    created_by_user_id: UUID
    created_at: datetime
    approvals: list[ProductionReleaseApproval] = Field(default_factory=list)
    latest_gates: list[ProductionReleaseGateRun] = Field(default_factory=list)
    deployment_events: list[ProductionDeploymentEvent] = Field(default_factory=list)


class ProductionReleaseCandidateList(BaseModel):
    items: list[ProductionReleaseCandidate]
