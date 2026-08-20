from datetime import UTC, datetime, timedelta

from zhaoniu_api.research_feed.service import should_deliver_alert


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
