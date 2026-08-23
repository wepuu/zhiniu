class MarketDataError(Exception):
    """Base error for failures that may be safely recorded in a sync run."""

    reason_code = "provider_invalid_response"


class ProviderUnavailableError(MarketDataError):
    reason_code = "provider_connection_failed"


class ProviderProxyUnavailableError(ProviderUnavailableError):
    reason_code = "provider_proxy_unavailable"


class ProviderTimeoutError(ProviderUnavailableError):
    reason_code = "provider_timeout"


class ProviderConnectionError(ProviderUnavailableError):
    reason_code = "provider_connection_failed"


class ProviderRateLimitedError(MarketDataError):
    reason_code = "provider_rate_limited"


class ProviderInvalidResponseError(MarketDataError):
    reason_code = "provider_invalid_response"


class DataNormalizationError(MarketDataError):
    reason_code = "provider_invalid_response"


class DataQualityError(MarketDataError):
    reason_code = "provider_invalid_response"


def safe_market_error_code(exc: Exception) -> str:
    """Return a stable code without exposing URLs, proxy settings or response bodies."""

    return str(getattr(exc, "reason_code", "provider_invalid_response"))
