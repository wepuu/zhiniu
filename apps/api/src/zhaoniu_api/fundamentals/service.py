import hashlib
from datetime import UTC, date, datetime, time, timedelta

from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.fundamentals.metrics import (
    METRIC_VERSION,
    compute_fundamental_metrics,
    compute_valuation_metrics,
    make_data_version,
)
from zhaoniu_api.fundamentals.models import (
    FinancialReport,
    FundamentalSnapshot,
    ValuationObservation,
)
from zhaoniu_api.fundamentals.normalizer import AKShareFinancialNormalizer
from zhaoniu_api.fundamentals.quality import validate_financial_batch
from zhaoniu_api.market_data.service import SyncResult, make_idempotency_key
from zhaoniu_api.ports.providers import FinancialDataProvider
from zhaoniu_api.ports.repositories import (
    FundamentalRepository,
    StockRepository,
    SyncRunRepository,
)


def _safe_error(exc: Exception) -> str:
    return type(exc).__name__


def _valuation_version(material: list[tuple[date, str, object]]) -> str:
    return hashlib.sha256(repr(material).encode("utf-8")).hexdigest()


class FundamentalResearchService:
    def __init__(
        self,
        *,
        provider: FinancialDataProvider,
        normalizer: AKShareFinancialNormalizer,
        stocks: StockRepository,
        fundamentals: FundamentalRepository,
        runs: SyncRunRepository,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._stocks = stocks
        self._fundamentals = fundamentals
        self._runs = runs

    async def sync_financial_statements(
        self,
        symbol: str,
        *,
        start_year: int,
        force: bool = False,
    ) -> SyncResult:
        resolved = resolve_symbol(symbol)
        if await self._stocks.get(resolved.canonical) is None:
            raise ValueError(f"stock is not present in the master table: {resolved.canonical}")
        requested_start = date(start_year, 1, 1)
        requested_end = date.today()
        key = make_idempotency_key(
            "financial-statements",
            self._provider.name,
            resolved.canonical,
            requested_start,
            requested_end,
            self._normalizer.version,
        )
        if not force and await self._runs.was_successful(key):
            return SyncResult("skipped", 0, 0, key, requested_start, requested_end)
        run_id = await self._runs.start(
            dataset="financial_statements",
            provider=self._provider.name,
            canonical_symbol=resolved.canonical,
            requested_start=requested_start,
            requested_end=requested_end,
            idempotency_key=key,
        )
        received = 0
        try:
            raw = await self._provider.get_financial_statements(resolved.ticker, start_year)
            received = len(raw)
            normalized = self._normalizer.reports(raw)
            valid = validate_financial_batch(normalized, resolved.canonical)
            written = await self._fundamentals.upsert_reports(valid)
            await self.compute_snapshot(resolved.canonical)
            await self._runs.finish(
                run_id,
                status="succeeded",
                received_count=received,
                written_count=written,
                error_summary=None,
                finished_at=datetime.now(UTC),
            )
            return SyncResult("succeeded", received, written, key, requested_start, requested_end)
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

    async def sync_valuations(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        force: bool = False,
    ) -> SyncResult:
        resolved = resolve_symbol(symbol)
        if await self._stocks.get(resolved.canonical) is None:
            raise ValueError(f"stock is not present in the master table: {resolved.canonical}")
        final_end = end or date.today()
        final_start = start or final_end - timedelta(days=365 * 3)
        key = make_idempotency_key(
            "valuations",
            self._provider.name,
            resolved.canonical,
            final_start,
            final_end,
            self._normalizer.version,
        )
        if not force and await self._runs.was_successful(key):
            return SyncResult("skipped", 0, 0, key, final_start, final_end)
        run_id = await self._runs.start(
            dataset="valuations",
            provider=self._provider.name,
            canonical_symbol=resolved.canonical,
            requested_start=final_start,
            requested_end=final_end,
            idempotency_key=key,
        )
        received = 0
        try:
            raw = await self._provider.get_valuation_observations(
                resolved.ticker, final_start, final_end
            )
            received = len(raw)
            observations = self._normalizer.valuations(raw)
            written = await self._fundamentals.upsert_valuations(observations)
            await self.compute_snapshot(resolved.canonical)
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

    async def compute_snapshot(
        self, symbol: str, *, as_of: datetime | None = None, persist: bool = True
    ) -> FundamentalSnapshot:
        canonical = resolve_symbol(symbol).canonical
        effective_as_of = as_of or datetime.now(UTC)
        reports = await self._fundamentals.list_reports(canonical, as_of=effective_as_of, limit=64)
        valuations = await self._fundamentals.list_valuations(
            canonical,
            start=(effective_as_of.date() - timedelta(days=365 * 3)),
            end=effective_as_of.date(),
            metric_codes=None,
            limit=10000,
        )
        report_version = make_data_version(reports)
        valuation_version = _valuation_version(
            [(item.trade_date, item.metric_code, item.value) for item in valuations]
        )
        data_version = hashlib.sha256(f"{report_version}|{valuation_version}".encode()).hexdigest()
        metrics = compute_fundamental_metrics(reports) + compute_valuation_metrics(valuations)
        snapshot = FundamentalSnapshot(
            canonical_symbol=canonical,
            as_of=effective_as_of,
            data_version=data_version,
            metric_version=METRIC_VERSION,
            latest_period_end=max((item.period_end for item in reports), default=None),
            metrics=metrics,
        )
        if persist and reports:
            await self._fundamentals.save_snapshot(snapshot)
        return snapshot

    async def get_snapshot(self, symbol: str, *, as_of: datetime | None) -> FundamentalSnapshot:
        canonical = resolve_symbol(symbol).canonical
        if as_of is None:
            stored = await self._fundamentals.latest_snapshot(canonical, as_of=None)
            if stored is not None:
                return stored
        return await self.compute_snapshot(canonical, as_of=as_of, persist=False)

    async def list_reports(
        self, symbol: str, *, as_of: datetime | None, limit: int
    ) -> list[FinancialReport]:
        return await self._fundamentals.list_reports(
            resolve_symbol(symbol).canonical, as_of=as_of, limit=limit
        )

    async def list_valuations(
        self,
        symbol: str,
        *,
        start: date | None,
        end: date | None,
        metric_codes: tuple[str, ...] | None,
        limit: int,
    ) -> list[ValuationObservation]:
        return await self._fundamentals.list_valuations(
            resolve_symbol(symbol).canonical,
            start=start,
            end=end,
            metric_codes=metric_codes,
            limit=limit,
        )


def end_of_day_utc(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)
