from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class FiscalPeriod(StrEnum):
    Q1 = "Q1"
    H1 = "H1"
    Q3 = "Q3"
    FY = "FY"


class StatementScope(StrEnum):
    CONSOLIDATED = "consolidated"
    PARENT = "parent"


class PublishedAtPrecision(StrEnum):
    DATE = "date"
    DATETIME = "datetime"


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    MISSING_INPUT = "missing_input"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NOT_APPLICABLE = "not_applicable"
    INVALID_INPUT = "invalid_input"


class MetricBasis(StrEnum):
    POINT_IN_TIME = "point_in_time"
    YTD = "ytd"
    STANDALONE = "standalone"
    FY = "fy"
    TTM = "ttm"


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    total_revenue: Decimal | None = None
    revenue: Decimal | None = None
    operating_cost: Decimal | None = None
    selling_expenses: Decimal | None = None
    administrative_expenses: Decimal | None = None
    research_expenses: Decimal | None = None
    finance_expenses: Decimal | None = None
    operating_profit: Decimal | None = None
    total_profit: Decimal | None = None
    income_tax_expense: Decimal | None = None
    net_profit: Decimal | None = None
    parent_net_profit: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    cash: Decimal | None = None
    accounts_receivable: Decimal | None = None
    inventory: Decimal | None = None
    contract_assets: Decimal | None = None
    current_assets: Decimal | None = None
    total_assets: Decimal | None = None
    short_term_borrowings: Decimal | None = None
    current_portion_noncurrent_liabilities: Decimal | None = None
    long_term_borrowings: Decimal | None = None
    bonds_payable: Decimal | None = None
    lease_liabilities: Decimal | None = None
    contract_liabilities: Decimal | None = None
    current_liabilities: Decimal | None = None
    total_liabilities: Decimal | None = None
    parent_equity: Decimal | None = None
    total_equity: Decimal | None = None
    goodwill: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CashFlowStatement:
    operating_cash_flow: Decimal | None = None
    investing_cash_flow: Decimal | None = None
    financing_cash_flow: Decimal | None = None
    cash_paid_for_long_term_assets: Decimal | None = None
    ending_cash: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FinancialReport:
    canonical_symbol: str
    fiscal_year: int
    fiscal_period: FiscalPeriod
    period_start: date
    period_end: date
    statement_scope: StatementScope
    currency: str
    provider: str
    provider_record_id: str
    provider_revision: str
    payload_checksum: str
    published_at: datetime
    published_at_precision: PublishedAtPrecision
    known_at: datetime
    first_observed_at: datetime
    source_updated_at: datetime | None
    is_audited: bool | None
    issuer_type: str
    income: IncomeStatement | None
    balance: BalanceSheet | None
    cash_flow: CashFlowStatement | None
    normalizer_version: str = "unknown"
    quality_warnings: tuple[str, ...] = ()
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class ValuationObservation:
    canonical_symbol: str
    trade_date: date
    metric_code: str
    value: Decimal
    unit: str
    provider: str
    collected_at: datetime
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class FundamentalMetric:
    code: str
    value: Decimal | None
    unit: str
    status: MetricStatus
    period_end: date | None
    basis: MetricBasis
    input_report_ids: tuple[UUID, ...] = ()
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    canonical_symbol: str
    as_of: datetime
    data_version: str
    metric_version: str
    latest_period_end: date | None
    metrics: tuple[FundamentalMetric, ...]
    id: UUID = field(default_factory=uuid4)
