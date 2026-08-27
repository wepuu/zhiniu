from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from zhaoniu_api.domain.models import AdjustType, DailyBar, Stock, resolve_symbol
from zhaoniu_api.market_data.akshare_provider import SINA_DAILY_SOURCE
from zhaoniu_api.market_data.errors import DataNormalizationError
from zhaoniu_api.ports.providers import RawDailyBar, RawStock


def _first(payload: dict[str, object], *names: str) -> object | None:
    for name in names:
        value = payload.get(name)
        if value is not None and value != "":
            return value
    return None


def _decimal(value: object | None, field: str) -> Decimal:
    if value is None:
        raise DataNormalizationError(f"missing required field: {field}")
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise DataNormalizationError(f"invalid decimal field: {field}") from exc
    if not result.is_finite():
        raise DataNormalizationError(f"non-finite decimal field: {field}")
    return result


def _date(value: object | None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        raise DataNormalizationError("missing required field: trade_date")
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise DataNormalizationError("invalid trade_date") from exc


class AKShareNormalizer:
    def stocks(self, rows: list[RawStock], *, collected_at: datetime | None = None) -> list[Stock]:
        timestamp = collected_at or datetime.now(UTC)
        stocks: list[Stock] = []
        for row in rows:
            ticker_value = _first(row.payload, "code", "代码", "symbol")
            name_value = _first(row.payload, "name", "名称")
            if ticker_value is None or name_value is None:
                raise DataNormalizationError("stock master row is missing code or name")
            resolved = resolve_symbol(str(ticker_value).zfill(6))
            stocks.append(
                Stock(
                    symbol=resolved.ticker,
                    canonical_symbol=resolved.canonical,
                    name=str(name_value).strip(),
                    exchange=resolved.exchange,
                    board=resolved.board,
                    source=row.provider,
                    collected_at=timestamp,
                )
            )
        return stocks

    def daily_bars(
        self, rows: list[RawDailyBar], *, collected_at: datetime | None = None
    ) -> list[DailyBar]:
        timestamp = collected_at or datetime.now(UTC)
        bars: list[DailyBar] = []
        previous_close: dict[str, Decimal] = {}
        ordered_rows = sorted(
            rows,
            key=lambda row: (
                resolve_symbol(row.requested_symbol).canonical,
                _date(_first(row.payload, "日期", "date", "trade_date")),
            ),
        )
        for row in ordered_rows:
            resolved = resolve_symbol(row.requested_symbol)
            close = _decimal(_first(row.payload, "收盘", "close"), "close")
            pre_close_value = _first(row.payload, "昨收", "pre_close")
            pre_close: Decimal | None
            if pre_close_value is None:
                change_value = _first(row.payload, "涨跌额", "change")
                if change_value is not None:
                    pre_close = close - _decimal(change_value, "change")
                elif row.provider == SINA_DAILY_SOURCE:
                    pre_close = previous_close.get(resolved.canonical)
                else:
                    pre_close = None
            else:
                pre_close = _decimal(pre_close_value, "pre_close")
            volume_value = _decimal(_first(row.payload, "成交量", "volume"), "volume")
            if volume_value != volume_value.to_integral_value():
                raise DataNormalizationError("AKShare daily volume must be an integer")
            volume = (
                int(volume_value) if row.provider == SINA_DAILY_SOURCE else int(volume_value) * 100
            )
            bars.append(
                DailyBar(
                    canonical_symbol=resolved.canonical,
                    trade_date=_date(_first(row.payload, "日期", "date", "trade_date")),
                    adjust_type=AdjustType.NONE,
                    open=_decimal(_first(row.payload, "开盘", "open"), "open"),
                    high=_decimal(_first(row.payload, "最高", "high"), "high"),
                    low=_decimal(_first(row.payload, "最低", "low"), "low"),
                    close=close,
                    pre_close=pre_close,
                    volume=volume,
                    amount=_decimal(_first(row.payload, "成交额", "amount"), "amount"),
                    source=row.provider,
                    collected_at=timestamp,
                )
            )
            previous_close[resolved.canonical] = close
        return bars
