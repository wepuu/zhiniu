from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

CLASSIFIER_VERSION = "corporate-disclosure-classifier-v1"
EXTRACTOR_VERSION = "corporate-event-extractor-v1"
ATTENTION_RULE_VERSION = "event-attention-v1"
RADAR_SCHEMA_VERSION = "event-radar-v1"


class EventFamily(StrEnum):
    SHARE_REPURCHASE = "share_repurchase"
    SHARE_PLEDGE = "share_pledge"
    SHARE_UNLOCK = "share_unlock"
    REGULATORY_ACTION = "regulatory_action"


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
    typed_payload: dict[str, Any]
    field_lineage: dict[str, Any]
    sources: list[EventSourceResponse] = Field(default_factory=list)


class CorporateEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    canonical_symbol: str
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
