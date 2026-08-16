from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    industry: str | None = None
    latest_price: Decimal | None = None
    change_percent: Decimal | None = None


@dataclass(slots=True)
class WatchlistItem:
    symbol: str
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Watchlist:
    user_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    items: list[WatchlistItem] = field(default_factory=list)

    def add(self, symbol: str) -> None:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        if all(item.symbol != normalized for item in self.items):
            self.items.append(WatchlistItem(symbol=normalized))
