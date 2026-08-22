from datetime import UTC, datetime

from fastapi.testclient import TestClient
from zhaoniu_api.company_timeline.models import (
    CompanyTimelineCoverage,
    CompanyTimelineEnvelope,
    CompanyTimelineSummary,
)
from zhaoniu_api.dependencies import get_company_timeline_service
from zhaoniu_api.main import create_app


class _TimelineService:
    async def get(self, symbol: str, **_: object) -> CompanyTimelineEnvelope:
        return CompanyTimelineEnvelope(
            status="empty",
            symbol="600519",
            canonical_symbol="600519.SH",
            query_cutoff=datetime(2026, 8, 22, tzinfo=UTC),
            summary=CompanyTimelineSummary(),
            coverage=CompanyTimelineCoverage(
                fundamental="ready", peer="ready", corporate_event="ready"
            ),
        )


def test_timeline_api_has_explicit_empty_state() -> None:
    app = create_app()
    app.dependency_overrides[get_company_timeline_service] = lambda: _TimelineService()
    response = TestClient(app).get("/api/v1/stocks/600519/timeline")
    assert response.status_code == 200
    assert response.json()["status"] == "empty"
    assert response.json()["coverage"]["corporate_event"] == "ready"
