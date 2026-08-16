from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient
from zhaoniu_api.dependencies import get_research_service, get_stock_repository
from zhaoniu_api.fundamentals.models import MetricBasis, MetricStatus
from zhaoniu_api.infrastructure.mock_repositories import (
    InMemoryFundamentalRepository,
    InMemoryResearchRepository,
    InMemoryStockRepository,
)
from zhaoniu_api.main import create_app
from zhaoniu_api.research.models import FundamentalMetricPoint
from zhaoniu_api.research.rules import evaluate_rules
from zhaoniu_api.research.service import (
    DeterministicResearchService,
    scope_observations_to_snapshot,
)


def _point(
    code: str,
    value: str,
    period_end: date,
    fiscal_period: str,
    *,
    basis: MetricBasis = MetricBasis.STANDALONE,
    detail: dict[str, object] | None = None,
) -> FundamentalMetricPoint:
    fingerprint = f"{code}:{period_end}:{value}"
    return FundamentalMetricPoint(
        id=uuid5(NAMESPACE_URL, fingerprint),
        canonical_symbol="600519.SH",
        code=code,
        value=Decimal(value),
        unit="percent",
        status=MetricStatus.AVAILABLE,
        period_end=period_end,
        fiscal_period=fiscal_period,
        basis=basis,
        known_at=datetime(2026, 8, 16, tzinfo=UTC),
        metric_version="fundamentals-v1",
        input_fingerprint=fingerprint,
        detail=detail or {},
    )


def _evaluate(points: list[FundamentalMetricPoint], issuer_type: str = "general"):
    return evaluate_rules(
        symbol="600519.SH",
        issuer_type=issuer_type,
        template_version="fundamental_general:v1",
        points=points,
        reports=[],
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


def test_consecutive_improvement_requires_three_consecutive_quarters() -> None:
    two_points = [
        _point("revenue_single_quarter_yoy", "-15", date(2026, 3, 31), "Q1"),
        _point("revenue_single_quarter_yoy", "-10", date(2026, 6, 30), "H1"),
    ]
    assert not [item for item in _evaluate(two_points) if item.rule_id.startswith("growth.")]

    three_points = [
        _point("revenue_single_quarter_yoy", "-18", date(2025, 12, 31), "FY"),
        *two_points,
    ]
    observations = [item for item in _evaluate(three_points) if item.rule_id.startswith("growth.")]
    assert len(observations) == 1
    assert observations[0].observation_type == "consecutive_improvement"
    assert observations[0].calculation.change_value == Decimal("8")


def test_zero_crossing_takes_priority_over_momentum_card() -> None:
    observations = _evaluate(
        [
            _point("parent_net_profit_single_quarter_yoy", "-8", date(2025, 12, 31), "FY"),
            _point("parent_net_profit_single_quarter_yoy", "-3", date(2026, 3, 31), "Q1"),
            _point("parent_net_profit_single_quarter_yoy", "2", date(2026, 6, 30), "H1"),
        ]
    )
    growth = [item for item in observations if item.rule_id.startswith("growth.")]
    assert len(growth) == 1
    assert growth[0].observation_type == "turned_positive"


def test_growth_gap_boundary_is_inclusive_and_uses_percentage_points() -> None:
    period = date(2026, 6, 30)
    below = _evaluate(
        [
            _point(
                "accounts_receivable_yoy", "29.99", period, "H1", basis=MetricBasis.POINT_IN_TIME
            ),
            _point("revenue_yoy", "10", period, "H1", basis=MetricBasis.YTD),
        ]
    )
    assert not [item for item in below if item.rule_id == "quality.ar_revenue_growth_gap"]

    boundary = _evaluate(
        [
            _point("accounts_receivable_yoy", "30", period, "H1", basis=MetricBasis.POINT_IN_TIME),
            _point("revenue_yoy", "10", period, "H1", basis=MetricBasis.YTD),
        ]
    )
    matches = [item for item in boundary if item.rule_id == "quality.ar_revenue_growth_gap"]
    assert len(matches) == 1
    assert matches[0].calculation.change_unit == "percentage_point"


def test_percentile_rule_distinguishes_state_from_threshold_crossing() -> None:
    detail = {"sample_count": 727}
    assert not _evaluate(
        [
            _point(
                "pe_ttm_percentile_3y",
                "79.9",
                date(2026, 8, 15),
                "market",
                basis=MetricBasis.POINT_IN_TIME,
                detail=detail,
            )
        ]
    )
    state = _evaluate(
        [
            _point(
                "pe_ttm_percentile_3y",
                "80",
                date(2026, 8, 15),
                "market",
                basis=MetricBasis.POINT_IN_TIME,
                detail=detail,
            )
        ]
    )
    assert state[0].observation_type == "percentile_high"
    crossed = _evaluate(
        [
            _point(
                "pe_ttm_percentile_3y",
                "79",
                date(2026, 8, 14),
                "market",
                basis=MetricBasis.POINT_IN_TIME,
                detail=detail,
            ),
            _point(
                "pe_ttm_percentile_3y",
                "80",
                date(2026, 8, 15),
                "market",
                basis=MetricBasis.POINT_IN_TIME,
                detail=detail,
            ),
        ]
    )
    assert crossed[0].observation_type == "threshold_crossed_up"


def test_general_rules_are_not_applied_to_bank_issuer() -> None:
    points = [
        _point("revenue_single_quarter_yoy", "-18", date(2025, 12, 31), "FY"),
        _point("revenue_single_quarter_yoy", "-15", date(2026, 3, 31), "Q1"),
        _point("revenue_single_quarter_yoy", "-10", date(2026, 6, 30), "H1"),
    ]
    assert _evaluate(points, issuer_type="bank") == ()


def test_observation_identity_is_scoped_to_immutable_snapshot() -> None:
    observations = list(
        _evaluate(
            [
                _point("revenue_single_quarter_yoy", "-18", date(2025, 12, 31), "FY"),
                _point("revenue_single_quarter_yoy", "-10", date(2026, 3, 31), "Q1"),
                _point("revenue_single_quarter_yoy", "-5", date(2026, 6, 30), "H1"),
            ]
        )
    )
    first = scope_observations_to_snapshot(uuid5(NAMESPACE_URL, "snapshot-one"), observations)
    second = scope_observations_to_snapshot(uuid5(NAMESPACE_URL, "snapshot-two"), observations)
    assert first[0].id != second[0].id
    assert first[0].content_fingerprint == second[0].content_fingerprint


async def test_research_snapshot_build_is_idempotent_and_read_only_api_returns_it() -> None:
    repository = InMemoryResearchRepository()
    stocks = InMemoryStockRepository()
    service = DeterministicResearchService(
        stocks=stocks,
        fundamentals=InMemoryFundamentalRepository(),
        research=repository,
    )
    first = await service.build_snapshot("600519", as_of=datetime(2026, 8, 16, tzinfo=UTC))
    second = await service.build_snapshot("600519", as_of=datetime(2026, 8, 16, tzinfo=UTC))
    assert first.status == "succeeded"
    assert second.status == "skipped"
    assert first.snapshot_id == second.snapshot_id
    assert len(repository.snapshots) == 1

    app = create_app()
    app.dependency_overrides[get_stock_repository] = lambda: stocks
    app.dependency_overrides[get_research_service] = lambda: service
    client = TestClient(app)
    response = client.get("/api/v1/stocks/600519/research/snapshot")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["snapshot"]["producer_kind"] == "deterministic"
    observations = client.get("/api/v1/stocks/600519/research/observations")
    assert observations.status_code == 200
    assert observations.json()["items"] == []
