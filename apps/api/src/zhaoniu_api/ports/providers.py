from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class RawStock(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    payload: dict[str, object]


class RawDailyBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    requested_symbol: str = Field(pattern=r"^[0-9]{6}$")
    payload: dict[str, object]


class MarketDataProvider(Protocol):
    name: str

    async def get_stock_master(self) -> list[RawStock]: ...

    async def get_daily_bars(self, symbol: str, start: date, end: date) -> list[RawDailyBar]: ...


class LLMUsage(BaseModel):
    task_type: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_microunits: int | None = None
    status: str


class LLMGateway(Protocol):
    async def generate_structured(
        self, *, task_type: str, input_data: dict[str, object], schema_name: str
    ) -> tuple[dict[str, object], LLMUsage]: ...
