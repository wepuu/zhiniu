from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from zhaoniu_api.domain.models import Stock, Watchlist


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    exchange: str
    industry: str | None
    latest_price: Decimal | None
    change_percent: Decimal | None

    @classmethod
    def from_domain(cls, stock: Stock) -> "StockResponse":
        return cls.model_validate(stock)


class StockSearchResponse(BaseModel):
    items: list[StockResponse]
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
