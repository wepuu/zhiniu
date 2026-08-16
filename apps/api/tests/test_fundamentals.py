from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from zhaoniu_api.dependencies import get_fundamental_service, get_stock_repository
from zhaoniu_api.fundamentals.metrics import compute_fundamental_metrics
from zhaoniu_api.fundamentals.models import (
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    FiscalPeriod,
    IncomeStatement,
    PublishedAtPrecision,
    StatementScope,
    ValuationObservation,
)
from zhaoniu_api.fundamentals.normalizer import AKShareFinancialNormalizer
from zhaoniu_api.fundamentals.quality import validate_financial_report
from zhaoniu_api.fundamentals.service import FundamentalResearchService
from zhaoniu_api.infrastructure.mock_repositories import (
    InMemoryFundamentalRepository,
    InMemoryStockRepository,
)
from zhaoniu_api.main import create_app
from zhaoniu_api.ports.providers import RawFinancialStatement, RawValuationObservation


def _report(
    year: int,
    period: FiscalPeriod,
    *,
    revenue: str,
    profit: str,
    ocf: str,
    known_at: datetime | None = None,
    checksum: str | None = None,
) -> FinancialReport:
    period_end = {
        FiscalPeriod.Q1: date(year, 3, 31),
        FiscalPeriod.H1: date(year, 6, 30),
        FiscalPeriod.Q3: date(year, 9, 30),
        FiscalPeriod.FY: date(year, 12, 31),
    }[period]
    timestamp = known_at or datetime(year + 1, 4, 1, tzinfo=UTC)
    return FinancialReport(
        id=uuid4(),
        canonical_symbol="600519.SH",
        fiscal_year=year,
        fiscal_period=period,
        period_start=date(year, 1, 1),
        period_end=period_end,
        statement_scope=StatementScope.CONSOLIDATED,
        currency="CNY",
        provider="fixture",
        provider_record_id=f"fixture-{year}-{period}",
        provider_revision="1",
        payload_checksum=checksum or f"checksum-{year}-{period}",
        published_at=timestamp,
        published_at_precision=PublishedAtPrecision.DATE,
        known_at=timestamp,
        first_observed_at=timestamp,
        source_updated_at=timestamp,
        is_audited=period == FiscalPeriod.FY,
        issuer_type="general",
        income=IncomeStatement(
            revenue=Decimal(revenue),
            operating_cost=Decimal(revenue) * Decimal("0.2"),
            net_profit=Decimal(profit),
            parent_net_profit=Decimal(profit),
        ),
        balance=BalanceSheet(
            cash=Decimal("100"),
            accounts_receivable=Decimal("20"),
            inventory=Decimal("30"),
            current_assets=Decimal("200"),
            total_assets=Decimal("500"),
            current_liabilities=Decimal("100"),
            total_liabilities=Decimal("150"),
            parent_equity=Decimal("350"),
            total_equity=Decimal("350"),
            goodwill=Decimal("5"),
        ),
        cash_flow=CashFlowStatement(
            operating_cash_flow=Decimal(ocf),
            cash_paid_for_long_term_assets=Decimal("10"),
        ),
    )


def test_akshare_financial_normalizer_preserves_period_version_and_units() -> None:
    rows = [
        RawFinancialStatement(
            provider="akshare",
            requested_symbol="600519",
            statement_type="利润表",
            payload={
                "报告日": "20240630",
                "营业收入": "1000.25",
                "营业成本": "200.05",
                "归属于母公司所有者的净利润": "400.10",
                "公告日期": "20240809",
                "币种": "CNY",
                "类型": "合并期末",
                "是否审计": "未审计",
                "更新日期": "2024-08-08T20:30:00",
            },
        ),
        RawFinancialStatement(
            provider="akshare",
            requested_symbol="600519",
            statement_type="资产负债表",
            payload={
                "报告日": "20240630",
                "资产总计": "5000",
                "负债合计": "1000",
                "所有者权益(或股东权益)合计": "4000",
                "公告日期": "20240809",
                "币种": "CNY",
                "类型": "合并期末",
                "更新日期": "2024-08-08T20:30:00",
            },
        ),
    ]
    report = AKShareFinancialNormalizer().reports(
        rows, observed_at=datetime(2024, 8, 10, tzinfo=UTC)
    )[0]
    assert report.fiscal_period == FiscalPeriod.H1
    assert report.income and report.income.revenue == Decimal("1000.25")
    assert report.known_at == datetime(2024, 8, 9, 16, 0, tzinfo=UTC)
    assert report.published_at_precision == PublishedAtPrecision.DATE
    assert len(report.payload_checksum) == 64
    assert validate_financial_report(report).quality_warnings == ()


