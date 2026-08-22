from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

QuestionKey = Literal[
    "recent_research_changes",
    "fundamental_changes",
    "corporate_event_context",
    "peer_position_context",
]


class CitedExplanationText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    evidence_refs: list[str] = Field(min_length=1, max_length=4)


class ExplanationInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus_key: str = Field(min_length=1, max_length=64)
    explanation: CitedExplanationText


class ResearchExplanationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["research-explanation-v1"]
    question_key: QuestionKey
    headline: CitedExplanationText
    summary: list[CitedExplanationText] = Field(min_length=2, max_length=4)
    interpretations: list[ExplanationInterpretation] = Field(min_length=1, max_length=4)
    attention_items: list[CitedExplanationText] = Field(default_factory=list, max_length=4)


class ExplanationEvidence(BaseModel):
    evidence_id: str
    source_kind: Literal["fundamental", "corporate_event", "peer"]
    source_id: UUID
    title: str
    summary: str
    attention_level: str
    known_at: datetime


class ExplanationOutput(BaseModel):
    output_id: UUID
    run_id: UUID
    symbol: str
    question_key: QuestionKey
    provider_display_name: str
    model_display_name: str
    knowledge_cutoff: datetime
    generated_at: datetime
    freshness: Literal["current", "stale"]
    content: ResearchExplanationV1
    evidence_index: list[ExplanationEvidence]
    limitations: list[str]
    ai_generated: Literal[True] = True


class ExplanationRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_key: QuestionKey
    client_request_id: UUID


class ExplanationRequestResponse(BaseModel):
    id: UUID
    symbol: str
    question_key: QuestionKey
    status: Literal["pending", "building", "ready", "failed"]
    error_code: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    output: ExplanationOutput | None = None


class ExplanationQuestion(BaseModel):
    key: QuestionKey
    label: str
    description: str
    coverage: Literal["available", "insufficient"]


class ExplanationQuestionCatalog(BaseModel):
    symbol: str
    enabled: bool
    access: Literal["available", "contact_support", "disabled"]
    remaining_today: int
    daily_limit: int
    support_contact_url: str | None = None
    questions: list[ExplanationQuestion]


class ExplanationContext(BaseModel):
    context_version: Literal["research-explanation-context-v1"]
    symbol: str
    question_key: QuestionKey
    snapshot_id: UUID
    knowledge_cutoff: datetime
    facts: list[ExplanationEvidence] = Field(min_length=1, max_length=12)
