from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from zhaoniu_api.config import Settings
from zhaoniu_api.coverage.models import (
    BetaFeedbackCreate,
    CoverageDimension,
    StockCoverageResponse,
)
from zhaoniu_api.coverage.policy import DatasetPolicyRegistry
from zhaoniu_api.coverage.service import plan_actions, stable_hash
from zhaoniu_api.dependencies import get_coverage_service
from zhaoniu_api.main import create_app


def _dimensions() -> list[CoverageDimension]:
    return [
        CoverageDimension(dimension="market", availability="ready", freshness="current"),
        CoverageDimension(
            dimension="financial",
            availability="missing_source_data",
            reason_codes=["financial_missing_report"],
        ),
        CoverageDimension(
            dimension="fundamental_research",
            availability="not_built",
            reason_codes=["fundamental_snapshot_not_built"],
        ),
        CoverageDimension(dimension="industry", availability="ready", freshness="current"),
        CoverageDimension(
            dimension="peer_research",
            availability="not_built",
            reason_codes=["peer_research_not_built"],
        ),
        CoverageDimension(dimension="event_radar", availability="ready", freshness="current"),
        CoverageDimension(dimension="screening", availability="ready", freshness="current"),
        CoverageDimension(dimension="ai_research", availability="disabled"),
    ]


def test_coverage_planner_is_allow_listed_ordered_and_never_plans_ai() -> None:
    actions = plan_actions(_dimensions())

    assert [item[1] for item in actions] == [
        "sync_financial_statements",
        "sync_valuations",
        "compute_fundamentals",
        "build_research_snapshot",
        "build_peer_research",
    ]
    assert [item[2] for item in actions] == sorted(item[2] for item in actions)
    assert all("ai" not in item[1] for item in actions)


def test_dataset_policy_is_executable_and_fails_closed_outside_evaluation() -> None:
    evaluation = DatasetPolicyRegistry(Settings(coverage_usage_scope="development_evaluation"))
    external = DatasetPolicyRegistry(Settings(coverage_usage_scope="external_beta"))

    assert evaluation.decide("financial").allowed is True
    decision = external.decide("financial")
    assert decision.allowed is False
    assert decision.reason_code == "policy_development_source_only"
    assert external.decide("ai_research").allowed is True


def test_stable_hash_is_key_order_independent() -> None:
    assert stable_hash({"symbol": "600519.SH", "version": 1}) == stable_hash(
        {"version": 1, "symbol": "600519.SH"}
    )


def test_beta_feedback_contract_rejects_short_and_unknown_content() -> None:
    try:
        BetaFeedbackCreate(
            feature_key="stock_research",
            category="bug",
            message="too short",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("short feedback must be rejected")

    item = BetaFeedbackCreate(
        feature_key="stock_research",
        category="data_missing",
        message="600519 的同行研究页面缺少可追溯的行业归属说明。",
    )
    assert item.category == "data_missing"


class _CoverageService:
    async def stock_coverage(self, symbol: str) -> StockCoverageResponse:
        now = datetime(2026, 8, 21, tzinfo=UTC)
        return StockCoverageResponse(
            symbol="600519",
            canonical_symbol="600519.SH",
            snapshot_id=UUID("00000000-0000-4000-8000-000000000013"),
            knowledge_cutoff=now,
            evaluated_at=now,
            coverage_schema_version="research-coverage-v1",
            evaluator_version="coverage-evaluator-v1",
            policy_version="coverage-policy-v1",
            dimensions=_dimensions(),
        )


def test_stock_coverage_api_has_explicit_three_axis_contract() -> None:
    app = create_app()
    app.dependency_overrides[get_coverage_service] = lambda: _CoverageService()

    response = TestClient(app).get("/api/v1/stocks/600519/coverage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_symbol"] == "600519.SH"
    assert payload["dimensions"][0] == {
        "dimension": "market",
        "availability": "ready",
        "freshness": "current",
        "source_health": "unknown",
        "reason_codes": [],
        "latest_artifact_at": None,
    }
