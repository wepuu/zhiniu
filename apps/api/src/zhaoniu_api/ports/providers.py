from datetime import date
from typing import Any, Protocol

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


class RawFinancialStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    requested_symbol: str = Field(pattern=r"^[0-9]{6}$")
    statement_type: str
    payload: dict[str, object]


class RawValuationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    requested_symbol: str = Field(pattern=r"^[0-9]{6}$")
    metric_code: str
    payload: dict[str, object]


class MarketDataProvider(Protocol):
    name: str

    async def get_stock_master(self) -> list[RawStock]: ...

    async def get_daily_bars(self, symbol: str, start: date, end: date) -> list[RawDailyBar]: ...


class FinancialDataProvider(Protocol):
    name: str

    async def get_financial_statements(
        self, symbol: str, start_year: int
    ) -> list[RawFinancialStatement]: ...

    async def get_valuation_observations(
        self, symbol: str, start: date, end: date
    ) -> list[RawValuationObservation]: ...


class LLMUsage(BaseModel):
    task_type: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_microunits: int | None = None
    status: str


class LLMStructuredResponse(BaseModel):
    data: dict[str, object]
    usage: LLMUsage
    finish_reason: str | None = None


class LLMGatewayError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LLMGateway(Protocol):
    def supports_structured_output(self, model: str) -> bool: ...

    async def generate_structured(
        self,
        *,
        model: str,
        task_type: str,
        system_prompt: str,
        input_data: dict[str, object],
        response_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> LLMStructuredResponse: ...
