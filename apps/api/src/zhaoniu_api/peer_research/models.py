from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

PEER_SCHEMA_VERSION = "peer-benchmark-v1"
PEER_PRODUCER_VERSION = "peer-engine-v1"
PRIMARY_TAXONOMY_CODE = "akshare_dev_industry"
PRIMARY_TAXONOMY_VERSION = "phase6-dev-v1"


class PeerComparisonStatus(StrEnum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED_TEMPLATE = "unsupported_template"
    MISSING_INDUSTRY = "missing_industry"
    MISSING_METRIC = "missing_metric"
    INCOMPARABLE_BASIS = "incomparable_basis"
    INSUFFICIENT_PEERS = "insufficient_peers"
    INVALID_INPUTS = "invalid_inputs"
    NOT_BUILT = "not_built"


class PeerMetricKind(StrEnum):
    FUNDAMENTAL = "fundamental"
    VALUATION = "valuation"


@dataclass(frozen=True, slots=True)
class IndustryTaxonomy:
    code: str
    name: str
    version: str
    source: str
    source_reference: str
    commercial_use_status: str
    redistribution_status: str
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class Industry:
    taxonomy_code: str
    taxonomy_version: str
    code: str
    name: str
    level: int
    parent_code: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class IndustryMembership:
    symbol: str
    industry_code: str
    taxonomy_code: str
    taxonomy_version: str
    source: str
    source_reference: str
    known_at: datetime
    ingested_at: datetime
    valid_from: date | None = None
    valid_to: date | None = None
    lineage_hash: str = ""
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class PeerUniverse:
    symbol: str
    taxonomy_code: str
    taxonomy_version: str
    industry_code: str | None
    industry_name: str | None
    peer_symbols: tuple[str, ...]
    peer_universe_fingerprint: str
    status: PeerComparisonStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ComparableMetricInput:
    symbol: str
    metric_code: str
    value: Decimal
    unit: str
    period_end: date | None
    fiscal_period: str | None
    basis: str
    metric_version: str
    known_at: datetime | None
    source_id: UUID
    source_kind: PeerMetricKind


@dataclass(frozen=True, slots=True)
class PeerBenchmarkResult:
    metric_code: str
    metric_kind: PeerMetricKind
    status: PeerComparisonStatus
    company_input: ComparableMetricInput | None
    peer_inputs: tuple[ComparableMetricInput, ...]
    median: Decimal | None = None
    p25: Decimal | None = None
    p75: Decimal | None = None
    numeric_percentile: Decimal | None = None
    numeric_rank_desc: int | None = None
    sample_size: int = 0
    excluded_invalid_value_count: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PeerBuildResult:
    status: str
    symbol: str
    industry_code: str | None
    peer_count: int
    comparison_count: int
    idempotency_key: str


class IndustryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_code: str
    taxonomy_version: str
    industry_code: str
    industry_name: str
    source: str
    source_reference: str
    commercial_use_status: str
    redistribution_status: str


class PeerStockResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: str
    issuer_type: str


class PeerUniverseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    canonical_symbol: str
    status: PeerComparisonStatus
    reason: str | None = None
    industry: IndustryResponse | None = None
    peer_universe_fingerprint: str | None = None
    sample_size: int = 0
    stocks: list[PeerStockResponse] = Field(default_factory=list)


class PeerBenchmarkEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_snapshot_id: UUID | None
    company_source_kind: PeerMetricKind | None
    company_source_id: UUID | None
    peer_input_count: int
    peer_source_ids: list[UUID]
    excluded_invalid_value_count: int = 0
    knowledge_cutoff: datetime


class PeerMetricComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_code: str
    metric_kind: PeerMetricKind
    dimension: str
    status: PeerComparisonStatus
    reason: str | None = None
    company_value: Decimal | None = None
    unit: str | None = None
    period_end: date | None = None
    fiscal_period: str | None = None
    basis: str | None = None
    peer_median: Decimal | None = None
    peer_p25: Decimal | None = None
    peer_p75: Decimal | None = None
    numeric_percentile: Decimal | None = None
    numeric_rank_desc: int | None = None
    sample_size: int = 0
    evidence: PeerBenchmarkEvidenceSummary


class PeerComparisonEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "ready",
        "not_built",
        "unsupported_template",
        "missing_industry",
        "insufficient_peers",
    ]
    symbol: str
    canonical_symbol: str
    industry: IndustryResponse | None = None
    peer_universe_fingerprint: str | None = None
    knowledge_cutoff: datetime | None = None
    items: list[PeerMetricComparisonResponse] = Field(default_factory=list)
    total: int = 0

