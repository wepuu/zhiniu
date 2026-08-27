import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

from zhaoniu_api.domain.models import Exchange, resolve_symbol
from zhaoniu_api.market_data.errors import (
    ProviderConnectionError,
    ProviderInvalidResponseError,
    ProviderProxyUnavailableError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from zhaoniu_api.ports.providers import RawDailyBar, RawStock

SINA_DAILY_SOURCE = "akshare_sina"
_TRANSIENT_PROVIDER_ERRORS = (
    ProviderProxyUnavailableError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitedError,
)


class AKShareProvider:
    name = "akshare"

    def __init__(
        self,
        sdk: Any | None = None,
        *,
        max_concurrency: int = 2,
        max_attempts: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        if not 1 <= max_attempts <= 2:
            raise ValueError("AKShare max_attempts must be between 1 and 2")
        self._sdk = sdk
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

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
            for attempt in range(1, self._max_attempts + 1):
                try:
                    return await asyncio.to_thread(function)
                except Exception as exc:
                    classified = self._classify_exception(exc)
                    if (
                        not isinstance(
                            classified,
                            _TRANSIENT_PROVIDER_ERRORS,
                        )
                        or attempt == self._max_attempts
                    ):
                        raise classified from None
                    await asyncio.sleep(self._retry_backoff_seconds)
        raise AssertionError("AKShare retry loop exhausted without a result")

    @staticmethod
    def _classify_exception(exc: Exception) -> Exception:
        if isinstance(exc, ProviderInvalidResponseError):
            return exc
        kind = type(exc).__name__.lower()
        message = str(exc).lower()
        if "proxy" in kind or "proxy" in message:
            return ProviderProxyUnavailableError("provider_proxy_unavailable")
        if isinstance(exc, TimeoutError) or "timeout" in kind or "timed out" in message:
            return ProviderTimeoutError("provider_timeout")
        if "429" in message or "rate limit" in message or "too many requests" in message:
            return ProviderRateLimitedError("provider_rate_limited")
        connection_markers = (
            "connection",
            "remote disconnected",
            "remotedisconnected",
            "connection aborted",
            "connection reset",
            "protocolerror",
        )
        if isinstance(exc, ConnectionError) or any(
            marker in kind or marker in message for marker in connection_markers
        ):
            return ProviderConnectionError("provider_connection_failed")
        return ProviderInvalidResponseError("provider_invalid_response")

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
        try:
            frame = await self._call(
                lambda: sdk.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="",
                )
            )
            source = self.name
        except _TRANSIENT_PROVIDER_ERRORS as primary_error:
            sina_symbol = self._sina_symbol(symbol)
            if sina_symbol is None:
                raise primary_error from None
            frame = await self._call(
                lambda: sdk.stock_zh_a_daily(
                    symbol=sina_symbol,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="",
                )
            )
            source = SINA_DAILY_SOURCE
        return [
            RawDailyBar(provider=source, requested_symbol=symbol, payload=row)
            for row in self._records(frame)
        ]

    @staticmethod
    def _sina_symbol(symbol: str) -> str | None:
        resolved = resolve_symbol(symbol)
        prefix = {
            Exchange.SSE: "sh",
            Exchange.SZSE: "sz",
        }.get(resolved.exchange)
        return f"{prefix}{resolved.ticker}" if prefix is not None else None
