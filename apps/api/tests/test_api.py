from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from zhaoniu_api.dependencies import (
    get_current_user_id,
    get_daily_bar_repository,
    get_stock_repository,
    get_watchlist_repository,
    require_csrf,
)
from zhaoniu_api.domain.models import AdjustType, DailyBar
from zhaoniu_api.infrastructure.mock_repositories import (
    InMemoryDailyBarRepository,
    InMemoryStockRepository,
    InMemoryWatchlistRepository,
)
from zhaoniu_api.main import create_app

app = create_app()
stocks = InMemoryStockRepository()
bars = InMemoryDailyBarRepository(
    [
        DailyBar(
            canonical_symbol="600519.SH",
            trade_date=date(2026, 8, 14),
            adjust_type=AdjustType.NONE,
            open=Decimal("1410.00"),
            high=Decimal("1445.00"),
            low=Decimal("1408.00"),
            close=Decimal("1438.20"),
            pre_close=Decimal("1429.34"),
            volume=1234567,
            amount=Decimal("1760000000.00"),
            source="fixture",
            collected_at=datetime(2026, 8, 15, tzinfo=UTC),
        )
    ]
)
watchlists = InMemoryWatchlistRepository()
app.dependency_overrides[get_stock_repository] = lambda: stocks
app.dependency_overrides[get_daily_bar_repository] = lambda: bars
app.dependency_overrides[get_watchlist_repository] = lambda: watchlists
app.dependency_overrides[get_current_user_id] = lambda: UUID(
    "00000000-0000-4000-8000-000000000001"
)
app.dependency_overrides[require_csrf] = lambda: None
client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stock_search_and_detail() -> None:
    response = client.get("/api/v1/stocks/search", params={"q": "600519"})
    assert response.status_code == 200
    assert response.json()["items"][0]["symbol"] == "600519"
    detail = client.get("/api/v1/stocks/600519.SH")
    assert detail.status_code == 200
    assert detail.json()["canonical_symbol"] == "600519.SH"


def test_daily_bars_contract_and_empty_state() -> None:
    response = client.get("/api/v1/stocks/600519/daily-bars")
    assert response.status_code == 200
    assert response.json()["items"][0]["close"] == "1438.20"
    assert response.json()["items"][0]["pct_change"] == "0.6199"
    assert client.get("/api/v1/stocks/000001/daily-bars").json()["items"] == []
    assert client.get("/api/v1/stocks/600519/daily-bars?adjust=qfq").status_code == 422
    assert client.get("/api/v1/stocks/999999/daily-bars").status_code == 404


def test_watchlist_api_flow() -> None:
    created = client.post("/api/v1/watchlists", json={"name": "Core"})
    assert created.status_code == 201
    watchlist_id = created.json()["id"]
    updated = client.post(f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "600519"})
    assert updated.status_code == 201
    assert updated.json()["items"][0]["symbol"] == "600519.SH"
    membership = client.get("/api/v1/watchlists/membership/600519")
    assert membership.status_code == 200
    assert membership.json()["is_member"] is True
    removed = client.delete(f"/api/v1/watchlists/{watchlist_id}/items/600519")
    assert removed.status_code == 200
    assert removed.json()["items"] == []
