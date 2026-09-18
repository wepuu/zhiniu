from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any, Literal

from zhaoniu_api.market_data.errors import DataNormalizationError
from zhaoniu_api.ports.providers import RawTradingSession

CN_TZ = timezone(timedelta(hours=8))
CALENDAR_SOURCE = "akshare_sina"
CALENDAR_PROVIDER = "akshare_sina_calendar"
CALENDAR_VERSION = "sina-trading-calendar-v1"
SSE = "SSE"
SZSE = "SZSE"
CALENDAR_HEALTH_MAX_AGE = timedelta(hours=36)
CalendarHealthStatus = Literal["healthy", "stale", "unknown"]


def calendar_health_status(
    checked_at: datetime | None,
    *,
    now: datetime,
) -> CalendarHealthStatus:
    if checked_at is None:
        return "unknown"
    checked = (
        checked_at.replace(tzinfo=UTC)
        if checked_at.tzinfo is None
        else checked_at.astimezone(UTC)
    )
    moment = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    age = moment - checked
    if age < timedelta(0):
        return "unknown"
    return "healthy" if age <= CALENDAR_HEALTH_MAX_AGE else "stale"


@dataclass(frozen=True, slots=True)
class TradingSession:
    exchange: str
    trade_date: date
    is_open: bool
    session_open_at: datetime | None
    session_close_at: datetime | None
    calendar_version: str
    source: str
    known_at: datetime
    ingested_at: datetime
    lineage_hash: str


class AKShareTradingCalendarNormalizer:
    """Normalize Sina's free AKShare date list into exchange-session facts."""

    def sessions(
        self,
        rows: Iterable[RawTradingSession],
        *,
        start: date,
        end: date,
        ingested_at: datetime | None = None,
    ) -> list[TradingSession]:
        if start > end:
            raise DataNormalizationError("calendar range is invalid")
        ingested = ingested_at or datetime.now(UTC)
        normalized: list[TradingSession] = []
        seen: set[tuple[str, date]] = set()
        for row in rows:
            trade_date = _parse_date(row.payload.get("trade_date") or row.payload.get("date"))
            if trade_date < start or trade_date > end:
                continue
            identity = (row.exchange, trade_date)
            if identity in seen:
                raise DataNormalizationError("calendar contains duplicate exchange dates")
            seen.add(identity)
            is_open = _parse_bool(row.payload.get("is_open"), default=True)
            session_open_at = _session_time(trade_date, time(9, 30)) if is_open else None
            session_close_at = _session_time(trade_date, time(15, 0)) if is_open else None
            source = row.provider or CALENDAR_SOURCE
            lineage_hash = _lineage_hash(
                {
                    "exchange": row.exchange,
                    "trade_date": trade_date.isoformat(),
                    "is_open": is_open,
                    "calendar_version": CALENDAR_VERSION,
                    "source": source,
                }
            )
            normalized.append(
                TradingSession(
                    exchange=row.exchange,
                    trade_date=trade_date,
                    is_open=is_open,
                    session_open_at=session_open_at,
                    session_close_at=session_close_at,
                    calendar_version=CALENDAR_VERSION,
                    source=source,
                    known_at=ingested,
                    ingested_at=ingested,
                    lineage_hash=lineage_hash,
                )
            )
        return sorted(normalized, key=lambda item: (item.exchange, item.trade_date))


def _parse_date(value: object | None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        raise DataNormalizationError("calendar row is missing trade_date")
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise DataNormalizationError("calendar row has invalid trade_date") from exc


def _parse_bool(value: object | None, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "open", "yes"}:
        return True
    if normalized in {"0", "false", "closed", "no"}:
        return False
    raise DataNormalizationError("calendar row has invalid is_open")


def _session_time(trade_date: date, value: time) -> datetime:
    return datetime.combine(trade_date, value, tzinfo=CN_TZ).astimezone(UTC)


def _lineage_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
