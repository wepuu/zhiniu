from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from zhaoniu_api.corporate_events.engine import attention_for, classify_title, extract_candidate
from zhaoniu_api.corporate_events.models import (
    CorporateEventResponse,
    DisclosureDocument,
    EventFamily,
    EventRadarEnvelope,
    EventType,
    RawDisclosure,
)
from zhaoniu_api.corporate_events.normalizer import (
    AKShareDisclosureNormalizer,
    parse_source_datetime,
)
from zhaoniu_api.dependencies import get_corporate_event_service
from zhaoniu_api.main import create_app


def _document(title: str) -> DisclosureDocument:
    published = datetime(2026, 8, 1, tzinfo=UTC)
    return DisclosureDocument(
        id=uuid4(),
        symbol="600519.SH",
        source_owner="cninfo",
        source_document_id="doc-1",
        title=title,
        source_url="https://example.invalid/doc-1",
        source_published_at=published,
        source_published_precision="date",
        known_at=published + timedelta(days=1),
        ingested_at=published + timedelta(days=2),
        content_fingerprint="a" * 64,
    )


def test_classifier_covers_four_phase_seven_families() -> None:
    cases = {
        "关于回购股份方案的公告": EventFamily.SHARE_REPURCHASE,
        "关于控股股东股份质押的公告": EventFamily.SHARE_PLEDGE,
        "限售股上市流通公告": EventFamily.SHARE_UNLOCK,
        "关于收到交易所问询函的公告": EventFamily.REGULATORY_ACTION,
    }
    for title, expected in cases.items():
        classification = classify_title(title)
        assert classification.status == "classified"
        assert classification.event_family == expected


def test_classifier_is_fail_closed_for_ambiguous_and_unknown_titles() -> None:
    assert classify_title("回购方案暨股份质押公告").status == "ambiguous"
    assert classify_title("年度股东大会决议公告").status == "unclassified"
    assert classify_title("关于回购注销部分限制性股票的公告").status == "unsupported"


def test_date_only_publication_uses_conservative_known_at() -> None:
    published, precision, known_at = parse_source_datetime(date(2026, 8, 1))
    assert precision == "date"
    assert known_at - published == timedelta(days=1)


def test_normalizer_uses_source_owner_and_stable_identity() -> None:
    raw = RawDisclosure(
        provider="akshare",
        source_owner="cninfo",
        requested_symbol="600519",
        payload={
            "公告标题": "关于回购股份方案的公告",
            "公告日期": "2026-08-01",
            "公告链接": "https://example.invalid/notice",
        },
    )
    normalizer = AKShareDisclosureNormalizer()
    first = normalizer.disclosures([raw], ingested_at=datetime(2026, 8, 3, tzinfo=UTC))[0]
    second = normalizer.disclosures([raw], ingested_at=datetime(2026, 8, 4, tzinfo=UTC))[0]
    assert first.source_owner == "cninfo"
    assert first.source_document_id == second.source_document_id
    assert first.content_fingerprint == second.content_fingerprint


def test_extractor_preserves_lineage_and_does_not_assign_attention() -> None:
    document = _document("关于回购股份方案的公告")
    candidate = extract_candidate(document, classify_title(document.title))
    assert candidate is not None
    assert candidate.extraction_status == "partial"
    assert "attention_level" not in candidate.typed_payload
    assert candidate.field_lineage["title"]["document_id"] == str(document.id)


def test_attention_rules_are_deterministic() -> None:
    assert attention_for(EventType.INVESTIGATION_OPENED)[0] == "important"
    assert attention_for(EventType.PLEDGE_CREATED)[0] == "notice"
    assert attention_for(EventType.REPURCHASE_COMPLETED)[0] == "info"


class _EventService:
    async def get_radar(self, symbol: str) -> EventRadarEnvelope:
        return EventRadarEnvelope(
            status="no_events",
            freshness="current",
            source_health="healthy",
            coverage_status="complete",
            symbol="600519",
            canonical_symbol="600519.SH",
            recent_items=[],
            upcoming_items=[],
        )

    async def list_events(self, symbol: str, *, limit: int = 100):
        raise AssertionError("not used")

    async def get_event(self, symbol: str, event_id: UUID) -> CorporateEventResponse | None:
        return None


def test_event_radar_api_has_explicit_empty_state() -> None:
    app = create_app()
    app.dependency_overrides[get_corporate_event_service] = lambda: _EventService()
    response = TestClient(app).get("/api/v1/stocks/600519/event-radar")
    assert response.status_code == 200
    assert response.json()["status"] == "no_events"
    assert response.json()["coverage_status"] == "complete"


def test_event_detail_returns_404_when_event_is_absent() -> None:
    app = create_app()
    app.dependency_overrides[get_corporate_event_service] = lambda: _EventService()
    response = TestClient(app).get(f"/api/v1/stocks/600519/events/{uuid4()}")
    assert response.status_code == 404
