"""
Yoto API exceptions.

Provides a clean exception hierarchy for API error handling.
"""

from typing import Optional


class YotoApiError(Exception):
    """Base exception for all Yoto API errors."""

    pass


class YotoAuthError(YotoApiError):
    """Authentication/authorization errors."""

    pass


class YotoRateLimitError(YotoApiError):
    """Rate limiting errors."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class YotoValidationError(YotoApiError):
    """Request validation errors."""

    pass


class YotoNotFoundError(YotoApiError):
    """Resource not found."""

    pass


class YotoServerError(YotoApiError):
    """Server-side errors."""

    pass


class YotoNetworkError(YotoApiError):
    """Network connectivity errors."""

    pass


class YotoTimeoutError(YotoApiError):
    """Request timeout errors."""

    pass
