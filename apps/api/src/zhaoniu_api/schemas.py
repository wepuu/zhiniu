from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema

from zhaoniu_api.domain.models import Stock, UserAccount, UserSession, Watchlist
from zhaoniu_api.fundamentals.metrics import DEFINITION_BY_CODE
from zhaoniu_api.fundamentals.models import FinancialReport, FundamentalMetric, ValuationObservation

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+(?:\.[0-9]+)?$"}),
]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    canonical_symbol: str
    name: str
    exchange: str
    board: str
    asset_type: str
    list_date: date | None
    status: str
    issuer_type: str
    industry: str | None
    latest_price: DecimalString | None
    change_percent: DecimalString | None
    latest_trade_date: date | None
    source: str | None
    collected_at: datetime | None

    @classmethod
    def from_domain(cls, stock: Stock) -> "StockResponse":
        return cls.model_validate(stock)


class StockSearchResponse(BaseModel):
    items: list[StockResponse]
    total: int


StockReadinessStatus = Literal[
    "queued", "preparing", "ready", "partial", "failed", "paused", "unsupported"
]


class StockReadinessStage(BaseModel):
    key: Literal["market", "deterministic_research", "extended_research", "ai_research"]
    status: StockReadinessStatus
    progress: int = Field(ge=0, le=100)
    reason_code: str | None = None
    updated_at: datetime | None = None


class StockReadinessResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    name: str
    overall_status: StockReadinessStatus
    progress: int = Field(ge=0, le=100)
    updated_at: datetime | None = None
    latest_price: DecimalString | None = None
    latest_trade_date: date | None = None
    stages: list[StockReadinessStage]


class StockReadinessListResponse(BaseModel):
    items: list[StockReadinessResponse]


class StockPreparationResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    status: Literal["queued", "reused", "paused"]
    run_id: UUID | None = None
    reason_code: str | None = None


class DailyBarResponse(BaseModel):
    trade_date: date
    adjust_type: str
    open: DecimalString
    high: DecimalString
    low: DecimalString
    close: DecimalString
    pre_close: DecimalString | None
    volume: int
    amount: DecimalString
    pct_change: DecimalString | None
    source: str
    collected_at: datetime


class DailyBarListResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    adjust: str
    items: list[DailyBarResponse]
    total: int


class FundamentalMetricResponse(BaseModel):
    code: str
    display_name: str
    dimension: str
    value: DecimalString | None
    unit: str
    status: str
    period_end: date | None
    basis: str
    source_report_ids: list[UUID]
    detail: str | None

    @classmethod
    def from_domain(cls, metric: FundamentalMetric) -> "FundamentalMetricResponse":
        definition = DEFINITION_BY_CODE[metric.code]
        return cls(
            code=metric.code,
            display_name=definition.display_name,
            dimension=definition.dimension,
            value=metric.value,
            unit=metric.unit,
            status=metric.status,
            period_end=metric.period_end,
            basis=metric.basis,
            source_report_ids=list(metric.input_report_ids),
            detail=metric.detail,
        )


class FundamentalDimensionResponse(BaseModel):
    code: str
    display_name: str
    items: list[FundamentalMetricResponse]


class FundamentalResearchResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    as_of: datetime
    latest_report_period: date | None
    latest_report_published_at: datetime | None
    published_at_precision: str | None
    issuer_type: str
    provider: str | None
    data_version: str
    metric_definition_version: str
    freshness: str
    dimensions: list[FundamentalDimensionResponse]


class IncomeStatementResponse(BaseModel):
    revenue: DecimalString | None
    operating_cost: DecimalString | None
    operating_profit: DecimalString | None
    total_profit: DecimalString | None
    net_profit: DecimalString | None
    parent_net_profit: DecimalString | None


class BalanceSheetResponse(BaseModel):
    cash: DecimalString | None
    accounts_receivable: DecimalString | None
    inventory: DecimalString | None
    current_assets: DecimalString | None
    total_assets: DecimalString | None
    current_liabilities: DecimalString | None
    total_liabilities: DecimalString | None
    parent_equity: DecimalString | None
    total_equity: DecimalString | None
    goodwill: DecimalString | None


class CashFlowStatementResponse(BaseModel):
    operating_cash_flow: DecimalString | None
    investing_cash_flow: DecimalString | None
    financing_cash_flow: DecimalString | None
    cash_paid_for_long_term_assets: DecimalString | None
    ending_cash: DecimalString | None


