import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

from zhaoniu_api.market_data.errors import (
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from zhaoniu_api.ports.providers import RawFinancialStatement, RawValuationObservation

_STATEMENTS = ("利润表", "资产负债表", "现金流量表")
_VALUATION_INDICATORS = {
    "pe_ttm": "市盈率(TTM)",
    "pb": "市净率",
    "pcf": "市现率",
    "market_cap": "总市值",
}


class AKShareFinancialProvider:
    """Development/evaluation adapter for AKShare's upstream financial endpoints."""

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
                raise ProviderUnavailableError("AKShare financial request failed") from exc

    @staticmethod
    def _records(frame: Any) -> list[dict[str, object]]:
        if frame is None or not hasattr(frame, "to_dict"):
            raise ProviderInvalidResponseError("AKShare returned a non-tabular response")
        records = frame.to_dict(orient="records")
        if not isinstance(records, list):
            raise ProviderInvalidResponseError("AKShare returned an invalid record collection")
        return records

    @staticmethod
    def _sina_symbol(symbol: str) -> str:
        prefix = (
            "sh"
            if symbol.startswith(("6", "9"))
            else "bj"
            if symbol.startswith(("4", "8"))
            else "sz"
        )
        return f"{prefix}{symbol}"

    async def get_financial_statements(
        self, symbol: str, start_year: int
    ) -> list[RawFinancialStatement]:
        sdk = self._load_sdk()
        vendor_symbol = self._sina_symbol(symbol)

        async def fetch(statement_type: str) -> list[RawFinancialStatement]:
            frame = await self._call(
                lambda: sdk.stock_financial_report_sina(stock=vendor_symbol, symbol=statement_type)
            )
            rows: list[RawFinancialStatement] = []
            for payload in self._records(frame):
                report_date = str(payload.get("报告日", ""))
                if report_date[:4].isdigit() and int(report_date[:4]) >= start_year:
                    rows.append(
                        RawFinancialStatement(
                            provider=self.name,
                            requested_symbol=symbol,
                            statement_type=statement_type,
                            payload=payload,
                        )
                    )
            return rows

        batches = await asyncio.gather(*(fetch(statement) for statement in _STATEMENTS))
        return [row for batch in batches for row in batch]

    async def get_valuation_observations(
        self, symbol: str, start: date, end: date
    ) -> list[RawValuationObservation]:
        sdk = self._load_sdk()
        years = max(1, end.year - start.year)
        period = "近三年" if years <= 3 else "近五年" if years <= 5 else "近十年"

        async def fetch(metric_code: str, indicator: str) -> list[RawValuationObservation]:
            frame = await self._call(
                lambda: sdk.stock_zh_valuation_baidu(
                    symbol=symbol, indicator=indicator, period=period
                )
            )
            rows: list[RawValuationObservation] = []
            for payload in self._records(frame):
                observed_on = payload.get("date")
                if isinstance(observed_on, date) and start <= observed_on <= end:
                    rows.append(
                        RawValuationObservation(
                            provider=self.name,
                            requested_symbol=symbol,
                            metric_code=metric_code,
                            payload=payload,
                        )
                    )
            return rows

        batches = await asyncio.gather(
            *(fetch(code, indicator) for code, indicator in _VALUATION_INDICATORS.items())
        )
        return [row for batch in batches for row in batch]
