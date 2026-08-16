from zhaoniu_api.domain.models import DailyBar
from zhaoniu_api.market_data.errors import DataQualityError


def validate_daily_bar_batch(bars: list[DailyBar], expected_symbol: str) -> list[DailyBar]:
    dates = [bar.trade_date for bar in bars]
    if len(dates) != len(set(dates)):
        raise DataQualityError("daily-bar batch contains duplicate trade dates")
    for bar in bars:
        if bar.canonical_symbol != expected_symbol:
            raise DataQualityError("daily-bar batch contains a mismatched symbol")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise DataQualityError("OHLC values must be positive")
        if bar.high < max(bar.open, bar.low, bar.close):
            raise DataQualityError("high is below an OHLC value")
        if bar.low > min(bar.open, bar.high, bar.close):
            raise DataQualityError("low is above an OHLC value")
        if bar.pre_close is not None and bar.pre_close <= 0:
            raise DataQualityError("pre_close must be positive")
        if bar.volume < 0 or bar.amount < 0:
            raise DataQualityError("volume and amount must be non-negative")
    return sorted(bars, key=lambda item: item.trade_date)
