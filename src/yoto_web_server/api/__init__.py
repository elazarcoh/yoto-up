"""
Yoto API client package.

Provides a clean, async API client for interacting with the Yoto API.
"""

from yoto_web_server.api.client import YotoApiClient
from yoto_web_server.api.config import YotoApiConfig
from yoto_web_server.api.exceptions import (
    YotoApiError,
    YotoAuthError,
    YotoNetworkError,
    YotoNotFoundError,
    YotoRateLimitError,
    YotoServerError,
    YotoTimeoutError,
    YotoValidationError,
)
from yoto_web_server.api.models import (
    Card,
    CardContent,
    CardMetadata,
    Chapter,
    Device,
    TokenData,
    Track,
)

__all__ = [
    # Client
    "YotoApiClient",
    "YotoApiConfig",
    # Exceptions
    "YotoApiError",
    "YotoAuthError",
    "YotoNetworkError",
    "YotoNotFoundError",
    "YotoRateLimitError",
    "YotoServerError",
    "YotoTimeoutError",
    "YotoValidationError",
    # Models
    "Card",
    "CardContent",
    "CardMetadata",
    "Chapter",
    "Device",
    "TokenData",
    "Track",
]
