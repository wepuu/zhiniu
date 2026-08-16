from uuid import uuid4

from zhaoniu_api.domain.models import Watchlist


def test_watchlist_deduplicates_symbols() -> None:
    watchlist = Watchlist(user_id=uuid4(), name="观察")
    watchlist.add("600519")
    watchlist.add("600519")
    assert [item.symbol for item in watchlist.items] == ["600519"]
