from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from zhaoniu_api.config import Settings
from zhaoniu_api.research_feed.service import ResearchFeedService, should_deliver_alert


class _EmptyScalarResult:
    def all(self) -> list[Any]:
        return []


class _CapturingSession:
    def __init__(self) -> None:
        self.statement: Any = None

    async def scalars(self, statement: Any) -> _EmptyScalarResult:
        self.statement = statement
        return _EmptyScalarResult()


def test_historical_signal_is_not_backfilled_to_new_watchlist_membership() -> None:
    known_at = datetime(2026, 8, 18, 9, tzinfo=UTC)
    assert not should_deliver_alert(
        signal_known_at=known_at,
        membership_added_at=known_at + timedelta(days=1),
        signal_attention="important",
        minimum_attention="important",
        enabled=True,
        source_enabled=True,
    )


def test_new_signal_after_membership_creates_a_deterministic_match() -> None:
    membership_at = datetime(2026, 8, 18, 9, tzinfo=UTC)
    assert should_deliver_alert(
        signal_known_at=membership_at + timedelta(minutes=1),
        membership_added_at=membership_at,
        signal_attention="important",
        minimum_attention="notice",
        enabled=True,
        source_enabled=True,
    )


def test_alert_match_respects_attention_and_source_settings() -> None:
    membership_at = datetime(2026, 8, 18, 9, tzinfo=UTC)
    assert not should_deliver_alert(
        signal_known_at=membership_at + timedelta(minutes=1),
        membership_added_at=membership_at,
        signal_attention="info",
        minimum_attention="important",
        enabled=True,
        source_enabled=True,
    )
    assert not should_deliver_alert(
        signal_known_at=membership_at + timedelta(minutes=1),
        membership_added_at=membership_at,
        signal_attention="important",
        minimum_attention="important",
        enabled=True,
        source_enabled=False,
    )


async def test_feed_collapses_equivalent_signal_versions_before_pagination() -> None:
    session = _CapturingSession()
    service = ResearchFeedService(session, Settings())  # type: ignore[arg-type]

    response = await service.feed(
        uuid4(), cursor=None, limit=40, source_kind=None, minimum_attention=None
    )

    statement = str(session.statement)
    assert "row_number() OVER" in statement
    assert "research_signals.dedup_group_key" in statement
    assert "anon_1.dedup_rank =" in statement
    assert response.today.total == 0
    assert response.recent.total == 0
