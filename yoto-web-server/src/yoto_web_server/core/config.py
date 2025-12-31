"""
Application configuration using pydantic-settings.

Loads configuration from environment variables with sensible defaults.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1

    # Security
    session_encryption_key: Optional[str] = None
    session_cookie_name: str = "yoto_session"
    session_cookie_secure: bool = False  # Set True in production with HTTPS
    session_cookie_max_age: int = 30 * 24 * 60 * 60  # 30 days

    # Yoto API configuration
    yoto_client_id: str = "GBW0M3PLOXIuXk2ev6EsP0PTBHEbSVpt"
    yoto_base_url: str = "https://api.yotoplay.com"
    yoto_auth_url: str = "https://login.yotoplay.com"
    yoto_api_timeout: float = 30.0

    # Debug configuration
    yoto_up_debug: bool = False
    yoto_up_debug_dir: Path = Path("./debug")

    # Paths
    cache_dir: Path = Path.home() / ".cache" / "yoto-web-server"
    data_dir: Path = Path.home() / ".local" / "share" / "yoto-web-server"

    def get_encryption_key(self) -> bytes:
        """
        Get encryption key for session cookies.

        Raises:
            RuntimeError: If no encryption key is configured
        """
        if self.session_encryption_key:
            return self.session_encryption_key.encode("utf-8")

        raise RuntimeError(
            "SESSION_ENCRYPTION_KEY environment variable is required. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.yoto_up_debug:
            self.yoto_up_debug_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
