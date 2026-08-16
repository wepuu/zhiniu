from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResearchChange(BaseModel):
    metric: str
    direction: str
    description: str


class StructuredResearch(BaseModel):
    """Contract rendered by the UI; an LLM never chooses presentation structure."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    changes: list[ResearchChange]
    dimensions: dict[str, str]
    risks: list[str]
    events: list[str]
    evidence_ids: list[str]


class ResearchSnapshotKey(BaseModel):
    symbol: str
    data_version: str
    research_template_version: str
    model_version: str
    generated_at: datetime
