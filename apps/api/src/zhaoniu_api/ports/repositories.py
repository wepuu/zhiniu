from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from zhaoniu_api.domain.models import DailyBar, Stock, Watchlist
from zhaoniu_api.fundamentals.models import (
    FinancialReport,
    FundamentalSnapshot,
    ValuationObservation,
)
from zhaoniu_api.research.models import (
    FundamentalMetricPoint,
    ResearchObservation,
    ResearchRunLease,
    ResearchSnapshotDocument,
)


class StockRepository(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[Stock]: ...

    async def get(self, symbol: str) -> Stock | None: ...

    async def upsert_many(self, stocks: list[Stock]) -> int: ...


class DailyBarRepository(Protocol):
    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]: ...

    async def latest_date(self, canonical_symbol: str) -> date | None: ...

    async def upsert_many(self, bars: list[DailyBar]) -> int: ...


class FundamentalRepository(Protocol):
    async def upsert_reports(self, reports: list[FinancialReport]) -> int: ...

    async def list_reports(
        self,
        canonical_symbol: str,
        *,
        as_of: datetime | None,
        limit: int,
    ) -> list[FinancialReport]: ...

    async def save_snapshot(self, snapshot: FundamentalSnapshot) -> int: ...

    async def latest_snapshot(
        self, canonical_symbol: str, *, as_of: datetime | None
    ) -> FundamentalSnapshot | None: ...

    async def upsert_valuations(self, observations: list[ValuationObservation]) -> int: ...

    async def list_valuations(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        metric_codes: tuple[str, ...] | None,
        limit: int,
    ) -> list[ValuationObservation]: ...


class SyncRunRepository(Protocol):
    async def was_successful(self, idempotency_key: str) -> bool: ...

    async def start(
        self,
        *,
        dataset: str,
        provider: str,
        canonical_symbol: str | None,
        requested_start: date | None,
        requested_end: date | None,
        idempotency_key: str,
    ) -> str: ...

    async def finish(
        self,
        run_id: str,
        *,
        status: str,
        received_count: int,
        written_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None: ...


class ResearchRepository(Protocol):
    async def upsert_metric_points(self, points: list[FundamentalMetricPoint]) -> int: ...

    async def find_snapshot(
        self,
        canonical_symbol: str,
        *,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchSnapshotDocument | None: ...

    async def latest_research_snapshot(
        self, canonical_symbol: str
    ) -> ResearchSnapshotDocument | None: ...

    async def save_research_snapshot(
        self,
        snapshot: ResearchSnapshotDocument,
        observations: list[ResearchObservation],
    ) -> None: ...

    async def list_research_observations(
        self, canonical_symbol: str, *, limit: int
    ) -> tuple[UUID | None, list[ResearchObservation]]: ...

    async def get_research_observation(
        self, canonical_symbol: str, observation_id: UUID
    ) -> ResearchObservation | None: ...

    async def acquire_research_run(
        self,
        *,
        canonical_symbol: str,
        idempotency_key: str,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchRunLease: ...

    async def finish_research_run(
        self,
        run_id: UUID,
        *,
        status: str,
        snapshot_id: UUID | None,
        observation_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None: ...


class WatchlistRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Watchlist]: ...

    async def create(self, watchlist: Watchlist) -> Watchlist: ...

    async def get_owned(self, watchlist_id: UUID, user_id: UUID) -> Watchlist | None: ...

    async def save(self, watchlist: Watchlist) -> Watchlist: ...
