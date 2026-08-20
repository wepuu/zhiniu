from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class Exchange(StrEnum):
    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"


class Board(StrEnum):
    MAIN = "main"
    SME = "sme"
    CHINEXT = "chinext"
    STAR = "star"
    BEIJING = "beijing"
    UNKNOWN = "unknown"


class AdjustType(StrEnum):
    NONE = "none"


class IssuerType(StrEnum):
    GENERAL = "general"
    BANK = "bank"
    OTHER_FINANCIAL = "other_financial"


@dataclass(frozen=True, slots=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    industry: str | None = None
    latest_price: Decimal | None = None
    change_percent: Decimal | None = None
    canonical_symbol: str | None = None
    board: str = Board.UNKNOWN
    asset_type: str = "stock"
    list_date: date | None = None
    status: str = "listed"
    issuer_type: str = IssuerType.GENERAL
    latest_trade_date: date | None = None
    source: str | None = None
    collected_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.canonical_symbol is None:
            object.__setattr__(self, "canonical_symbol", resolve_symbol(self.symbol).canonical)


@dataclass(frozen=True, slots=True)
class ResolvedSymbol:
    ticker: str
    exchange: Exchange
    board: Board

    @property
    def canonical(self) -> str:
        suffix = {Exchange.SSE: "SH", Exchange.SZSE: "SZ", Exchange.BSE: "BJ"}[self.exchange]
        return f"{self.ticker}.{suffix}"


def resolve_symbol(value: str) -> ResolvedSymbol:
    normalized = value.strip().upper()
    suffix: str | None = None
    if "." in normalized:
        ticker, suffix = normalized.rsplit(".", 1)
    else:
        ticker = normalized
    if len(ticker) != 6 or not ticker.isdigit():
        raise ValueError("A-share symbol must contain exactly six digits")

    if ticker.startswith(("688", "689")):
        inferred = ResolvedSymbol(ticker, Exchange.SSE, Board.STAR)
    elif ticker.startswith("30"):
        inferred = ResolvedSymbol(ticker, Exchange.SZSE, Board.CHINEXT)
    elif ticker.startswith("002"):
        inferred = ResolvedSymbol(ticker, Exchange.SZSE, Board.SME)
    elif ticker.startswith("6"):
        inferred = ResolvedSymbol(ticker, Exchange.SSE, Board.MAIN)
    elif ticker.startswith(("000", "001", "003")):
        inferred = ResolvedSymbol(ticker, Exchange.SZSE, Board.MAIN)
    elif ticker.startswith(("4", "8", "92")):
        inferred = ResolvedSymbol(ticker, Exchange.BSE, Board.BEIJING)
    else:
        raise ValueError(f"unsupported A-share symbol: {ticker}")

    expected_suffix = {Exchange.SSE: "SH", Exchange.SZSE: "SZ", Exchange.BSE: "BJ"}[
        inferred.exchange
    ]
    if suffix is not None and suffix not in {expected_suffix, inferred.exchange.value}:
        raise ValueError(f"symbol suffix {suffix} does not match ticker {ticker}")
    return inferred


@dataclass(frozen=True, slots=True)
class DailyBar:
    canonical_symbol: str
    trade_date: date
    adjust_type: AdjustType
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    pre_close: Decimal | None
    volume: int
    amount: Decimal
    source: str
    collected_at: datetime

    @property
    def pct_change(self) -> Decimal | None:
        if self.pre_close is None or self.pre_close == 0:
            return None
        return ((self.close - self.pre_close) / self.pre_close * Decimal("100")).quantize(
            Decimal("0.0001")
        )


@dataclass(slots=True)
class WatchlistItem:
    symbol: str
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Watchlist:
    user_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    is_default: bool = False
    items: list[WatchlistItem] = field(default_factory=list)

    def add(self, symbol: str) -> None:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        if all(item.symbol != normalized for item in self.items):
            self.items.append(WatchlistItem(symbol=normalized))

    def remove(self, symbol: str) -> bool:
        normalized = symbol.strip().upper()
        before = len(self.items)
        self.items = [item for item in self.items if item.symbol != normalized]
        return len(self.items) != before


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: UUID
    email: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None
    email_verified_at: datetime | None = None
    password_changed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UserSession:
    id: UUID
    user_id: UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None = None
    is_current: bool = False
