"""
API Service - Async wrapper around YotoApiClient for the server context.

This service manages the Yoto API client instance and authentication state.
All methods are async and should be awaited.
"""

from typing import Any, Callable, Optional

from loguru import logger

from yoto_up.yoto_api_client import (
    YotoApiClient,
    YotoApiConfig,
    YotoAuthError,
    TokenStorage,
)
from yoto_up.yoto_app import config as yoto_config
from yoto_up import paths
from yoto_up_server.models import AuthStatus


class ApiService:
    """
    Async service for managing Yoto API interactions.

    Wraps the YotoApiClient class and provides server-appropriate
    async lifecycle management and token handling.

    All methods are async and must be awaited.
    """

    def __init__(self) -> None:
        self._api: Optional[YotoApiClient] = None
        self._client_id: str = yoto_config.CLIENT_ID
        self._config = YotoApiConfig(client_id=self._client_id)
        self._token_file = paths.TOKENS_FILE
        # Create token storage directly (not dependent on API initialization)
        # This avoids chicken-and-egg problem when saving tokens during auth
        self._token_storage = TokenStorage(self._token_file)

    async def initialize(self) -> None:
        """Initialize the API client (load stored tokens if available)."""
        if self._api is None:
            self._api = YotoApiClient(
                config=self._config,
                token_file=self._token_file,
            )
            await self._api.initialize()
            logger.debug("API client initialized")

    def get_api(self) -> YotoApiClient:
        """
        Get the underlying API client instance.

        Note: The client must be initialized first via initialize().
        """
        if self._api is None:
            raise RuntimeError(
                "API service not initialized. Call await api_service.initialize() first."
            )
        return self._api

    async def close(self) -> None:
        """Close the API client and cleanup resources."""
        if self._api:
            await self._api.close()
            self._api = None

    def is_authenticated(self) -> bool:
        """
        Check if the user is authenticated.
        
        Returns True if:
        - API client is initialized and has valid tokens, OR
        - Token file exists on disk with valid tokens (tokens not yet loaded)
        """
        # If API is already initialized, use its authentication state
        if self._api is not None:
            return self._api.is_authenticated()
        
        # Otherwise, check if tokens exist on disk
        # This handles the case where tokens were saved before server restart
        try:
            token_data = self._token_storage.load()
            # Need to refresh tokens here if expired
            if token_data and token_data.is_expired():
                return False
            return token_data is not None
        except Exception:
            return False

    def get_auth_status(self) -> AuthStatus:
        """Get current authentication status."""
        return AuthStatus(
            authenticated=self.is_authenticated(),
        )

    async def save_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> None:
        """
        Save authentication tokens using TokenStorage.

        This works independently of API client initialization, solving
        the chicken-and-egg problem where tokens need to be saved during auth
        before the full API client is initialized.
        """
        try:
            from yoto_up.yoto_api_client import TokenData
            import time

            # Calculate expiration time (assuming 1 hour expiry if not specified)
            expires_at = time.time() + 3600

            token_data = TokenData(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )

            # Use direct token storage (no API client dependency)
            self._token_storage.save(token_data)
            logger.info("Tokens saved successfully")

        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise

    def clear_tokens(self) -> None:
        """Clear stored tokens and log out."""
        try:
            # Use direct token storage to clear
            self._token_storage.clear()
            logger.info("Tokens cleared")
        except Exception as e:
            logger.error(f"Failed to clear tokens: {e}")

    async def refresh_tokens(self) -> bool:
        """
        Refresh authentication tokens.

        Returns True if refresh was successful.
        """
        api = self.get_api()

        try:
            # Use the auth client to refresh
            await api.auth.refresh_access_token()
            logger.info("Tokens refreshed successfully")
            return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    async def authenticate(
        self,
        callback: Optional[Callable[[str, str], None]] = None,
        timeout: int = 300,
    ) -> bool:
        """
        Perform device code authentication flow.

        Args:
            callback: Optional callback(verification_url, user_code) for custom UI
            timeout: Maximum time to wait for authentication

        Returns:
            True if authentication successful
        """
        api = self.get_api()

        try:
            await api.authenticate(callback=callback, timeout=timeout)
            logger.info("Authentication successful")
            return True
        except YotoAuthError as e:
            logger.error(f"Authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return False

    # ========================================================================
    # API Methods - Content Management
    # ========================================================================

    async def get_my_content(self) -> Any:  # noqa: F401
        """Get user's content (playlists/cards)."""
        api = self.get_api()
        return await api.get_my_content()

    async def get_myo_content(self) -> Any:  # noqa: F401
        """Alias for get_my_content() for backward compatibility."""
        return await self.get_my_content()

    async def get_card(self, card_id: str) -> Any:  # noqa: F401
        """Get a specific card by ID."""
        api = self.get_api()
        return await api.get_card(card_id)

    async def create_card(self, card: Any) -> Any:  # noqa: F401
        """Create a new card/playlist."""
        api = self.get_api()
        return await api.create_card(card)

    async def update_card(self, card: Any) -> Any:  # noqa: F401
        """Update a card."""
        api = self.get_api()
        return await api.update_card(card)

    async def delete_card(self, card_id: str) -> None:
        """Delete a card."""
        api = self.get_api()
        await api.delete_card(card_id)

    # ========================================================================
    # API Methods - Device Management
    # ========================================================================

    async def get_devices(self) -> Any:  # noqa: F401
        """Get user's devices."""
        api = self.get_api()
        return await api.get_devices()

    async def get_device_status(self, device_id: str) -> Any:  # noqa: F401
        """Get device status."""
        api = self.get_api()
        return await api.get_device_status(device_id)

    async def get_device_config(self, device_id: str) -> Any:  # noqa: F401
        """Get device config."""
        api = self.get_api()
        return await api.get_device_config(device_id)

    async def update_device_config(self, device_id: str, name: str, config: Any) -> Any:  # noqa: F401
        """Update device config."""
        api = self.get_api()
        return await api.update_device_config(device_id, name, config)

    # ========================================================================
    # API Methods - Media Upload
    # ========================================================================

    def calculate_sha256(self, file_path: Any) -> Any:  # noqa: F401
        """Calculate SHA256 of a file (sync method, no async needed)."""
        api = self.get_api()
        return api.calculate_sha256(file_path)

    async def get_audio_upload_url(
        self, sha256: str, filename: Optional[str] = None
    ) -> Any:  # noqa: F401
        """Get audio upload URL."""
        api = self.get_api()
        return await api.get_audio_upload_url(sha256, filename)

    async def upload_audio_file(
        self, upload_url: str, audio_bytes: bytes, mime_type: str = "audio/mpeg"
    ) -> None:
        """Upload audio file."""
        api = self.get_api()
        await api.upload_audio_file(upload_url, audio_bytes, mime_type)

    async def poll_for_transcoding(
        self,
        upload_id: str,
        loudnorm: bool = False,
        poll_interval: float = 2.0,
        max_attempts: int = 120,
        callback: Optional[Callable[[int, int], None]] = None,
    ) -> Any:  # noqa: F401
        """Poll for transcoding completion."""
        api = self.get_api()
        return await api.poll_for_transcoding(
            upload_id, loudnorm, poll_interval, max_attempts, callback
        )

    async def upload_cover_image(
        self,
        image_path: Optional[Any] = None,
        image_url: Optional[str] = None,
        image_data: Optional[bytes] = None,
        autoconvert: bool = True,
        cover_type: Optional[Any] = None,
    ) -> Any:  # noqa: F401
        """Upload cover image."""
        api = self.get_api()
        return await api.upload_cover_image(
            image_path, image_url, image_data, autoconvert, cover_type
        )
