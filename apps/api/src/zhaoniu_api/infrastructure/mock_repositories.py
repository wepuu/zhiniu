from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from zhaoniu_api.ai_research.models import (
    AIResearchOutputDocument,
    AIResearchRunLease,
    AIResearchRunView,
    LLMCallAudit,
)
from zhaoniu_api.domain.models import DailyBar, Stock, Watchlist, resolve_symbol
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


class InMemoryStockRepository:
    def __init__(self) -> None:
        self._stocks = {
            "600519": Stock(
                "600519", "贵州茅台", "SSE", "白酒", Decimal("1438.20"), Decimal("0.62")
            ),
            "000001": Stock(
                "000001",
                "平安银行",
                "SZSE",
                "银行",
                Decimal("11.28"),
                Decimal("-0.18"),
                issuer_type="bank",
            ),
            "300750": Stock(
                "300750", "宁德时代", "SZSE", "电池", Decimal("286.35"), Decimal("1.24")
            ),
        }

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        needle = query.strip().lower()
        return [
            stock
            for stock in self._stocks.values()
            if needle in stock.symbol.lower() or needle in stock.name.lower()
        ][:limit]

    async def get(self, symbol: str) -> Stock | None:
        try:
            return self._stocks.get(resolve_symbol(symbol).ticker)
        except ValueError:
            return None

    async def upsert_many(self, stocks: list[Stock]) -> int:
        self._stocks.update({stock.symbol: stock for stock in stocks})
        return len(stocks)


class InMemoryDailyBarRepository:
    def __init__(self, bars: list[DailyBar] | None = None) -> None:
        self._bars = bars or []

    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]:
        matches = [
            bar
            for bar in self._bars
            if bar.canonical_symbol == canonical_symbol
            and (start is None or bar.trade_date >= start)
            and (end is None or bar.trade_date <= end)
        ]
        return sorted(matches, key=lambda item: item.trade_date)[-limit:]

    async def latest_date(self, canonical_symbol: str) -> date | None:
        dates = [bar.trade_date for bar in self._bars if bar.canonical_symbol == canonical_symbol]
        return max(dates) if dates else None

    async def upsert_many(self, bars: list[DailyBar]) -> int:
        identities = {(bar.canonical_symbol, bar.trade_date, bar.adjust_type) for bar in bars}
        self._bars = [
            bar
            for bar in self._bars
            if (bar.canonical_symbol, bar.trade_date, bar.adjust_type) not in identities
        ] + bars
        return len(bars)


class InMemoryFundamentalRepository:
    def __init__(
        self,
        reports: list[FinancialReport] | None = None,
        valuations: list[ValuationObservation] | None = None,
    ) -> None:
        self._reports = reports or []
        self._valuations = valuations or []
        self._snapshots: list[FundamentalSnapshot] = []

    async def upsert_reports(self, reports: list[FinancialReport]) -> int:
        identities = {
            (
                item.canonical_symbol,
                item.provider,
                item.period_end,
                item.statement_scope,
                item.normalizer_version,
                item.payload_checksum,
            )
            for item in self._reports
        }
        inserted = 0
        for report in reports:
            identity = (
                report.canonical_symbol,
                report.provider,
                report.period_end,
                report.statement_scope,
                report.normalizer_version,
                report.payload_checksum,
            )
            if identity not in identities:
                self._reports.append(report)
                identities.add(identity)
                inserted += 1
        return inserted

    async def list_reports(
        self,
        canonical_symbol: str,
        *,
        as_of: datetime | None,
        limit: int,
    ) -> list[FinancialReport]:
        candidates = [
            item
            for item in self._reports
            if item.canonical_symbol == canonical_symbol
            and (as_of is None or item.known_at <= as_of)
        ]
        selected: list[FinancialReport] = []
        seen: set[tuple[date, str]] = set()
        for item in sorted(
            candidates, key=lambda report: (report.period_end, report.known_at), reverse=True
        ):
            identity = (item.period_end, item.statement_scope)
            if identity not in seen:
                selected.append(item)
                seen.add(identity)
            if len(selected) >= limit:
                break
        return selected

    async def save_snapshot(self, snapshot: FundamentalSnapshot) -> int:
        self._snapshots = [
            item
            for item in self._snapshots
            if not (
                item.canonical_symbol == snapshot.canonical_symbol
                and item.data_version == snapshot.data_version
                and item.metric_version == snapshot.metric_version
            )
        ]
        self._snapshots.append(snapshot)
        return len(snapshot.metrics)

    async def latest_snapshot(
        self, canonical_symbol: str, *, as_of: datetime | None
    ) -> FundamentalSnapshot | None:
        candidates = [
            item
            for item in self._snapshots
            if item.canonical_symbol == canonical_symbol and (as_of is None or item.as_of <= as_of)
        ]
        return max(candidates, key=lambda item: item.as_of, default=None)

    async def upsert_valuations(self, observations: list[ValuationObservation]) -> int:
        identities = {
            (item.canonical_symbol, item.trade_date, item.metric_code, item.provider)
            for item in observations
        }
        self._valuations = [
            item
            for item in self._valuations
            if (item.canonical_symbol, item.trade_date, item.metric_code, item.provider)
            not in identities
        ] + observations
        return len(observations)

    async def list_valuations(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        metric_codes: tuple[str, ...] | None,
        limit: int,
    ) -> list[ValuationObservation]:
        matches = [
            item
            for item in self._valuations
            if item.canonical_symbol == canonical_symbol
            and (start is None or item.trade_date >= start)
            and (end is None or item.trade_date <= end)
            and (not metric_codes or item.metric_code in metric_codes)
        ]
        return sorted(matches, key=lambda item: item.trade_date)[-limit:]


