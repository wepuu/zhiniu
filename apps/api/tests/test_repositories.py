from uuid import uuid4

import pytest
from zhaoniu_api.domain.models import Watchlist
from zhaoniu_api.infrastructure.mock_repositories import InMemoryWatchlistRepository
from zhaoniu_api.ports.providers import MarketDataProvider
from zhaoniu_api.ports.repositories import StockRepository


def test_port_contracts_are_runtime_structural() -> None:
    assert hasattr(StockRepository, "search")
    assert hasattr(MarketDataProvider, "get_quote")


@pytest.mark.asyncio
async def test_watchlist_ownership_is_enforced() -> None:
    owner = uuid4()
    intruder = uuid4()
    repository = InMemoryWatchlistRepository()
    created = await repository.create(Watchlist(user_id=owner, name="私人观察"))
    assert await repository.get_owned(created.id, owner) is created
    assert await repository.get_owned(created.id, intruder) is None
