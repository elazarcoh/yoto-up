"""
Yoto API configuration.
"""

from pydantic import BaseModel


class YotoApiConfig(BaseModel):
    """Configuration for Yoto API client."""

    client_id: str
    base_url: str = "https://api.yotoplay.com"
    auth_url: str = "https://login.yotoplay.com"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    model_config = {"frozen": True}
