from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

from zhaoniu_api.corporate_events.errors import (
    DisclosureProviderInvalidResponse,
    DisclosureProviderTransientError,
)
from zhaoniu_api.corporate_events.models import EventFamily, RawDisclosure, RawEventFact


class AKShareDisclosureProvider:
    """Controlled-thread adapter for AKShare's public disclosure data functions."""

    name = "akshare"

    def __init__(self, sdk: Any | None = None, *, max_concurrency: int = 2) -> None:
        self._sdk = sdk
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self.last_source_health = "healthy"

    def _load_sdk(self) -> Any:
        if self._sdk is None:
            try:
                import akshare  # type: ignore[import-untyped]
            except ImportError as exc:
                raise DisclosureProviderTransientError("AKShare is not installed") from exc
            self._sdk = akshare
        return self._sdk

    async def _call(self, function: Callable[[], Any]) -> Any:
        async with self._semaphore:
            try:
                return await asyncio.to_thread(function)
            except Exception as exc:
                raise DisclosureProviderTransientError("AKShare disclosure request failed") from exc

    @staticmethod
    def _records(frame: Any) -> list[dict[str, object]]:
        if frame is None or not hasattr(frame, "to_dict"):
            raise DisclosureProviderInvalidResponse("AKShare returned a non-tabular response")
        records = frame.to_dict(orient="records")
        if not isinstance(records, list):
            raise DisclosureProviderInvalidResponse("AKShare returned invalid records")
        return records

    async def get_disclosures(self, symbol: str, start: date, end: date) -> list[RawDisclosure]:
        sdk = self._load_sdk()
        function = getattr(sdk, "stock_zh_a_disclosure_report_cninfo", None)
        if function is None:
            raise DisclosureProviderInvalidResponse("AKShare disclosure function is unavailable")
        frame = await self._call(
            lambda: function(
                symbol=symbol,
                market="沪深京",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        )
        return [
            RawDisclosure(
                provider=self.name,
                source_owner="cninfo",
                requested_symbol=symbol,
                payload=row,
            )
            for row in self._records(frame)
        ]

    async def get_source_facts(self, symbol: str) -> list[RawEventFact]:
        sdk = self._load_sdk()
        self.last_source_health = "healthy"
        facts: list[RawEventFact] = []
        requests: tuple[tuple[str, EventFamily, str, Callable[[], Any]], ...] = (
            (
                "eastmoney",
                EventFamily.SHARE_REPURCHASE,
                "stock_repurchase_em",
                lambda: sdk.stock_repurchase_em(),
            ),
            (
                "cninfo",
                EventFamily.SHARE_PLEDGE,
                "stock_cg_equity_mortgage_cninfo",
                lambda: sdk.stock_cg_equity_mortgage_cninfo(date="全部"),
            ),
            (
                "sina",
                EventFamily.SHARE_UNLOCK,
                "stock_restricted_release_queue_sina",
                lambda: sdk.stock_restricted_release_queue_sina(symbol=symbol),
            ),
        )
        for owner, family, function_name, call in requests:
            if not hasattr(sdk, function_name):
                self.last_source_health = "degraded"
                continue
            try:
                rows = self._records(await self._call(call))
            except DisclosureProviderTransientError:
                self.last_source_health = "degraded"
                continue
            for row in rows:
                row_symbol = _row_symbol(row)
                if row_symbol and row_symbol.zfill(6) != symbol.zfill(6):
                    continue
                facts.append(
                    RawEventFact(
                        provider=self.name,
                        source_owner=owner,
                        requested_symbol=symbol,
                        event_family=family,
                        payload=row,
                    )
                )
        return facts


def _row_symbol(row: dict[str, object]) -> str | None:
    for key in ("股票代码", "证券代码", "代码", "symbol", "code"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).split(".")[0]
    return None
