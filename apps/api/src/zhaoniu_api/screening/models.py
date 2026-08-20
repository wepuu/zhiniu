from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScreenOperator = Literal["gt", "gte", "lt", "lte", "between"]
ScreenStatus = Literal["pending", "running", "succeeded", "failed"]


class MetricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["metric"] = "metric"
    metric_code: str
    selector: Literal["latest_available", "latest_fy"] = "latest_available"
    operator: ScreenOperator
    value: Decimal
    upper_value: Decimal | None = None

    @model_validator(mode="after")
    def validate_range(self) -> MetricCriterion:
        if self.operator == "between":
            if self.upper_value is None or self.upper_value < self.value:
                raise ValueError("between_requires_ordered_upper_value")
        elif self.upper_value is not None:
            raise ValueError("upper_value_only_allowed_for_between")
        return self


class PeerCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["peer"] = "peer"
    metric_code: str
    operator: ScreenOperator
    value: Decimal = Field(ge=0, le=100)
    upper_value: Decimal | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_range(self) -> PeerCriterion:
        if self.operator == "between":
            if self.upper_value is None or self.upper_value < self.value:
                raise ValueError("between_requires_ordered_upper_value")
        elif self.upper_value is not None:
            raise ValueError("upper_value_only_allowed_for_between")
        return self


class IndustryCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["industry"] = "industry"
    taxonomy_code: str
    taxonomy_version: str
    industry_codes: list[str] = Field(min_length=1, max_length=20)


class EventCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["event"] = "event"
    event_family: Literal["share_repurchase", "share_pledge", "share_unlock", "regulatory_action"]
    mode: Literal["exists", "not_exists"]
    within_days: int = Field(ge=1, le=730)


ScreenCriterion = Annotated[
    MetricCriterion | PeerCriterion | IndustryCriterion | EventCriterion,
    Field(discriminator="kind"),
]


class ScreenSort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = "symbol"
    direction: Literal["asc", "desc"] = "asc"


class ScreenQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dsl_version: Literal["screen-query-v1"] = "screen-query-v1"
    filters: list[ScreenCriterion] = Field(min_length=1, max_length=8)
    sort: ScreenSort = Field(default_factory=ScreenSort)


class ScreenExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: ScreenQuery


class ScreenMetricCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    display_name: str
    dimension: str
    unit: str
    source_kind: Literal["metric", "valuation"]
    selectors: list[str]
    operators: list[ScreenOperator]


class ScreenIndustryCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_code: str
    taxonomy_version: str
    industry_code: str
    industry_name: str


class ScreenCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dsl_version: str
    metrics: list[ScreenMetricCatalogItem]
    peer_metric_codes: list[str]
    industries: list[ScreenIndustryCatalogItem]
    event_families: list[str]
    limitations: list[str]


class ScreenValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    code: str
    message: str


class ScreenValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    canonical_query: ScreenQuery | None = None
    query_hash: str | None = None
    issues: list[ScreenValidationIssue] = Field(default_factory=list)


class ScreenCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "partial_coverage", "not_built", "building", "failed"]
    snapshot_id: UUID | None = None
    knowledge_cutoff: datetime | None = None
    universe_count: int = 0
    eligible_count: int = 0
    excluded_count: int = 0
    fact_counts: dict[str, int] = Field(default_factory=dict)
    taxonomy_code: str | None = None
    taxonomy_version: str | None = None
    commercial_use_status: Literal["development_evaluation_only"] = "development_evaluation_only"
    limitations: list[str] = Field(default_factory=list)


class ScreenExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    screening_snapshot_id: UUID
    status: ScreenStatus
    query_hash: str
    engine_version: str
    knowledge_cutoff: datetime
    result_count: int
    evaluated_count: int
    unknown_count: int
    excluded_count: int
    error_summary: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class ScreenMatchedCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_key: str
    label: str
    value: Decimal | str | bool
    unit: str | None = None
    effective_on: date | None = None
    evidence_type: str
    evidence_id: UUID


class ScreenResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    stock_name: str
    exchange: str
    industry_name: str | None = None
    ordinal: int
    matched_conditions: list[ScreenMatchedCondition]
    research_path: str
    is_in_watchlist: bool


class ScreenResultListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    query_cutoff: datetime
    items: list[ScreenResultItem]
    total: int
    next_cursor: str | None = None


class ScreeningBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "skipped"]
    snapshot_id: UUID
    member_count: int
    fact_count: int
    idempotency_key: str