def test_valuation_normalizer_converts_baidu_market_cap_to_cny() -> None:
    row = RawValuationObservation(
        provider="akshare",
        requested_symbol="600519",
        metric_code="market_cap",
        payload={"date": date(2026, 8, 14), "value": "20000.5"},
    )
    value = AKShareFinancialNormalizer().valuations([row])[0]
    assert value.value == Decimal("2000050000000.0")
    assert value.unit == "CNY"


def test_single_quarter_metrics_use_flow_differences_not_balance_sheet() -> None:
    reports = [
        _report(2024, FiscalPeriod.Q1, revenue="100", profit="20", ocf="18"),
        _report(2024, FiscalPeriod.H1, revenue="250", profit="45", ocf="40"),
        _report(2025, FiscalPeriod.Q1, revenue="120", profit="24", ocf="22"),
        _report(2025, FiscalPeriod.H1, revenue="300", profit="54", ocf="50"),
    ]
    metrics = {item.code: item for item in compute_fundamental_metrics(reports)}
    assert metrics["revenue_single_quarter_yoy"].value == Decimal("20.0000")
    assert metrics["parent_net_profit_single_quarter_yoy"].value == Decimal("20.0000")
    assert metrics["cash"].value == Decimal("100.00")


async def test_report_revisions_are_selected_point_in_time() -> None:
    old = _report(
        2024,
        FiscalPeriod.FY,
        revenue="100",
        profit="20",
        ocf="18",
        known_at=datetime(2025, 3, 1, tzinfo=UTC),
        checksum="old",
    )
    revised = _report(
        2024,
        FiscalPeriod.FY,
        revenue="110",
        profit="22",
        ocf="19",
        known_at=datetime(2025, 5, 1, tzinfo=UTC),
        checksum="new",
    )
    repository = InMemoryFundamentalRepository([old, revised])
    before = await repository.list_reports(
        "600519.SH", as_of=datetime(2025, 4, 1, tzinfo=UTC), limit=10
    )
    after = await repository.list_reports(
        "600519.SH", as_of=datetime(2025, 6, 1, tzinfo=UTC), limit=10
    )
    assert before[0].payload_checksum == "old"
    assert after[0].payload_checksum == "new"


class _UnusedProvider:
    name = "fixture"

    async def get_financial_statements(self, symbol: str, start_year: int):  # type: ignore[no-untyped-def]
        return []

    async def get_valuation_observations(self, symbol: str, start: date, end: date):  # type: ignore[no-untyped-def]
        return []


class _UnusedRuns:
    async def was_successful(self, idempotency_key: str) -> bool:
        return False


def test_fundamental_api_returns_grouped_metrics_and_traceable_periods() -> None:
    reports = [
        _report(2023, FiscalPeriod.FY, revenue="100", profit="20", ocf="18"),
        _report(2024, FiscalPeriod.FY, revenue="120", profit="24", ocf="22"),
    ]
    valuations = [
        ValuationObservation(
            canonical_symbol="600519.SH",
            trade_date=date(2025, 4, 1),
            metric_code="pe_ttm",
            value=Decimal("20"),
            unit="multiple",
            provider="fixture",
            collected_at=datetime(2025, 4, 1, tzinfo=UTC),
        )
    ]
    repository = InMemoryFundamentalRepository(reports, valuations)
    service = FundamentalResearchService(
        provider=_UnusedProvider(),
        normalizer=AKShareFinancialNormalizer(),
        stocks=InMemoryStockRepository(),
        fundamentals=repository,
        runs=_UnusedRuns(),  # type: ignore[arg-type]
    )
    app = create_app()
    app.dependency_overrides[get_stock_repository] = InMemoryStockRepository
    app.dependency_overrides[get_fundamental_service] = lambda: service
    client = TestClient(app)

    research = client.get(
        "/api/v1/stocks/600519/research/fundamentals",
        params={"as_of": "2025-04-02T00:00:00Z"},
    )
    assert research.status_code == 200
    assert [item["code"] for item in research.json()["dimensions"]] == [
        "growth",
        "profitability",
        "quality",
        "balance",
        "valuation",
    ]
    periods = client.get("/api/v1/stocks/600519/financials/periods")
    assert periods.status_code == 200
    assert periods.json()["items"][0]["provider"] == "fixture"
    valuation = client.get("/api/v1/stocks/600519/valuations?metrics=pe_ttm")
    assert valuation.json()["items"][0]["value"] == "20"
