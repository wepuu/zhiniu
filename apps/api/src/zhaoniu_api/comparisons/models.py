from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

ComparisonStatus = Literal["pending", "building", "ready", "partial", "failed", "unsupported"]
Comparability = Literal["comparable", "not_comparable", "missing"]


class ComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_symbol: str = Field(min_length=6, max_length=16)
    right_symbol: str = Field(min_length=6, max_length=16)
    include_ai: bool = False
    client_request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def different_symbols(self) -> ComparisonCreate:
        if self.left_symbol.strip().upper() == self.right_symbol.strip().upper():
            raise ValueError("comparison_symbols_must_differ")
        return self


class ComparisonCompany(BaseModel):
    symbol: str
    ticker: str
    name: str
    exchange: str
    board: str
    industry_name: str | None = None


class ComparisonEvidence(BaseModel):
    evidence_id: str
    side: Literal["left", "right", "shared"]
    source_kind: Literal["metric", "valuation", "industry", "peer", "signal"]
    source_id: UUID
    title: str
    known_at: datetime
    evidence_path: str


class ComparisonValue(BaseModel):
    value: str | None
    unit: str | None
    status: str
    period_end: date | None = None
    basis: str | None = None
    evidence_ref: str | None = None


class ComparisonMetric(BaseModel):
    code: str
    label: str
    dimension: str
    comparability: Comparability
    reason: str | None = None
    left: ComparisonValue
    right: ComparisonValue


class ComparisonSignal(BaseModel):
    side: Literal["left", "right"]
    title: str
    summary: str
    attention_level: str
    known_at: datetime
    evidence_ref: str


class ComparisonSnapshotDocument(BaseModel):
    schema_version: Literal["company-comparison-v1"] = "company-comparison-v1"
    profile_version: Literal["standard-v1"] = "standard-v1"
    knowledge_cutoff: datetime
    left: ComparisonCompany
    right: ComparisonCompany
    same_industry: bool
    metrics: list[ComparisonMetric]
    recent_signals: list[ComparisonSignal]
    limitations: list[str]


class ComparisonCitedText(BaseModel):
    text: str = Field(min_length=1, max_length=360)
    evidence_refs: list[str] = Field(min_length=1, max_length=4)


class ComparisonAIResearchV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline: ComparisonCitedText
    common_ground: list[ComparisonCitedText] = Field(min_length=1, max_length=3)
    differences: list[ComparisonCitedText] = Field(min_length=1, max_length=4)
    attention_items: list[ComparisonCitedText] = Field(default_factory=list, max_length=4)


class ComparisonAIOutput(BaseModel):
    output_id: UUID
    provider: str
    model: str
    generated_at: datetime
    content: ComparisonAIResearchV1


class ComparisonResponse(BaseModel):
    id: UUID
    left_symbol: str
    right_symbol: str
    status: ComparisonStatus
    include_ai: bool
    ai_status: Literal["not_requested", "building", "ready", "disabled", "failed"]
    error_code: str | None = None
    requested_cutoff: datetime
    created_at: datetime
    snapshot_id: UUID | None = None
    snapshot: ComparisonSnapshotDocument | None = None
    evidence: list[ComparisonEvidence] = Field(default_factory=list)
    ai_output: ComparisonAIOutput | None = None


class ComparisonListResponse(BaseModel):
    items: list[ComparisonResponse]


class SavedComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    left_symbol: str = Field(min_length=6, max_length=16)
    right_symbol: str = Field(min_length=6, max_length=16)


class SavedComparisonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class SavedComparisonResponse(BaseModel):
    id: UUID
    name: str
    left_symbol: str
    right_symbol: str
    latest_request_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SavedComparisonListResponse(BaseModel):
    items: list[SavedComparisonResponse]
    limit: int


class ComparisonCatalogResponse(BaseModel):
    profile_version: str = "standard-v1"
    supported_issuer_type: str = "general"
    dimensions: list[str]
    ai_available: bool
    saved_limit: int
