from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from zhaoniu_api.dependencies import (
    CurrentUserId,
    DailyBarRepo,
    FundamentalService,
    StockRepo,
    WatchlistRepo,
)
from zhaoniu_api.domain.models import Watchlist, resolve_symbol
from zhaoniu_api.schemas import (
    AddWatchlistItemRequest,
    CreateWatchlistRequest,
    DailyBarListResponse,
    DailyBarResponse,
    FinancialPeriodListResponse,
    FinancialPeriodResponse,
    FundamentalDimensionResponse,
    FundamentalMetricResponse,
    FundamentalResearchResponse,
    HealthResponse,
    StockResponse,
    StockSearchResponse,
    ValuationCoverageResponse,
    ValuationListResponse,
    ValuationObservationResponse,
    WatchlistResponse,
)

_DIMENSIONS = {
    "growth": "成长",
    "profitability": "盈利能力",
    "quality": "经营质量",
    "balance": "资产负债",
    "valuation": "估值",
}
_VALUATION_CODES = {"pe_ttm", "pb", "pcf", "market_cap"}

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="zhaoniu-api", version="0.1.0")


@router.get("/stocks/search", response_model=StockSearchResponse, tags=["stocks"])
async def search_stocks(
    repository: StockRepo,
    q: Annotated[str, Query(min_length=1, max_length=40)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> StockSearchResponse:
    stocks = await repository.search(q, limit)
    items = [StockResponse.from_domain(stock) for stock in stocks]
    return StockSearchResponse(items=items, total=len(items))


@router.get("/stocks/{symbol}", response_model=StockResponse, tags=["stocks"])
async def get_stock(symbol: str, repository: StockRepo) -> StockResponse:
    stock = await repository.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return StockResponse.from_domain(stock)


@router.get("/stocks/{symbol}/daily-bars", response_model=DailyBarListResponse, tags=["stocks"])
async def get_daily_bars(
    symbol: str,
    stocks: StockRepo,
    bars: DailyBarRepo,
    start: date | None = None,
    end: date | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 120,
    adjust: Literal["none"] = "none",
) -> DailyBarListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    resolved = resolve_symbol(symbol)
    records = await bars.list_for_symbol(resolved.canonical, start=start, end=end, limit=limit)
    items = [
        DailyBarResponse(
            trade_date=bar.trade_date,
            adjust_type=bar.adjust_type,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            pre_close=bar.pre_close,
            volume=bar.volume,
            amount=bar.amount,
            pct_change=bar.pct_change,
            source=bar.source,
            collected_at=bar.collected_at,
        )
        for bar in records
    ]
    return DailyBarListResponse(
        symbol=resolved.ticker,
        canonical_symbol=resolved.canonical,
        adjust=adjust,
        items=items,
        total=len(items),
    )


@router.get(
    "/stocks/{symbol}/research/fundamentals",
    response_model=FundamentalResearchResponse,
    tags=["fundamentals"],
)
async def get_fundamental_research(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    as_of: datetime | None = None,
) -> FundamentalResearchResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    effective_as_of = as_of or datetime.now(UTC)
    if effective_as_of.tzinfo is None:
        effective_as_of = effective_as_of.replace(tzinfo=UTC)
    reports = await service.list_reports(symbol, as_of=effective_as_of, limit=64)
    snapshot = await service.get_snapshot(symbol, as_of=as_of)
    latest = max(reports, key=lambda item: item.period_end, default=None)
    grouped: dict[str, list[FundamentalMetricResponse]] = {code: [] for code in _DIMENSIONS}
    for metric in snapshot.metrics:
        response = FundamentalMetricResponse.from_domain(metric)
        grouped[response.dimension].append(response)
    freshness = "unavailable"
    if latest is not None:
        freshness = (
            "stale" if (effective_as_of.date() - latest.period_end).days > 240 else "current"
        )
    return FundamentalResearchResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        as_of=effective_as_of,
        latest_report_period=latest.period_end if latest else None,
        latest_report_published_at=latest.published_at if latest else None,
        published_at_precision=latest.published_at_precision if latest else None,
        issuer_type=latest.issuer_type if latest else stock.issuer_type,
        provider=latest.provider if latest else None,
        data_version=snapshot.data_version,
        metric_definition_version=snapshot.metric_version,
        freshness=freshness,
        dimensions=[
            FundamentalDimensionResponse(code=code, display_name=name, items=grouped[code])
            for code, name in _DIMENSIONS.items()
        ],
    )


@router.get(
    "/stocks/{symbol}/financials/periods",
    response_model=FinancialPeriodListResponse,
    tags=["fundamentals"],
)
async def get_financial_periods(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    as_of: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 12,
) -> FinancialPeriodListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    effective_as_of = as_of
    if effective_as_of is not None and effective_as_of.tzinfo is None:
        effective_as_of = effective_as_of.replace(tzinfo=UTC)
    reports = await service.list_reports(symbol, as_of=effective_as_of, limit=limit)
    items = [FinancialPeriodResponse.from_domain(item) for item in reports]
    return FinancialPeriodListResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        items=items,
        total=len(items),
    )


@router.get(
    "/stocks/{symbol}/valuations",
    response_model=ValuationListResponse,
    tags=["fundamentals"],
)
async def get_valuations(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    start: date | None = None,
    end: date | None = None,
    metrics: str | None = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 4000,
) -> ValuationListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    requested_codes = (
        tuple(item.strip() for item in metrics.split(",") if item.strip()) if metrics else None
    )
    if requested_codes and not set(requested_codes).issubset(_VALUATION_CODES):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported valuation metric",
        )
    observations = await service.list_valuations(
        symbol,
        start=start,
        end=end,
        metric_codes=requested_codes,
        limit=limit,
    )
    dates = [item.trade_date for item in observations]
    return ValuationListResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        items=[ValuationObservationResponse.from_domain(item) for item in observations],
        total=len(observations),
        coverage=ValuationCoverageResponse(
            start=min(dates, default=None),
            end=max(dates, default=None),
            sample_count=len(observations),
            metric_codes=sorted({item.metric_code for item in observations}),
        ),
    )


@router.get("/watchlists", response_model=list[WatchlistResponse], tags=["watchlists"])
async def list_watchlists(
    user_id: CurrentUserId, repository: WatchlistRepo
) -> list[WatchlistResponse]:
    return [WatchlistResponse.from_domain(item) for item in await repository.list_for_user(user_id)]


@router.post(
    "/watchlists",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["watchlists"],
)
async def create_watchlist(
    payload: CreateWatchlistRequest, user_id: CurrentUserId, repository: WatchlistRepo
) -> WatchlistResponse:
    item = await repository.create(Watchlist(user_id=user_id, name=payload.name))
    return WatchlistResponse.from_domain(item)


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["watchlists"],
)
async def add_watchlist_item(
    watchlist_id: UUID,
    payload: AddWatchlistItemRequest,
    user_id: CurrentUserId,
    repository: WatchlistRepo,
) -> WatchlistResponse:
    item = await repository.get_owned(watchlist_id, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    item.add(payload.symbol)
    return WatchlistResponse.from_domain(await repository.save(item))
