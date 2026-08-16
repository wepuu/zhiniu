from fastapi.testclient import TestClient
from zhaoniu_api.main import create_app

client = TestClient(create_app())


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stock_search_and_detail() -> None:
    response = client.get("/api/v1/stocks/search", params={"q": "茅台"})
    assert response.status_code == 200
    assert response.json()["items"][0]["symbol"] == "600519"
    assert client.get("/api/v1/stocks/600519").status_code == 200


def test_watchlist_api_flow() -> None:
    created = client.post("/api/v1/watchlists", json={"name": "核心观察"})
    assert created.status_code == 201
    watchlist_id = created.json()["id"]
    updated = client.post(f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "600519"})
    assert updated.status_code == 201
    assert updated.json()["items"][0]["symbol"] == "600519"
