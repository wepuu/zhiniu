from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema

from zhaoniu_api.domain.models import Stock, Watchlist

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+(?:\.[0-9]+)?$"}),
]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    canonical_symbol: str
    name: str
    exchange: str
    board: str
    asset_type: str
    list_date: date | None
    status: str
    industry: str | None
    latest_price: DecimalString | None
    change_percent: DecimalString | None
    latest_trade_date: date | None
    source: str | None
    collected_at: datetime | None

    @classmethod
    def from_domain(cls, stock: Stock) -> "StockResponse":
        return cls.model_validate(stock)


class StockSearchResponse(BaseModel):
    items: list[StockResponse]
    total: int


class DailyBarResponse(BaseModel):
    trade_date: date
    adjust_type: str
    open: DecimalString
    high: DecimalString
    low: DecimalString
    close: DecimalString
    pre_close: DecimalString | None
    volume: int
    amount: DecimalString
    pct_change: DecimalString | None
    source: str
    collected_at: datetime


class DailyBarListResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    adjust: str
    items: list[DailyBarResponse]
    total: int


class WatchlistItemResponse(BaseModel):
    symbol: str
    added_at: datetime


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    items: list[WatchlistItemResponse]

    @classmethod
    def from_domain(cls, watchlist: Watchlist) -> "WatchlistResponse":
        return cls(
            id=watchlist.id,
            name=watchlist.name,
            items=[
                WatchlistItemResponse(symbol=i.symbol, added_at=i.added_at) for i in watchlist.items
            ],
        )


class CreateWatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class AddWatchlistItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(pattern=r"^[0-9A-Z.]{1,16}$")
