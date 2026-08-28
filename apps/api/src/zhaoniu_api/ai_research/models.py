from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from zhaoniu_api.research.models import (
    CalculationTrace,
    EvidenceMetric,
    EvidenceSource,
    ObservationDimension,
    ResearchCoverage,
)


class AIResearchStatus(StrEnum):
    READY = "ready"
    NOT_BUILT = "not_built"
    BUILDING = "building"
    FAILED = "failed"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"


class AIResearchReason(StrEnum):
    DETERMINISTIC_SNAPSHOT_MISSING = "deterministic_snapshot_missing"
    UNSUPPORTED_ISSUER_TYPE = "unsupported_issuer_type"
    LLM_DISABLED = "llm_disabled"
    GENERATION_FAILED = "generation_failed"


class CitedText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Chinese research prose without Arabic digits, Chinese quantities, dates, "
            "percentages, amounts, prices or time-window lengths; describe historical windows "
            "as 历史区间 and never write forms such as 三年."
        ),
    )
    evidence_refs: list[str] = Field(
        min_length=1,
        max_length=4,
        description="One to four valid evidence IDs; never include a fifth reference.",
    )


class AIResearchDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ObservationDimension
    interpretation: CitedText | None


class AIAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: CitedText
    interpretation: CitedText


class StockHealthResearchV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["stock-health-v1"] = "stock-health-v1"
    headline: CitedText
    executive_summary: list[CitedText] = Field(min_length=2, max_length=4)
    dimensions: list[AIResearchDimension] = Field(min_length=5, max_length=5)
    attention_items: list[AIAttentionItem] = Field(default_factory=list, max_length=5)


class EvidenceIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^EV-[A-F0-9]{12}$")
    observation_id: UUID
    dimension: ObservationDimension
    title: str
    summary: str
    current_period: date
    evidence_metrics: list[EvidenceMetric]
    evidence_sources: list[EvidenceSource]
    calculation: CalculationTrace


class AIResearchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_version: Literal["ai-context-v2"] = "ai-context-v2"
    snapshot_id: UUID
    symbol: str
    knowledge_cutoff: datetime
    data_version: str
    metric_version: str
    rule_set_version: str
    research_template_version: str
    coverage: list[ResearchCoverage]
    evidence_index: list[EvidenceIndexEntry]
    context_hash: str = ""


class AIResearchOutputDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: UUID
    run_id: UUID
    symbol: str
    snapshot_id: UUID
    knowledge_cutoff: datetime
    research_type: Literal["stock_health"] = "stock_health"
    ai_generated: Literal[True] = True
    provider_display_name: str
    model_display_name: str
    context_version: str
    context_hash: str
    prompt_version: str
    prompt_hash: str
    output_schema_version: str
    model_route_version: str
    route_hash: str
    content: StockHealthResearchV1
    evidence_index: list[EvidenceIndexEntry]
    coverage: list[ResearchCoverage]
    generated_at: datetime


class AIResearchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AIResearchStatus
    reason: AIResearchReason | None = None
    freshness: Literal["current", "stale"] | None = None
    output: AIResearchOutputDocument | None = None


@dataclass(frozen=True, slots=True)
class AIResearchBuildResult:
    status: str
    run_id: UUID | None
    output_id: UUID | None
    idempotency_key: str | None
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class AIResearchRunLease:
    run_id: UUID
    acquired: bool
    status: str


@dataclass(frozen=True, slots=True)
class AIResearchRunView:
    run_id: UUID
    status: str
    snapshot_id: UUID
    error_code: str | None


@dataclass(frozen=True, slots=True)
class LLMCallAudit:
    run_id: UUID
    attempt_index: int
    task_type: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_microunits: int | None
    status: str
    finish_reason: str | None = None
    error_code: str | None = None
    requested_model: str | None = None
    actual_model: str | None = None
    capability_mode: str | None = None
