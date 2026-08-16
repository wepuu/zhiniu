from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class RawQuote(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    payload: dict[str, object]


class CanonicalQuote(BaseModel):
    symbol: str
    trading_date: date
    close: float
    currency: str = "CNY"


class MarketDataProvider(Protocol):
    async def get_quote(self, symbol: str) -> RawQuote: ...

    async def get_daily_bars(self, symbol: str, start: date, end: date) -> list[RawQuote]: ...

    async def get_financials(self, symbol: str) -> list[dict[str, object]]: ...


class QuoteNormalizer(Protocol):
    def normalize(self, raw: RawQuote) -> CanonicalQuote: ...


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
