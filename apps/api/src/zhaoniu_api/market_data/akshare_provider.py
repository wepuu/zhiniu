import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

from zhaoniu_api.market_data.errors import (
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from zhaoniu_api.ports.providers import RawDailyBar, RawStock


class AKShareProvider:
    name = "akshare"

    def __init__(self, sdk: Any | None = None, *, max_concurrency: int = 2) -> None:
        self._sdk = sdk
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def _load_sdk(self) -> Any:
        if self._sdk is None:
            try:
                import akshare  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ProviderUnavailableError("AKShare is not installed") from exc
            self._sdk = akshare
        return self._sdk

    async def _call(self, function: Callable[[], Any]) -> Any:
        async with self._semaphore:
            try:
                return await asyncio.to_thread(function)
            except Exception as exc:
                message = str(exc).lower()
                if "429" in message or "rate" in message or "too many" in message:
                    raise ProviderRateLimitedError(
                        "AKShare upstream rate limited the request"
                    ) from exc
                raise ProviderUnavailableError("AKShare request failed") from exc

    @staticmethod
    def _records(frame: Any) -> list[dict[str, object]]:
        if frame is None or not hasattr(frame, "to_dict"):
            raise ProviderInvalidResponseError("AKShare returned a non-tabular response")
        records = frame.to_dict(orient="records")
        if not isinstance(records, list):
            raise ProviderInvalidResponseError("AKShare returned an invalid record collection")
        return records

    async def get_stock_master(self) -> list[RawStock]:
        sdk = self._load_sdk()
        frame = await self._call(sdk.stock_info_a_code_name)
        return [RawStock(provider=self.name, payload=row) for row in self._records(frame)]

    async def get_daily_bars(self, symbol: str, start: date, end: date) -> list[RawDailyBar]:
        sdk = self._load_sdk()
        frame = await self._call(
            lambda: sdk.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
        )
        return [
            RawDailyBar(provider=self.name, requested_symbol=symbol, payload=row)
            for row in self._records(frame)
        ]
