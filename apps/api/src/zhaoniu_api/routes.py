from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from zhaoniu_api.dependencies import CurrentUserId, StockRepo, WatchlistRepo
from zhaoniu_api.domain.models import Watchlist
from zhaoniu_api.schemas import (
    AddWatchlistItemRequest,
    CreateWatchlistRequest,
    HealthResponse,
    StockResponse,
    StockSearchResponse,
    WatchlistResponse,
)

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
