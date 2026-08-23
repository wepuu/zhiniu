import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.market_data.errors import safe_market_error_code
from zhaoniu_api.market_data.normalizer import AKShareNormalizer
from zhaoniu_api.market_data.quality import validate_daily_bar_batch
from zhaoniu_api.ports.providers import MarketDataProvider
from zhaoniu_api.ports.repositories import (
    DailyBarRepository,
    StockRepository,
    SyncRunRepository,
)


@dataclass(frozen=True, slots=True)
class SyncResult:
    status: str
    received_count: int
    written_count: int
    idempotency_key: str
    requested_start: date | None = None
    requested_end: date | None = None


def make_idempotency_key(*parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    return safe_market_error_code(exc)


class MarketDataSyncService:
    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        normalizer: AKShareNormalizer,
        stocks: StockRepository,
        bars: DailyBarRepository,
        runs: SyncRunRepository,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._stocks = stocks
        self._bars = bars
        self._runs = runs

    async def sync_stock_master(
        self, *, force: bool = False, today: date | None = None
    ) -> SyncResult:
        current_date = today or date.today()
        key = make_idempotency_key("stock-master", self._provider.name, current_date)
        if not force and await self._runs.was_successful(key):
            return SyncResult("skipped", 0, 0, key)
        run_id = await self._runs.start(
            dataset="stock_master",
            provider=self._provider.name,
            canonical_symbol=None,
            requested_start=current_date,
            requested_end=current_date,
            idempotency_key=key,
        )
        received = 0
        try:
            raw = await self._provider.get_stock_master()
            received = len(raw)
            normalized = self._normalizer.stocks(raw)
            identities = [stock.canonical_symbol for stock in normalized]
            if len(identities) != len(set(identities)):
                raise ValueError("stock master contains duplicate canonical symbols")
            written = await self._stocks.upsert_many(normalized)
            await self._runs.finish(
                run_id,
                status="succeeded",
                received_count=received,
                written_count=written,
                error_summary=None,
                finished_at=datetime.now(UTC),
            )
            return SyncResult("succeeded", received, written, key)
        except Exception as exc:
            await self._runs.finish(
                run_id,
                status="failed",
                received_count=received,
                written_count=0,
                error_summary=_safe_error(exc),
                finished_at=datetime.now(UTC),
            )
            raise

    async def sync_daily_bars(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        force: bool = False,
    ) -> SyncResult:
        resolved = resolve_symbol(symbol)
        known = await self._stocks.get(resolved.canonical)
        if known is None:
            raise ValueError(f"stock is not present in the master table: {resolved.canonical}")
        final_end = end or date.today()
        latest = await self._bars.latest_date(resolved.canonical)
        final_start = start or (
            latest + timedelta(days=1) if latest else final_end - timedelta(days=365)
        )
        if final_start > final_end:
            key = make_idempotency_key(
                "daily-bars", self._provider.name, resolved.canonical, final_start, final_end
            )
            return SyncResult("up-to-date", 0, 0, key, final_start, final_end)
        key = make_idempotency_key(
            "daily-bars", self._provider.name, resolved.canonical, final_start, final_end, "none"
        )
        if not force and await self._runs.was_successful(key):
            return SyncResult("skipped", 0, 0, key, final_start, final_end)
        run_id = await self._runs.start(
            dataset="daily_bars",
            provider=self._provider.name,
            canonical_symbol=resolved.canonical,
            requested_start=final_start,
            requested_end=final_end,
            idempotency_key=key,
        )
        received = 0
        try:
            raw = await self._provider.get_daily_bars(resolved.ticker, final_start, final_end)
            received = len(raw)
            normalized = self._normalizer.daily_bars(raw)
            valid = validate_daily_bar_batch(normalized, resolved.canonical)
            written = await self._bars.upsert_many(valid)
            await self._runs.finish(
                run_id,
                status="succeeded",
                received_count=received,
                written_count=written,
                error_summary=None,
                finished_at=datetime.now(UTC),
            )
            return SyncResult("succeeded", received, written, key, final_start, final_end)
        except Exception as exc:
            await self._runs.finish(
                run_id,
                status="failed",
                received_count=received,
                written_count=0,
                error_summary=_safe_error(exc),
                finished_at=datetime.now(UTC),
            )
            raise
