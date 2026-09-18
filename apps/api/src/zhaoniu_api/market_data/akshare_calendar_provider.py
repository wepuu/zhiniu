from __future__ import annotations

from datetime import date

from zhaoniu_api.market_data.akshare_provider import AKShareProvider
from zhaoniu_api.market_data.errors import ProviderInvalidResponseError
from zhaoniu_api.market_data.trading_calendar import (
    CALENDAR_PROVIDER,
    CALENDAR_SOURCE,
    SSE,
    SZSE,
)
from zhaoniu_api.ports.providers import RawTradingSession


class AKShareTradingCalendarProvider(AKShareProvider):
    """Adapter for AKShare's free Sina historical trading-date endpoint.

    Sina publishes one A-share trading-date list.  SSE and SZSE share the same
    open dates, so the adapter emits one raw row for each exchange and leaves
    session semantics to the canonical normalizer.
    """

    name = CALENDAR_PROVIDER

    async def get_trading_sessions(
        self, start: date, end: date
    ) -> list[RawTradingSession]:
        if start > end:
            raise ValueError("calendar range is invalid")
        sdk = self._load_sdk()
        frame = await self._call(sdk.tool_trade_date_hist_sina)
        rows = self._records(frame)
        if not rows:
            raise ProviderInvalidResponseError("trading calendar response is empty")
        sessions: list[RawTradingSession] = []
        for row in rows:
            for exchange in (SSE, SZSE):
                sessions.append(
                    RawTradingSession(
                        provider=CALENDAR_SOURCE,
                        exchange=exchange,
                        payload=dict(row),
                    )
                )
        return sessions
