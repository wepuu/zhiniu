from uuid import uuid4

import pytest
from zhaoniu_api.domain.models import Watchlist
from zhaoniu_api.infrastructure.mock_repositories import InMemoryWatchlistRepository
from zhaoniu_api.infrastructure.sql_repositories import SQLAlchemyStockRepository
from zhaoniu_api.ports.providers import MarketDataProvider
from zhaoniu_api.ports.repositories import StockRepository


def test_port_contracts_are_runtime_structural() -> None:
    assert hasattr(StockRepository, "search")
    assert hasattr(MarketDataProvider, "get_stock_master")
    assert hasattr(MarketDataProvider, "get_daily_bars")


@pytest.mark.asyncio
async def test_watchlist_ownership_is_enforced() -> None:
    owner = uuid4()
    intruder = uuid4()
    repository = InMemoryWatchlistRepository()
    created = await repository.create(Watchlist(user_id=owner, name="私人观察"))
    assert await repository.get_owned(created.id, owner) is created
    assert await repository.get_owned(created.id, intruder) is None


class _EmptyResult:
    def all(self) -> list[object]:
        return []


class _CapturingSession:
    statement: object | None = None

    async def execute(self, statement: object) -> _EmptyResult:
        self.statement = statement
        return _EmptyResult()


@pytest.mark.asyncio
async def test_stock_search_uses_deterministic_relevance_and_literal_wildcards() -> None:
    session = _CapturingSession()
    repository = SQLAlchemyStockRepository(session)  # type: ignore[arg-type]

    assert await repository.search("贵州%", limit=10) == []
    statement = str(session.statement)
    assert "CASE WHEN" in statement
    assert "lower(stocks.ticker)" in statement
    assert "stocks.search_name" in statement
    assert "stocks.name_pinyin" in statement
    assert "stocks.name_pinyin_initials" in statement
    assert "ESCAPE" in statement


def test_stock_name_search_terms_cover_chinese_pinyin_and_initials() -> None:
    from zhaoniu_api.stock_search import normalize_stock_search_text, stock_name_search_terms

    assert stock_name_search_terms("贵州茅台") == ("贵州茅台", "guizhoumaotai", "gzmt")
    assert normalize_stock_search_text("Mao Tai") == "maotai"
    assert normalize_stock_search_text("GUI-ZHOU_MAO.TAI") == "guizhoumaotai"
