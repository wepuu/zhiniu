from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SourceKind = Literal["fundamental", "peer", "corporate_event"]
AttentionLevel = Literal["info", "notice", "important"]


class FeedSignalResponse(BaseModel):
    id: UUID
    symbol: str
    stock_name: str
    source_kind: SourceKind
    signal_family: str
    signal_type: str
    attention_level: AttentionLevel
    known_at: datetime
    effective_on: date | None = None
    title: str
    summary: str
    display_payload: dict[str, object]
    evidence_path: str
    ai_status: Literal["ready", "disabled", "not_built"]


class FeedSection(BaseModel):
    items: list[FeedSignalResponse]
    total: int


class ResearchFeedResponse(BaseModel):
    query_cutoff: datetime
    today: FeedSection
    recent: FeedSection
    next_cursor: str | None = None


class SourceCoverage(BaseModel):
    fundamental: str
    peer: str
    corporate_event: str
    ai: str


class WatchlistCoverageItem(BaseModel):
    symbol: str
    stock_name: str
    coverage: SourceCoverage


class WatchlistCoverageResponse(BaseModel):
    items: list[WatchlistCoverageItem]
    total: int


class AlertSettingsResponse(BaseModel):
    enabled: bool
    minimum_attention: AttentionLevel
    fundamental_enabled: bool
    peer_enabled: bool
    corporate_event_enabled: bool
    settings_version: int
    updated_at: datetime


class AlertSettingsUpdate(BaseModel):
    enabled: bool
    minimum_attention: AttentionLevel
    fundamental_enabled: bool
    peer_enabled: bool
    corporate_event_enabled: bool


class AlertDeliveryResponse(BaseModel):
    id: UUID
    signal: FeedSignalResponse
    created_at: datetime
    read_at: datetime | None = None


class AlertListResponse(BaseModel):
    items: list[AlertDeliveryResponse]
    unread_count: int
    next_cursor: str | None = None


class AlertSummaryResponse(BaseModel):
    unread_count: int = Field(ge=0)


class ProjectionResult(BaseModel):
    status: Literal["succeeded", "skipped"]
    projected_signal_ids: list[UUID]
    peer_observation_count: int = 0


class DispatchResult(BaseModel):
    status: Literal["succeeded", "skipped"]
    matched_user_count: int = 0
    delivery_count: int = 0
