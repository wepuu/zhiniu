from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SourceKind = Literal["fundamental", "peer", "corporate_event"]
AttentionLevel = Literal["info", "notice", "important"]


class TimelineDisplayValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class TimelineSourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SourceKind
    id: UUID
    evidence_path: str


class EventThreadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_key: str
    version_count: int = Field(ge=1)
    current_index: int = Field(ge=1)


class CompanyTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    symbol: str
    source_kind: SourceKind
    signal_family: str
    signal_type: str
    attention_level: AttentionLevel
    known_at: datetime
    effective_on: date | None = None
    title: str
    summary: str
    display_values: list[TimelineDisplayValue] = Field(default_factory=list)
    source_artifact: TimelineSourceArtifact
    event_thread: EventThreadSummary | None = None


class TimelineUpcomingEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    title: str
    event_family: str
    attention_level: AttentionLevel
    known_at: datetime
    effective_on: date


class CompanyTimelineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_30d_total: int = 0
    fundamental_count: int = 0
    peer_count: int = 0
    corporate_event_count: int = 0
    important_count: int = 0
    upcoming_count: int = 0


class CompanyTimelineCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fundamental: Literal["ready", "not_built"]
    peer: Literal["ready", "not_built"]
    corporate_event: Literal["ready", "not_built"]


class CompanyTimelineEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "empty", "partial", "not_built"]
    symbol: str
    canonical_symbol: str
    query_cutoff: datetime
    latest_known_at: datetime | None = None
    summary: CompanyTimelineSummary
    items: list[CompanyTimelineItem] = Field(default_factory=list)
    upcoming_events: list[TimelineUpcomingEvent] = Field(default_factory=list)
    coverage: CompanyTimelineCoverage
    next_cursor: str | None = None