class FinancialPeriodResponse(BaseModel):
    id: UUID
    fiscal_year: int
    fiscal_period: str
    period_start: date
    period_end: date
    statement_scope: str
    currency: str
    published_at: datetime
    published_at_precision: str
    known_at: datetime
    is_audited: bool | None
    provider: str
    provider_revision: str
    normalizer_version: str
    quality_warnings: list[str]
    income: IncomeStatementResponse | None
    balance: BalanceSheetResponse | None
    cash_flow: CashFlowStatementResponse | None

    @classmethod
    def from_domain(cls, report: FinancialReport) -> "FinancialPeriodResponse":
        return cls(
            id=report.id,
            fiscal_year=report.fiscal_year,
            fiscal_period=report.fiscal_period,
            period_start=report.period_start,
            period_end=report.period_end,
            statement_scope=report.statement_scope,
            currency=report.currency,
            published_at=report.published_at,
            published_at_precision=report.published_at_precision,
            known_at=report.known_at,
            is_audited=report.is_audited,
            provider=report.provider,
            provider_revision=report.provider_revision,
            normalizer_version=report.normalizer_version,
            quality_warnings=list(report.quality_warnings),
            income=IncomeStatementResponse.model_validate(report.income, from_attributes=True)
            if report.income
            else None,
            balance=BalanceSheetResponse.model_validate(report.balance, from_attributes=True)
            if report.balance
            else None,
            cash_flow=CashFlowStatementResponse.model_validate(
                report.cash_flow, from_attributes=True
            )
            if report.cash_flow
            else None,
        )


class FinancialPeriodListResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    items: list[FinancialPeriodResponse]
    total: int


class ValuationObservationResponse(BaseModel):
    trade_date: date
    metric_code: str
    value: DecimalString
    unit: str
    provider: str

    @classmethod
    def from_domain(cls, item: ValuationObservation) -> "ValuationObservationResponse":
        return cls.model_validate(item, from_attributes=True)


class ValuationCoverageResponse(BaseModel):
    start: date | None
    end: date | None
    sample_count: int
    metric_codes: list[str]


class ValuationListResponse(BaseModel):
    symbol: str
    canonical_symbol: str
    items: list[ValuationObservationResponse]
    total: int
    coverage: ValuationCoverageResponse


class WatchlistItemResponse(BaseModel):
    symbol: str
    added_at: datetime


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    is_default: bool
    items: list[WatchlistItemResponse]
    item_count: int

    @classmethod
    def from_domain(cls, watchlist: Watchlist) -> "WatchlistResponse":
        return cls(
            id=watchlist.id,
            name=watchlist.name,
            is_default=watchlist.is_default,
            items=[
                WatchlistItemResponse(symbol=i.symbol, added_at=i.added_at) for i in watchlist.items
            ],
            item_count=len(watchlist.items),
        )


class CreateWatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class AddWatchlistItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(pattern=r"^[0-9A-Z.]{1,16}$")


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class LegalAcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: Literal[
        "terms_of_service", "privacy_policy", "risk_disclosure", "ai_content_notice"
    ]
    document_version: str = Field(min_length=1, max_length=40)


class RegistrationRequest(AuthRequest):
    invitation_code: str = Field(min_length=8, max_length=80)
    legal_acceptances: list[LegalAcceptanceRequest] = Field(min_length=2, max_length=4)


class UserResponse(BaseModel):
    id: UUID
    email: str
    status: str
    created_at: datetime
    last_login_at: datetime | None
    email_verified_at: datetime | None = None
    password_changed_at: datetime | None = None

    @classmethod
    def from_domain(cls, user: UserAccount) -> "UserResponse":
        return cls.model_validate(user, from_attributes=True)


class EntitlementsResponse(BaseModel):
    access_status: str
    valid_until: datetime | None = None
    features: dict[str, bool]
    limits: dict[str, int]


class MeResponse(BaseModel):
    user: UserResponse
    entitlements: EntitlementsResponse
    required_legal_acceptances: list[str] = Field(default_factory=list)


class AuthResponse(BaseModel):
    user: UserResponse
    entitlements: EntitlementsResponse


class EmailVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=256)


class EmailVerificationResponse(BaseModel):
    status: Literal["verified", "already_verified", "sent", "delivery_unavailable"]


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=15, max_length=128)


class OperationAcceptedResponse(BaseModel):
    status: Literal["accepted", "completed"]


class LegalDocumentResponse(BaseModel):
    document_type: str
    version: str
    title: str
    path: str
    content_hash: str
    required_at_registration: bool


class LegalDocumentListResponse(BaseModel):
    items: list[LegalDocumentResponse]


class LegalAcceptanceBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LegalAcceptanceRequest] = Field(min_length=1, max_length=4)


class LegalAcceptanceStatusResponse(BaseModel):
    required_document_types: list[str]


class DependencyStatus(BaseModel):
    name: str
    status: Literal["healthy", "degraded", "unavailable", "disabled"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    migration_head: str
    dependencies: list[DependencyStatus]


class SessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    user_agent: str | None
    is_current: bool

    @classmethod
    def from_domain(cls, session: UserSession) -> "SessionResponse":
        return cls.model_validate(session, from_attributes=True)


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int


class WatchlistMembershipResponse(BaseModel):
    symbol: str
    watchlist_ids: list[UUID]
    is_member: bool