class InMemoryResearchRepository:
    def __init__(self) -> None:
        self.metric_points: dict[str, FundamentalMetricPoint] = {}
        self.snapshots: list[ResearchSnapshotDocument] = []
        self.observations: dict[UUID, ResearchObservation] = {}
        self.runs: dict[str, dict[str, object]] = {}

    async def upsert_metric_points(self, points: list[FundamentalMetricPoint]) -> int:
        before = len(self.metric_points)
        self.metric_points.update({item.input_fingerprint: item for item in points})
        return len(self.metric_points) - before

    async def find_snapshot(
        self,
        canonical_symbol: str,
        *,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchSnapshotDocument | None:
        return next(
            (
                item
                for item in self.snapshots
                if item.symbol == canonical_symbol
                and item.data_version == data_version
                and item.metric_version == metric_version
                and item.rule_set_version == rule_set_version
                and item.research_template_version == template_version
            ),
            None,
        )

    async def latest_research_snapshot(
        self, canonical_symbol: str
    ) -> ResearchSnapshotDocument | None:
        return max(
            (item for item in self.snapshots if item.symbol == canonical_symbol),
            key=lambda item: item.knowledge_cutoff,
            default=None,
        )

    async def save_research_snapshot(
        self,
        snapshot: ResearchSnapshotDocument,
        observations: list[ResearchObservation],
    ) -> None:
        if all(item.id != snapshot.id for item in self.snapshots):
            self.snapshots.append(snapshot)
        self.observations.update({item.id: item for item in observations})

    async def list_research_observations(
        self, canonical_symbol: str, *, limit: int
    ) -> tuple[UUID | None, list[ResearchObservation]]:
        snapshot = await self.latest_research_snapshot(canonical_symbol)
        if snapshot is None:
            return None, []
        return snapshot.id, list(snapshot.observations[:limit])

    async def get_research_observation(
        self, canonical_symbol: str, observation_id: UUID
    ) -> ResearchObservation | None:
        item = self.observations.get(observation_id)
        return item if item and item.symbol == canonical_symbol else None

    async def acquire_research_run(
        self,
        *,
        canonical_symbol: str,
        idempotency_key: str,
        data_version: str,
        metric_version: str,
        rule_set_version: str,
        template_version: str,
    ) -> ResearchRunLease:
        existing = self.runs.get(idempotency_key)
        if existing and existing["status"] != "failed":
            return ResearchRunLease(
                run_id=existing["id"],  # type: ignore[arg-type]
                acquired=False,
                status=str(existing["status"]),
            )
        run_id = existing["id"] if existing else uuid4()
        self.runs[idempotency_key] = {
            "id": run_id,
            "symbol": canonical_symbol,
            "status": "running",
            "data_version": data_version,
            "metric_version": metric_version,
            "rule_set_version": rule_set_version,
            "template_version": template_version,
        }
        return ResearchRunLease(run_id=run_id, acquired=True, status="running")  # type: ignore[arg-type]

    async def finish_research_run(
        self,
        run_id: UUID,
        *,
        status: str,
        snapshot_id: UUID | None,
        observation_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None:
        for item in self.runs.values():
            if item["id"] == run_id:
                item.update(
                    status=status,
                    snapshot_id=snapshot_id,
                    observation_count=observation_count,
                    error_summary=error_summary,
                    finished_at=finished_at,
                )
                return


class InMemoryAIResearchRepository:
    def __init__(self) -> None:
        self.outputs: dict[str, AIResearchOutputDocument] = {}
        self.runs: dict[str, dict[str, object]] = {}
        self.calls: list[LLMCallAudit] = []

    async def find_output_by_key(
        self, idempotency_key: str
    ) -> AIResearchOutputDocument | None:
        return self.outputs.get(idempotency_key)

    async def latest_output(
        self, canonical_symbol: str
    ) -> AIResearchOutputDocument | None:
        return max(
            (item for item in self.outputs.values() if item.symbol == canonical_symbol),
            key=lambda item: item.generated_at,
            default=None,
        )

    async def latest_run(self, canonical_symbol: str) -> AIResearchRunView | None:
        matches = [item for item in self.runs.values() if item["symbol"] == canonical_symbol]
        if not matches:
            return None
        row = max(matches, key=lambda item: item["started_at"])  # type: ignore[arg-type,return-value]
        return AIResearchRunView(
            run_id=row["id"],  # type: ignore[arg-type]
            status=str(row["status"]),
            snapshot_id=row["snapshot_id"],  # type: ignore[arg-type]
            error_code=str(row["error_code"]) if row.get("error_code") else None,
        )

    async def acquire_run(
        self,
        *,
        canonical_symbol: str,
        snapshot_id: UUID,
        idempotency_key: str,
        context_version: str,
        context_hash: str,
        prompt_version: str,
        prompt_hash: str,
        output_schema_version: str,
        model_route_version: str,
        route_hash: str,
        retry_failed: bool,
    ) -> AIResearchRunLease:
        now = datetime.now(UTC)
        existing = self.runs.get(idempotency_key)
        if existing:
            lease_expires_at = existing["lease_expires_at"]
            stale = (
                existing["status"] == "running"
                and isinstance(lease_expires_at, datetime)
                and lease_expires_at < now
            )
            retry = existing["status"] == "failed" and retry_failed
            if not stale and not retry:
                return AIResearchRunLease(
                    existing["id"], False, str(existing["status"])  # type: ignore[arg-type]
                )
            existing.update(
                status="running",
                error_code=None,
                started_at=now,
                lease_expires_at=now + timedelta(minutes=30),
            )
            return AIResearchRunLease(existing["id"], True, "running")  # type: ignore[arg-type]
        run_id = uuid4()
        self.runs[idempotency_key] = {
            "id": run_id,
            "symbol": canonical_symbol,
            "snapshot_id": snapshot_id,
            "status": "running",
            "error_code": None,
            "started_at": now,
            "lease_expires_at": now + timedelta(minutes=30),
        }
        return AIResearchRunLease(run_id, True, "running")

    async def record_call(self, audit: LLMCallAudit) -> None:
        self.calls.append(audit)

    async def complete_run(
        self, output: AIResearchOutputDocument, *, idempotency_key: str
    ) -> None:
        self.outputs.setdefault(idempotency_key, output)
        self.runs[idempotency_key]["status"] = "succeeded"

    async def fail_run(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_summary: str,
        finished_at: datetime,
    ) -> None:
        row = next(item for item in self.runs.values() if item["id"] == run_id)
        row.update(
            status="failed",
            error_code=error_code,
            error_summary=error_summary,
            finished_at=finished_at,
        )


class InMemoryWatchlistRepository:
    def __init__(self) -> None:
        self._watchlists: dict[UUID, Watchlist] = {}

    async def list_for_user(self, user_id: UUID) -> list[Watchlist]:
        return [item for item in self._watchlists.values() if item.user_id == user_id]

    async def create(self, watchlist: Watchlist) -> Watchlist:
        self._watchlists[watchlist.id] = watchlist
        return watchlist

    async def get_owned(self, watchlist_id: UUID, user_id: UUID) -> Watchlist | None:
        item = self._watchlists.get(watchlist_id)
        return item if item and item.user_id == user_id else None

    async def save(self, watchlist: Watchlist) -> Watchlist:
        self._watchlists[watchlist.id] = watchlist
        return watchlist
