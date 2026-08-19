class CorporateEventError(Exception):
    """Base error for disclosure and event processing."""


class DisclosureProviderTransientError(CorporateEventError):
    """Retryable provider network, timeout, rate-limit, or upstream failure."""


class DisclosureProviderInvalidResponse(CorporateEventError):
    """Provider response did not satisfy the expected tabular contract."""


class DisclosureNormalizationError(CorporateEventError):
    """A source row could not be normalized safely."""
