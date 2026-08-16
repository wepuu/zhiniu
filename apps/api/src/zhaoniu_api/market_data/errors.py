class MarketDataError(Exception):
    """Base error for failures that may be safely recorded in a sync run."""


class ProviderUnavailableError(MarketDataError):
    pass


class ProviderRateLimitedError(MarketDataError):
    pass


class ProviderInvalidResponseError(MarketDataError):
    pass


class DataNormalizationError(MarketDataError):
    pass


class DataQualityError(MarketDataError):
    pass
