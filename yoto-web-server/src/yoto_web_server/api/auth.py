"""
Yoto API Authentication Client.

Handles OAuth device code flow and token management.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Callable, Optional
from urllib.parse import urljoin

import httpx
from loguru import logger

from yoto_web_server.api.config import YotoApiConfig
from yoto_web_server.api.exceptions import YotoAuthError, YotoNetworkError
from yoto_web_server.api.models import DeviceAuthResponse, TokenData, TokenResponse


class YotoAuthClient:
    """
    Handles OAuth authentication and token management for Yoto API.

    Supports device code flow and automatic token refresh.
    """

    def __init__(
        self,
        config: YotoApiConfig,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.config = config
        self._client = http_client
        self._token_data: Optional[TokenData] = None
        self._token_lock = asyncio.Lock()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "YotoAuthClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        await self.close()

    def _decode_jwt(self, token: str) -> Optional[dict[str, Any]]:
        """Decode JWT token (without verification)."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Add padding if needed
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += "=" * padding

            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
            return None

    def _is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        decoded = self._decode_jwt(token)
        if not decoded or "exp" not in decoded:
            return True
        return decoded["exp"] < time.time() + 30

    async def initialize(self) -> None:
        """Initialize the auth client."""
        pass

    async def get_device_code(self) -> DeviceAuthResponse:
        """
        Request device authorization code.

        Returns device code and verification URLs for user authentication.
        """
        url = urljoin(self.config.auth_url, "/oauth/device/code")
        data = {
            "client_id": self.config.client_id,
            "scope": "profile offline_access",
            "audience": self.config.base_url,
        }

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            return DeviceAuthResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise YotoAuthError(f"Device code request failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise YotoNetworkError(f"Network error: {e}") from e

    async def poll_for_token(
        self,
        device_code: str,
        interval: int = 5,
        timeout: int = 300,
        callback: Optional[Callable[[str], None]] = None,
    ) -> TokenData:
        """
        Poll for token using device code.

        Args:
            device_code: Device code from get_device_code
            interval: Polling interval in seconds
            timeout: Maximum time to poll
            callback: Optional callback for status updates

        Returns:
            TokenData with access and refresh tokens

        Raises:
            YotoAuthError: If authentication fails or times out
        """
        url = urljoin(self.config.auth_url, "/oauth/token")
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": self.config.client_id,
        }

        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise YotoAuthError("Authentication timeout")

            try:
                response = await self.client.post(url, data=data)

                if response.status_code == 200:
                    token_response = TokenResponse.model_validate(response.json())
                    token_data = TokenData.from_token_response(token_response)
                    self._token_data = token_data
                    if callback:
                        callback("Authentication successful!")
                    return token_data

                elif response.status_code == 400:
                    error = response.json().get("error")
                    if error == "authorization_pending":
                        if callback:
                            callback("Waiting for user authorization...")
                    elif error == "slow_down":
                        interval = int(interval * 1.5)
                        if callback:
                            callback(f"Rate limited, slowing down to {interval}s")
                    elif error == "expired_token":
                        raise YotoAuthError("Device code expired")
                    elif error == "access_denied":
                        raise YotoAuthError("User denied authorization")
                    else:
                        raise YotoAuthError(f"Authorization error: {error}")
                else:
                    raise YotoAuthError(f"Unexpected status: {response.status_code}")

            except httpx.RequestError as e:
                logger.warning(f"Polling error: {e}")

            await asyncio.sleep(interval)

    async def refresh_access_token(self) -> TokenData:
        """
        Refresh access token using refresh token.

        Returns:
            New TokenData

        Raises:
            YotoAuthError: If refresh fails
        """
        if not self._token_data or not self._token_data.refresh_token:
            raise YotoAuthError("No refresh token available")

        url = urljoin(self.config.auth_url, "/oauth/token")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "refresh_token": self._token_data.refresh_token,
        }

        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()

            token_response = TokenResponse.model_validate(response.json())
            # Keep old refresh token if new one not provided
            if not token_response.refresh_token:
                token_response.refresh_token = self._token_data.refresh_token

            token_data = TokenData.from_token_response(token_response)
            self._token_data = token_data
            logger.info("Access token refreshed successfully")
            return token_data

        except httpx.HTTPStatusError as e:
            raise YotoAuthError(f"Token refresh failed: {e.response.text}") from e
        except httpx.RequestError as e:
            raise YotoNetworkError(f"Network error during refresh: {e}") from e

    async def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            YotoAuthError: If no token available and refresh fails
        """
        async with self._token_lock:
            if not self._token_data:
                raise YotoAuthError("Not authenticated. Call authenticate() first.")

            if self._token_data.is_expired():
                logger.info("Token expired, refreshing...")
                await self.refresh_access_token()

            return self._token_data.access_token

    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._token_data is not None and not self._token_data.is_expired()

    def clear_tokens(self) -> None:
        """Clear all stored tokens."""
        self._token_data = None
