from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from zhaoniu_api.dependencies import get_peer_research_service, get_stock_repository
from zhaoniu_api.domain.models import Stock
from zhaoniu_api.main import app
from zhaoniu_api.peer_research.engine import compare_metric, numeric_rank_desc, percentile_rank
from zhaoniu_api.peer_research.models import (
    ComparableMetricInput,
    PeerComparisonEnvelope,
    PeerComparisonStatus,
    PeerMetricKind,
)


def _input(symbol: str, value: str, metric_code: str = "roe") -> ComparableMetricInput:
    return ComparableMetricInput(
        symbol=symbol,
        metric_code=metric_code,
        value=Decimal(value),
        unit="percent",
        period_end=date(2025, 12, 31),
        fiscal_period="FY",
        basis="fy",
        metric_version="fundamentals-v1",
        known_at=datetime(2026, 4, 30, tzinfo=UTC),
        source_id=uuid4(),
        source_kind=PeerMetricKind.FUNDAMENTAL,
    )


def test_peer_percentile_uses_midrank_ties() -> None:
    values = [Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")]
    assert percentile_rank(values, Decimal("2")) == Decimal("50.0")
    assert numeric_rank_desc(values, Decimal("2")) == 2


def test_peer_comparison_rejects_small_samples() -> None:
    result = compare_metric(
        "roe",
        PeerMetricKind.FUNDAMENTAL,
        _input("600519.SH", "18"),
        [_input(f"peer{i}.SH", str(i)) for i in range(7)],
    )
    assert result.status == PeerComparisonStatus.INSUFFICIENT_PEERS
    assert result.sample_size == 7


def test_peer_comparison_excludes_negative_pe() -> None:
    company = _input("600519.SH", "20", "pe_ttm")
    peers = [_input(f"peer{i}.SH", str(i + 10), "pe_ttm") for i in range(8)]
    peers.append(_input("loss.SZ", "-3", "pe_ttm"))
    result = compare_metric("pe_ttm", PeerMetricKind.VALUATION, company, peers)
    assert result.status == PeerComparisonStatus.AVAILABLE
    assert result.sample_size == 8
    assert result.excluded_invalid_value_count == 1


class _StockRepo:
    async def get(self, symbol: str) -> Stock | None:
        if symbol == "600519":
            symbol = "600519.SH"
        if symbol == "600519.SH":
            return Stock("600519", "贵州茅台", "SSE", "白酒")
        return None

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        return []

    async def upsert_many(self, stocks: list[Stock]) -> int:
        return len(stocks)


class _PeerService:
    async def get_peer_comparisons(
        self, symbol: str, *, dimension: str | None = None
    ) -> PeerComparisonEnvelope:
        return PeerComparisonEnvelope(
            status="not_built",
            symbol="600519",
            canonical_symbol="600519.SH",
        )

    async def get_peers(self, symbol: str, *, as_of: datetime | None = None):
        raise AssertionError("not used")


def test_peer_comparison_api_returns_explicit_status() -> None:
    app.dependency_overrides[get_stock_repository] = lambda: _StockRepo()
    app.dependency_overrides[get_peer_research_service] = lambda: _PeerService()
    client = TestClient(app)
    response = client.get("/api/v1/stocks/600519/peer-comparisons")
    assert response.status_code == 200
    assert response.json()["status"] == "not_built"
    app.dependency_overrides.clear()

