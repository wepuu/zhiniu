from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CoverageDimensionKey = Literal[
    "market",
    "financial",
    "fundamental_research",
    "industry",
    "peer_research",
    "event_radar",
    "screening",
    "ai_research",
]
Availability = Literal[
    "ready",
    "partial",
    "not_built",
    "missing_source_data",
    "unsupported",
    "disabled",
    "blocked_by_policy",
]
Freshness = Literal["current", "stale", "unknown"]
SourceHealth = Literal["healthy", "degraded", "unavailable", "unknown"]


class CoverageDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: CoverageDimensionKey
    availability: Availability
    freshness: Freshness = "unknown"
    source_health: SourceHealth = "unknown"
    reason_codes: list[str] = Field(default_factory=list)
    latest_artifact_at: datetime | None = None


class StockCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    canonical_symbol: str
    snapshot_id: UUID | None = None
    knowledge_cutoff: datetime
    evaluated_at: datetime
    coverage_schema_version: str
    evaluator_version: str
    policy_version: str
    dimensions: list[CoverageDimension]
    limitations: list[str] = Field(default_factory=list)


class UniverseMemberResponse(BaseModel):
    symbol: str
    priority_rank: int
    reason_flags: list[str]


class UniverseSnapshotResponse(BaseModel):
    id: UUID
    knowledge_cutoff: datetime
    universe_fingerprint: str
    schema_version: str
    items: list[UniverseMemberResponse]
    total: int


class CoverageSnapshotResult(BaseModel):
    id: UUID
    universe_snapshot_id: UUID
    knowledge_cutoff: datetime
    evaluated_at: datetime
    member_count: int
    content_fingerprint: str
    status: Literal["succeeded", "skipped"]


class BackfillItemResponse(BaseModel):
    id: UUID
    symbol: str
    action_key: str
    reason_code: str
    status: Literal["pending", "running", "succeeded", "skipped", "failed", "blocked"]
    dependency_order: int
    changed: bool = False
    error_code: str | None = None


class BackfillRunResponse(BaseModel):
    id: UUID
    universe_snapshot_id: UUID
    coverage_snapshot_id: UUID
    status: Literal["pending", "running", "succeeded", "partial", "failed"]
    planned_items: int
    succeeded_items: int
    failed_items: int
    skipped_items: int
    blocked_items: int
    items: list[BackfillItemResponse] = Field(default_factory=list)


FeedbackFeature = Literal[
    "stock_research",
    "research_feed",
    "peer_research",
    "event_radar",
    "screening",
    "account",
    "other",
]
FeedbackCategory = Literal["bug", "data_missing", "hard_to_understand", "feature_request", "other"]


class BetaFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_key: FeedbackFeature
    category: FeedbackCategory
    message: str = Field(min_length=20, max_length=2000)


class BetaFeedbackResponse(BaseModel):
    id: UUID
    feature_key: FeedbackFeature
    category: FeedbackCategory
    status: Literal["new", "triaged", "resolved"]
    created_at: datetime


class BetaFeedbackOperatorView(BetaFeedbackResponse):
    user_id: UUID
    message: str
    updated_at: datetime


class BetaLearningReport(BaseModel):
    generated_at: datetime
    period_days: int
    audience: Literal["internal_beta"] = "internal_beta"
    adoption: dict[str, int | str]
    coverage: dict[str, dict[str, int]]
    top_gaps: list[dict[str, int | str]]
    backfill: dict[str, int]
    feedback: dict[str, int | str]
    unavailable_metrics: list[str]
