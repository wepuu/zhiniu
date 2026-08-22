from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

CLASSIFIER_VERSION = "corporate-disclosure-classifier-v2.1"
EXTRACTOR_VERSION = "corporate-event-extractor-v2"
ATTENTION_RULE_VERSION = "event-attention-v2"
RADAR_SCHEMA_VERSION = "event-radar-v2"


class EventFamily(StrEnum):
    SHARE_REPURCHASE = "share_repurchase"
    SHARE_PLEDGE = "share_pledge"
    SHARE_UNLOCK = "share_unlock"
    REGULATORY_ACTION = "regulatory_action"
    SHAREHOLDER_CHANGE = "shareholder_change"
    LITIGATION_ARBITRATION = "litigation_arbitration"


class EventType(StrEnum):
    REPURCHASE_PLAN = "repurchase_plan"
    REPURCHASE_PROGRESS = "repurchase_progress"
    REPURCHASE_COMPLETED = "repurchase_completed"
    REPURCHASE_ADJUSTED = "repurchase_adjusted"
    REPURCHASE_CANCELLED = "repurchase_cancelled"
    PLEDGE_CREATED = "pledge_created"
    PLEDGE_RELEASED = "pledge_released"
    PLEDGE_CHANGED = "pledge_changed"
    UNLOCK_SCHEDULED = "unlock_scheduled"
    UNLOCK_COMPLETED = "unlock_completed"
    REGULATORY_INQUIRY = "regulatory_inquiry"
    INVESTIGATION_OPENED = "investigation_opened"
    WARNING_LETTER = "warning_letter"
    ADMINISTRATIVE_PENALTY = "administrative_penalty"
    DISCIPLINARY_ACTION = "disciplinary_action"
    REGULATORY_MEASURE = "regulatory_measure"
    SHAREHOLDING_CHANGE_PLAN = "shareholding_change_plan"
    SHAREHOLDING_CHANGE_PROGRESS = "shareholding_change_progress"
    SHAREHOLDING_CHANGE_COMPLETED = "shareholding_change_completed"
    SHAREHOLDING_CHANGE_CANCELLED = "shareholding_change_cancelled"
    CASE_FILED = "case_filed"
    CASE_PROGRESS = "case_progress"
    JUDGMENT_OR_AWARD = "judgment_or_award"
    CASE_CLOSED = "case_closed"


@dataclass(frozen=True, slots=True)
class RawDisclosure:
    provider: str
    source_owner: str
    requested_symbol: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class RawEventFact:
    provider: str
    source_owner: str
    requested_symbol: str
    event_family: EventFamily
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class DisclosureDocument:
    symbol: str
    source_owner: str
    source_document_id: str
    title: str
    source_url: str
    source_published_at: datetime
    source_published_precision: str
    known_at: datetime
    ingested_at: datetime
    content_fingerprint: str
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class SourceFact:
    symbol: str
    source_owner: str
    source_fact_id: str
    event_family: EventFamily
    raw_payload: dict[str, Any]
    source_published_at: datetime | None
    known_at: datetime
    ingested_at: datetime
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class Classification:
    event_family: EventFamily | None
    event_type: EventType | None
    status: Literal["classified", "unclassified", "ambiguous", "unsupported"]
    matched_rule: str | None = None


@dataclass(frozen=True, slots=True)
class EventCandidate:
    document_id: UUID
    source_fact_id: UUID | None
    symbol: str
    event_family: EventFamily
    event_type: EventType
    title: str
    source_published_at: datetime
    source_published_precision: str
    known_at: datetime
    event_effective_from: date | None
    event_effective_to: date | None
    event_time_precision: str | None
    extraction_status: Literal["complete", "partial", "invalid"]
    typed_payload: dict[str, Any]
    field_lineage: dict[str, Any]
    event_thread_key: str
    event_version_fingerprint: str
    identity_basis: str


@dataclass(frozen=True, slots=True)
class EventBuildResult:
    status: str
    symbol: str
    received_count: int
    written_count: int
    idempotency_key: str


class EventSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    source_owner: str
    source_document_id: str
    title: str
    source_url: str
    source_published_at: datetime
    source_published_precision: str


class ExistingEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["share_repurchase", "share_pledge", "share_unlock", "regulatory_action"]
    event_type: str


class ShareholderChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["shareholder_change"]
    event_type: Literal[
        "shareholding_change_plan",
        "shareholding_change_progress",
        "shareholding_change_completed",
        "shareholding_change_cancelled",
    ]
    direction: Literal["increase", "decrease"]
    stage: Literal["plan", "progress", "completed", "cancelled"]
    holder_name: str | None = None
    shareholder_name: str | None = None
    holder_type: str | None = None
    plan_reference: str | None = None
    planned_shares: str | None = None
    planned_ratio_total: str | None = None
    completed_shares: str | None = None
    completed_ratio_total: str | None = None


class LitigationArbitrationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["litigation_arbitration"]
    event_type: Literal["case_filed", "case_progress", "judgment_or_award", "case_closed"]
    case_kind: Literal["litigation", "arbitration"]
    case_stage: Literal["filed", "progress", "judgment_or_award", "closed"]
    case_reference: str | None = None
    company_role: str | None = None
    counterparty: str | None = None
    court_or_body: str | None = None
    amount: str | None = None
    currency: str | None = None
    judgment_amount: str | None = None


TypedEventPayload = Annotated[
    ExistingEventPayload | ShareholderChangePayload | LitigationArbitrationPayload,
    Field(discriminator="kind"),
]


class CorporateEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    symbol: str
    canonical_symbol: str
    event_family: EventFamily
    event_type: EventType
    title: str
    event_thread_key: str
    identity_basis: str
    previous_event_id: UUID | None = None
    source_published_at: datetime
    known_at: datetime
    event_effective_from: date | None = None
    event_effective_to: date | None = None
    event_time_precision: str | None = None
    extraction_status: Literal["complete", "partial", "invalid"]
    typed_payload: TypedEventPayload
    field_lineage: dict[str, Any]
    sources: list[EventSourceResponse] = Field(default_factory=list)


class CorporateEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    canonical_symbol: str
    items: list[CorporateEventResponse]
    total: int


class EventThreadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_thread_key: str
    items: list[CorporateEventResponse]
    total: int


class EventRadarItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: CorporateEventResponse
    section: Literal["recent", "upcoming"]
    attention_level: Literal["info", "notice", "important"]
    attention_rule_id: str
    attention_rule_version: str
    attention_reason: str


class EventRadarEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "no_events", "not_built", "building", "failed"]
    freshness: Literal["current", "stale"] | None = None
    source_health: Literal["healthy", "degraded", "unavailable"] | None = None
    coverage_status: Literal["complete", "partial", "unknown"]
    symbol: str
    canonical_symbol: str
    snapshot_id: UUID | None = None
    knowledge_cutoff: datetime | None = None
    generated_at: datetime | None = None
    recent_items: list[EventRadarItemResponse] = Field(default_factory=list)
    upcoming_items: list[EventRadarItemResponse] = Field(default_factory=list)
