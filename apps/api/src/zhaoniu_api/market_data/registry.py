from collections.abc import Iterable

from zhaoniu_api.market_data.errors import MarketDataError, ProviderUnavailableError
from zhaoniu_api.ports.providers import MarketDataProvider


class ProviderRegistry:
    def __init__(self, providers: Iterable[MarketDataProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> MarketDataProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderUnavailableError(
                f"market-data provider is not registered: {name}"
            ) from exc


class FallbackEngine:
    """Try providers in order. Phase 1 uses this contract only with fake providers in tests."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        self._providers = providers

    async def daily_bars(self, symbol: str, start: object, end: object) -> tuple[str, list[object]]:
        failures: list[str] = []
        for provider in self._providers:
            try:
                # The public engine is deliberately generic; adapters keep their precise port.
                rows = await provider.get_daily_bars(symbol, start, end)  # type: ignore[arg-type]
                return provider.name, list(rows)
            except MarketDataError as exc:
                failures.append(f"{provider.name}:{type(exc).__name__}")
        raise ProviderUnavailableError("all providers failed: " + ", ".join(failures))
