from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.db import (
    BalanceSheetRecord,
    CashFlowStatementRecord,
    DataSyncRunRecord,
    FinancialReportRevisionRecord,
    FundamentalMetricRecord,
    FundamentalSnapshotRecord,
    IncomeStatementRecord,
    StockDailyBarRecord,
    StockRecord,
    ValuationObservationRecord,
)
from zhaoniu_api.domain.models import AdjustType, DailyBar, Stock, resolve_symbol
from zhaoniu_api.fundamentals.models import (
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    FiscalPeriod,
    FundamentalMetric,
    FundamentalSnapshot,
    IncomeStatement,
    MetricBasis,
    MetricStatus,
    PublishedAtPrecision,
    StatementScope,
    ValuationObservation,
)


class SQLAlchemyStockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _domain(record: StockRecord, bar: StockDailyBarRecord | None) -> Stock:
        return Stock(
            symbol=record.ticker,
            canonical_symbol=record.symbol,
            name=record.name,
            exchange=record.exchange,
            industry=record.industry_code,
            board=record.board,
            asset_type=record.asset_type,
            list_date=record.list_date,
            status=record.status,
            issuer_type=record.issuer_type,
            source=record.source,
            collected_at=record.collected_at,
            latest_price=bar.close if bar else None,
            change_percent=bar_to_pct_change(bar),
            latest_trade_date=bar.trade_date if bar else None,
        )

    async def _latest_bar(self, canonical_symbol: str) -> StockDailyBarRecord | None:
        return cast(
            StockDailyBarRecord | None,
            await self._session.scalar(
                select(StockDailyBarRecord)
                .where(
                    StockDailyBarRecord.symbol == canonical_symbol,
                    StockDailyBarRecord.adjust_type == AdjustType.NONE,
                )
                .order_by(StockDailyBarRecord.trade_date.desc())
                .limit(1)
            ),
        )

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        needle = f"%{query.strip()}%"
        records = (
            await self._session.scalars(
                select(StockRecord)
                .where(or_(StockRecord.ticker.ilike(needle), StockRecord.name.ilike(needle)))
                .order_by(StockRecord.ticker)
                .limit(limit)
            )
        ).all()
        return [self._domain(record, await self._latest_bar(record.symbol)) for record in records]

    async def get(self, symbol: str) -> Stock | None:
        try:
            canonical = resolve_symbol(symbol).canonical
        except ValueError:
            return None
        record = await self._session.get(StockRecord, canonical)
        if record is None:
            return None
        return self._domain(record, await self._latest_bar(canonical))

    async def upsert_many(self, stocks: list[Stock]) -> int:
        if not stocks:
            return 0
        values = [
            {
                "symbol": stock.canonical_symbol,
                "ticker": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "industry_code": stock.industry,
                "asset_type": stock.asset_type,
                "board": stock.board,
                "list_date": stock.list_date,
                "status": stock.status,
                "issuer_type": stock.issuer_type,
                "source": stock.source or "unknown",
                "collected_at": stock.collected_at or datetime.now(UTC),
            }
            for stock in stocks
        ]
        try:
            for offset in range(0, len(values), 1000):
                statement = insert(StockRecord).values(values[offset : offset + 1000])
                await self._session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[StockRecord.symbol],
                        set_={
                            "ticker": statement.excluded.ticker,
                            "name": statement.excluded.name,
                            "exchange": statement.excluded.exchange,
                            "industry_code": statement.excluded.industry_code,
                            "asset_type": statement.excluded.asset_type,
                            "board": statement.excluded.board,
                            "list_date": statement.excluded.list_date,
                            "status": statement.excluded.status,
                            "issuer_type": statement.excluded.issuer_type,
                            "source": statement.excluded.source,
                            "collected_at": statement.excluded.collected_at,
                            "updated_at": func.now(),
                        },
                    )
                )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(stocks)


def bar_to_pct_change(bar: StockDailyBarRecord | None) -> Decimal | None:
    if bar is None or bar.pre_close is None or bar.pre_close == 0:
        return None
    return ((bar.close - bar.pre_close) / bar.pre_close * Decimal("100")).quantize(
        Decimal("0.0001")
    )


class SQLAlchemyDailyBarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _domain(row: StockDailyBarRecord) -> DailyBar:
        return DailyBar(
            canonical_symbol=row.symbol,
            trade_date=row.trade_date,
            adjust_type=AdjustType(row.adjust_type),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            pre_close=row.pre_close,
            volume=row.volume,
            amount=row.amount,
            source=row.source,
            collected_at=row.collected_at,
        )

    async def list_for_symbol(
        self,
        canonical_symbol: str,
        *,
        start: date | None,
        end: date | None,
        limit: int,
    ) -> list[DailyBar]:
        filters = [
            StockDailyBarRecord.symbol == canonical_symbol,
            StockDailyBarRecord.adjust_type == AdjustType.NONE,
        ]
        if start is not None:
            filters.append(StockDailyBarRecord.trade_date >= start)
        if end is not None:
            filters.append(StockDailyBarRecord.trade_date <= end)
        rows = (
            await self._session.scalars(
                select(StockDailyBarRecord)
                .where(*filters)
                .order_by(StockDailyBarRecord.trade_date.desc())
                .limit(limit)
            )
        ).all()
        return [self._domain(row) for row in reversed(rows)]

    async def latest_date(self, canonical_symbol: str) -> date | None:
        latest = await self._session.scalar(
            select(func.max(StockDailyBarRecord.trade_date)).where(
                StockDailyBarRecord.symbol == canonical_symbol,
                StockDailyBarRecord.adjust_type == AdjustType.NONE,
            )
        )
        return latest if isinstance(latest, date) else None

    async def upsert_many(self, bars: list[DailyBar]) -> int:
        if not bars:
            return 0
        values = [
            {
                "symbol": bar.canonical_symbol,
                "trade_date": bar.trade_date,
                "adjust_type": bar.adjust_type,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "pre_close": bar.pre_close,
                "volume": bar.volume,
                "amount": bar.amount,
                "source": bar.source,
                "collected_at": bar.collected_at,
            }
            for bar in bars
        ]
        try:
            statement = insert(StockDailyBarRecord).values(values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_stock_daily_bar_identity",
                    set_={
                        "open": statement.excluded.open,
                        "high": statement.excluded.high,
                        "low": statement.excluded.low,
                        "close": statement.excluded.close,
                        "pre_close": statement.excluded.pre_close,
                        "volume": statement.excluded.volume,
                        "amount": statement.excluded.amount,
                        "source": statement.excluded.source,
                        "collected_at": statement.excluded.collected_at,
                        "updated_at": func.now(),
                    },
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(bars)


class SQLAlchemyFundamentalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_reports(self, reports: list[FinancialReport]) -> int:
        if not reports:
            return 0
        written = 0
        try:
            for report in reports:
                revision_values = {
                    "id": report.id,
                    "symbol": report.canonical_symbol,
                    "fiscal_year": report.fiscal_year,
                    "fiscal_period": report.fiscal_period,
                    "period_start": report.period_start,
                    "period_end": report.period_end,
                    "statement_scope": report.statement_scope,
                    "currency": report.currency,
                    "provider": report.provider,
                    "provider_record_id": report.provider_record_id,
                    "provider_revision": report.provider_revision,
                    "normalizer_version": report.normalizer_version,
                    "payload_checksum": report.payload_checksum,
                    "published_at": report.published_at,
                    "published_at_precision": report.published_at_precision,
                    "known_at": report.known_at,
                    "first_observed_at": report.first_observed_at,
                    "source_updated_at": report.source_updated_at,
                    "is_audited": report.is_audited,
                    "issuer_type": report.issuer_type,
                    "quality_warnings": {"items": list(report.quality_warnings)},
                }
                statement = (
                    insert(FinancialReportRevisionRecord)
                    .values(revision_values)
                    .on_conflict_do_nothing(constraint="uq_financial_report_revision_identity")
                    .returning(FinancialReportRevisionRecord.id)
                )
                inserted_id = await self._session.scalar(statement)
                if inserted_id is None:
                    continue
                written += 1
                if report.income is not None:
                    await self._session.execute(
                        insert(IncomeStatementRecord).values(
                            report_id=report.id,
                            total_revenue=report.income.total_revenue,
                            revenue=report.income.revenue,
                            operating_cost=report.income.operating_cost,
                            selling_expenses=report.income.selling_expenses,
                            administrative_expenses=report.income.administrative_expenses,
                            research_expenses=report.income.research_expenses,
                            finance_expenses=report.income.finance_expenses,
                            operating_profit=report.income.operating_profit,
                            total_profit=report.income.total_profit,
                            income_tax_expense=report.income.income_tax_expense,
                            net_profit=report.income.net_profit,
                            parent_net_profit=report.income.parent_net_profit,
                        )
                    )
                if report.balance is not None:
                    await self._session.execute(
                        insert(BalanceSheetRecord).values(
                            report_id=report.id,
                            cash=report.balance.cash,
                            accounts_receivable=report.balance.accounts_receivable,
                            inventory=report.balance.inventory,
                            contract_assets=report.balance.contract_assets,
                            current_assets=report.balance.current_assets,
                            total_assets=report.balance.total_assets,
                            short_term_borrowings=report.balance.short_term_borrowings,
                            current_portion_noncurrent_liabilities=(
                                report.balance.current_portion_noncurrent_liabilities
                            ),
                            long_term_borrowings=report.balance.long_term_borrowings,
                            bonds_payable=report.balance.bonds_payable,
                            lease_liabilities=report.balance.lease_liabilities,
                            contract_liabilities=report.balance.contract_liabilities,
                            current_liabilities=report.balance.current_liabilities,
                            total_liabilities=report.balance.total_liabilities,
                            parent_equity=report.balance.parent_equity,
                            total_equity=report.balance.total_equity,
                            goodwill=report.balance.goodwill,
                        )
                    )
                if report.cash_flow is not None:
                    await self._session.execute(
                        insert(CashFlowStatementRecord).values(
                            report_id=report.id,
                            operating_cash_flow=report.cash_flow.operating_cash_flow,
                            investing_cash_flow=report.cash_flow.investing_cash_flow,
                            financing_cash_flow=report.cash_flow.financing_cash_flow,
                            cash_paid_for_long_term_assets=(
                                report.cash_flow.cash_paid_for_long_term_assets
                            ),
                            ending_cash=report.cash_flow.ending_cash,
                        )
                    )
                if report.issuer_type != "general":
                    await self._session.execute(
                        update(StockRecord)
                        .where(StockRecord.symbol == report.canonical_symbol)
                        .values(issuer_type=report.issuer_type)
                    )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return written

    async def list_reports(
        self,
        canonical_symbol: str,
        *,
        as_of: datetime | None,
        limit: int,
    ) -> list[FinancialReport]:
        filters = [FinancialReportRevisionRecord.symbol == canonical_symbol]
        if as_of is not None:
            filters.append(FinancialReportRevisionRecord.known_at <= as_of)
        revision_rows = (
            await self._session.scalars(
                select(FinancialReportRevisionRecord)
                .where(*filters)
                .order_by(
                    FinancialReportRevisionRecord.period_end.desc(),
                    FinancialReportRevisionRecord.known_at.desc(),
                    FinancialReportRevisionRecord.created_at.desc(),
                )
                .limit(limit * 4)
            )
        ).all()
        selected: list[FinancialReportRevisionRecord] = []
        seen: set[tuple[date, str]] = set()
        for row in revision_rows:
            identity = (row.period_end, row.statement_scope)
            if identity not in seen:
                selected.append(row)
                seen.add(identity)
            if len(selected) >= limit:
                break
        if not selected:
            return []
        ids = [row.id for row in selected]
        income = {
            row.report_id: row
            for row in (
                await self._session.scalars(
                    select(IncomeStatementRecord).where(IncomeStatementRecord.report_id.in_(ids))
                )
            ).all()
        }
        balance = {
            row.report_id: row
            for row in (
                await self._session.scalars(
                    select(BalanceSheetRecord).where(BalanceSheetRecord.report_id.in_(ids))
                )
            ).all()
        }
        cash_flow = {
            row.report_id: row
            for row in (
                await self._session.scalars(
                    select(CashFlowStatementRecord).where(
                        CashFlowStatementRecord.report_id.in_(ids)
                    )
                )
            ).all()
        }
        reports: list[FinancialReport] = []
        for row in selected:
            income_row = income.get(row.id)
            balance_row = balance.get(row.id)
            cash_flow_row = cash_flow.get(row.id)
            warnings = row.quality_warnings.get("items", [])
            reports.append(
                FinancialReport(
                    id=row.id,
                    canonical_symbol=row.symbol,
                    fiscal_year=row.fiscal_year,
                    fiscal_period=FiscalPeriod(row.fiscal_period),
                    period_start=row.period_start,
                    period_end=row.period_end,
                    statement_scope=StatementScope(row.statement_scope),
                    currency=row.currency,
                    provider=row.provider,
                    provider_record_id=row.provider_record_id,
                    provider_revision=row.provider_revision,
                    normalizer_version=row.normalizer_version,
                    payload_checksum=row.payload_checksum,
                    published_at=row.published_at,
                    published_at_precision=PublishedAtPrecision(row.published_at_precision),
                    known_at=row.known_at,
                    first_observed_at=row.first_observed_at,
                    source_updated_at=row.source_updated_at,
                    is_audited=row.is_audited,
                    issuer_type=row.issuer_type,
                    income=(
                        IncomeStatement(
                            total_revenue=income_row.total_revenue,
                            revenue=income_row.revenue,
                            operating_cost=income_row.operating_cost,
                            selling_expenses=income_row.selling_expenses,
                            administrative_expenses=income_row.administrative_expenses,
                            research_expenses=income_row.research_expenses,
                            finance_expenses=income_row.finance_expenses,
                            operating_profit=income_row.operating_profit,
                            total_profit=income_row.total_profit,
                            income_tax_expense=income_row.income_tax_expense,
                            net_profit=income_row.net_profit,
                            parent_net_profit=income_row.parent_net_profit,
                        )
                        if income_row
                        else None
                    ),
                    balance=(
                        BalanceSheet(
                            cash=balance_row.cash,
                            accounts_receivable=balance_row.accounts_receivable,
                            inventory=balance_row.inventory,
                            contract_assets=balance_row.contract_assets,
                            current_assets=balance_row.current_assets,
                            total_assets=balance_row.total_assets,
                            short_term_borrowings=balance_row.short_term_borrowings,
                            current_portion_noncurrent_liabilities=(
                                balance_row.current_portion_noncurrent_liabilities
                            ),
                            long_term_borrowings=balance_row.long_term_borrowings,
                            bonds_payable=balance_row.bonds_payable,
                            lease_liabilities=balance_row.lease_liabilities,
                            contract_liabilities=balance_row.contract_liabilities,
                            current_liabilities=balance_row.current_liabilities,
                            total_liabilities=balance_row.total_liabilities,
                            parent_equity=balance_row.parent_equity,
                            total_equity=balance_row.total_equity,
                            goodwill=balance_row.goodwill,
                        )
                        if balance_row
                        else None
                    ),
                    cash_flow=(
                        CashFlowStatement(
                            operating_cash_flow=cash_flow_row.operating_cash_flow,
                            investing_cash_flow=cash_flow_row.investing_cash_flow,
                            financing_cash_flow=cash_flow_row.financing_cash_flow,
                            cash_paid_for_long_term_assets=(
                                cash_flow_row.cash_paid_for_long_term_assets
                            ),
                            ending_cash=cash_flow_row.ending_cash,
                        )
                        if cash_flow_row
                        else None
                    ),
                    quality_warnings=tuple(str(item) for item in warnings),
                )
            )
        return reports

    async def save_snapshot(self, snapshot: FundamentalSnapshot) -> int:
        try:
            statement = (
                insert(FundamentalSnapshotRecord)
                .values(
                    id=snapshot.id,
                    symbol=snapshot.canonical_symbol,
                    as_of=snapshot.as_of,
                    data_version=snapshot.data_version,
                    metric_version=snapshot.metric_version,
                    latest_period_end=snapshot.latest_period_end,
                )
                .on_conflict_do_nothing(constraint="uq_fundamental_snapshot_identity")
                .returning(FundamentalSnapshotRecord.id)
            )
            snapshot_id = await self._session.scalar(statement)
            if snapshot_id is None:
                snapshot_id = await self._session.scalar(
                    select(FundamentalSnapshotRecord.id).where(
                        FundamentalSnapshotRecord.symbol == snapshot.canonical_symbol,
                        FundamentalSnapshotRecord.data_version == snapshot.data_version,
                        FundamentalSnapshotRecord.metric_version == snapshot.metric_version,
                    )
                )
            if snapshot_id is None:
                raise RuntimeError("fundamental snapshot upsert failed")
            if snapshot.metrics:
                metric_values = [
                    {
                        "snapshot_id": snapshot_id,
                        "code": metric.code,
                        "value": metric.value,
                        "unit": metric.unit,
                        "status": metric.status,
                        "period_end": metric.period_end,
                        "basis": metric.basis,
                        "input_report_ids": {
                            "items": [str(item) for item in metric.input_report_ids]
                        },
                        "detail": metric.detail,
                    }
                    for metric in snapshot.metrics
                ]
                metric_statement = insert(FundamentalMetricRecord).values(metric_values)
                await self._session.execute(
                    metric_statement.on_conflict_do_update(
                        constraint="uq_fundamental_metric_snapshot_code",
                        set_={
                            "value": metric_statement.excluded.value,
                            "unit": metric_statement.excluded.unit,
                            "status": metric_statement.excluded.status,
                            "period_end": metric_statement.excluded.period_end,
                            "basis": metric_statement.excluded.basis,
                            "input_report_ids": metric_statement.excluded.input_report_ids,
                            "detail": metric_statement.excluded.detail,
                        },
                    )
                )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(snapshot.metrics)

    async def latest_snapshot(
        self, canonical_symbol: str, *, as_of: datetime | None
    ) -> FundamentalSnapshot | None:
        filters = [FundamentalSnapshotRecord.symbol == canonical_symbol]
        if as_of is not None:
            filters.append(FundamentalSnapshotRecord.as_of <= as_of)
        record = await self._session.scalar(
            select(FundamentalSnapshotRecord)
            .where(*filters)
            .order_by(FundamentalSnapshotRecord.as_of.desc())
            .limit(1)
        )
        if record is None:
            return None
        metric_rows = (
            await self._session.scalars(
                select(FundamentalMetricRecord)
                .where(FundamentalMetricRecord.snapshot_id == record.id)
                .order_by(FundamentalMetricRecord.code)
            )
        ).all()
        return FundamentalSnapshot(
            id=record.id,
            canonical_symbol=record.symbol,
            as_of=record.as_of,
            data_version=record.data_version,
            metric_version=record.metric_version,
            latest_period_end=record.latest_period_end,
            metrics=tuple(
                FundamentalMetric(
                    code=row.code,
                    value=row.value,
                    unit=row.unit,
                    status=MetricStatus(row.status),
                    period_end=row.period_end,
                    basis=MetricBasis(row.basis),
                    input_report_ids=tuple(
                        UUID(item) for item in row.input_report_ids.get("items", [])
                    ),
                    detail=row.detail,
                )
                for row in metric_rows
            ),
        )

    async def upsert_valuations(self, observations: list[ValuationObservation]) -> int:
        if not observations:
            return 0
        values = [
            {
                "symbol": item.canonical_symbol,
                "trade_date": item.trade_date,
                "metric_code": item.metric_code,
                "value": item.value,
                "unit": item.unit,
                "provider": item.provider,
                "collected_at": item.collected_at,
            }
            for item in observations
        ]
        try:
            for offset in range(0, len(values), 1000):
                statement = insert(ValuationObservationRecord).values(
                    values[offset : offset + 1000]
                )
                await self._session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_valuation_observation_identity",
                        set_={
                            "value": statement.excluded.value,
                            "unit": statement.excluded.unit,
                            "collected_at": statement.excluded.collected_at,
                            "updated_at": func.now(),
                        },
                    )
                )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
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
        filters = [ValuationObservationRecord.symbol == canonical_symbol]
        if start is not None:
            filters.append(ValuationObservationRecord.trade_date >= start)
        if end is not None:
            filters.append(ValuationObservationRecord.trade_date <= end)
        if metric_codes:
            filters.append(ValuationObservationRecord.metric_code.in_(metric_codes))
        rows = (
            await self._session.scalars(
                select(ValuationObservationRecord)
                .where(*filters)
                .order_by(ValuationObservationRecord.trade_date.desc())
                .limit(limit)
            )
        ).all()
        return [
            ValuationObservation(
                canonical_symbol=row.symbol,
                trade_date=row.trade_date,
                metric_code=row.metric_code,
                value=row.value,
                unit=row.unit,
                provider=row.provider,
                collected_at=row.collected_at,
                id=row.id,
            )
            for row in reversed(rows)
        ]


class SQLAlchemySyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def was_successful(self, idempotency_key: str) -> bool:
        return bool(
            await self._session.scalar(
                select(func.count(DataSyncRunRecord.id)).where(
                    DataSyncRunRecord.idempotency_key == idempotency_key,
                    DataSyncRunRecord.status == "succeeded",
                )
            )
        )

    async def start(
        self,
        *,
        dataset: str,
        provider: str,
        canonical_symbol: str | None,
        requested_start: date | None,
        requested_end: date | None,
        idempotency_key: str,
    ) -> str:
        record = DataSyncRunRecord(
            dataset=dataset,
            provider=provider,
            symbol=canonical_symbol,
            requested_start=requested_start,
            requested_end=requested_end,
            idempotency_key=idempotency_key,
            status="running",
        )
        self._session.add(record)
        await self._session.commit()
        return str(record.id)

    async def finish(
        self,
        run_id: str,
        *,
        status: str,
        received_count: int,
        written_count: int,
        error_summary: str | None,
        finished_at: datetime,
    ) -> None:
        record = await self._session.get(DataSyncRunRecord, UUID(run_id))
        if record is None:
            raise RuntimeError("sync run not found")
        record.status = status
        record.received_count = received_count
        record.written_count = written_count
        record.error_summary = error_summary[:500] if error_summary else None
        record.finished_at = finished_at
        started = record.started_at
        if started is not None:
            record.duration_ms = int((finished_at - started).total_seconds() * 1000)
        await self._session.commit()
