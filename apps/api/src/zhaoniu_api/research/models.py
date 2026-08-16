from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from zhaoniu_api.fundamentals.models import MetricBasis, MetricStatus


class ObservationDimension(StrEnum):
    GROWTH = "growth"
    PROFITABILITY = "profitability"
    QUALITY = "quality"
    BALANCE = "balance"
    VALUATION = "valuation"


class AttentionLevel(StrEnum):
    INFO = "info"
    NOTICE = "notice"
    IMPORTANT = "important"


class Movement(StrEnum):
    UP = "up"
    DOWN = "down"
    CROSSED_UP = "crossed_up"
    CROSSED_DOWN = "crossed_down"
    NEUTRAL = "neutral"


class CoverageStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass(frozen=True, slots=True)
class FundamentalMetricPoint:
    canonical_symbol: str
    code: str
    value: Decimal | None
    unit: str
    status: MetricStatus
    period_end: date
    fiscal_period: str
    basis: MetricBasis
    known_at: datetime
    metric_version: str
    input_fingerprint: str
    input_report_ids: tuple[UUID, ...] = ()
    input_valuation_ids: tuple[UUID, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


class EvidenceMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_point_id: UUID
    role: str
    metric_code: str
    display_name: str
    period_end: date
    fiscal_period: str
    basis: str
    value: Decimal | None
    unit: str
    status: str
    input_report_ids: list[UUID] = Field(default_factory=list)
    input_valuation_ids: list[UUID] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: UUID
    provider: str
    provider_record_id: str
    fiscal_period: str
    period_end: date
    published_at: datetime
    published_at_precision: str
    known_at: datetime


class CalculationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    expression: str
    change_value: Decimal | None = None
    change_unit: str | None = None


class ResearchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    symbol: str
    dimension: ObservationDimension
    observation_family: str
    observation_type: str
    attention_level: AttentionLevel
    movement: Movement
    title: str
    summary: str
    current_period: date
    comparison_periods: list[date]
    rule_id: str
    rule_version: str
    observation_key: str
    content_fingerprint: str
    evidence_metrics: list[EvidenceMetric]
    evidence_sources: list[EvidenceSource]
    calculation: CalculationTrace
    generated_at: datetime


class ResearchCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ObservationDimension
    status: CoverageStatus
    reason: str | None = None


class ResearchSnapshotDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    symbol: str
    knowledge_cutoff: datetime
    data_version: str
    metric_version: str
    rule_set_version: str
    research_template_version: str
    snapshot_schema_version: str
    producer_kind: Literal["deterministic"] = "deterministic"
    producer_version: str
    latest_financial_period: date | None
    latest_valuation_date: date | None
    input_manifest: dict[str, Any]
    coverage: list[ResearchCoverage]
    observations: list[ResearchObservation]
    generated_at: datetime


class ResearchSnapshotEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_built"]
    snapshot: ResearchSnapshotDocument | None = None


class ObservationList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    snapshot_id: UUID | None
    items: list[ResearchObservation]
    total: int


@dataclass(frozen=True, slots=True)
class ResearchBuildResult:
    status: str
    snapshot_id: UUID
    data_version: str
    observation_count: int
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ResearchRunLease:
    run_id: UUID
    acquired: bool
    status: str
