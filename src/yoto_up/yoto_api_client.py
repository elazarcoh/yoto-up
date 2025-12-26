"""
Production-ready Yoto API Client

This module provides a clean, maintainable API client for the Yoto API
with proper separation of concerns, error handling, and type safety.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Optional
from urllib.parse import urljoin

import httpx
from loguru import logger
from pydantic import BaseModel, Field, field_validator, ConfigDict

from yoto_up.models import (
    Card,
    Device,
    DeviceConfig,
    DeviceStatus,
    Track,
    Chapter,
    TrackDisplay,
    ChapterDisplay,
)
from yoto_up_server.models import DisplayIconManifest


# ============================================================================
# Configuration & Constants
# ============================================================================


class YotoApiConfig(BaseModel):
    """Configuration for Yoto API client"""

    client_id: str
    base_url: str = "https://api.yotoplay.com"
    auth_url: str = "https://login.yotoplay.com"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    model_config = {"frozen": True}


# ============================================================================
# Exception Hierarchy
# ============================================================================


class YotoApiError(Exception):
    """Base exception for all Yoto API errors"""

    pass


class YotoAuthError(YotoApiError):
    """Authentication/authorization errors"""

    pass


class YotoRateLimitError(YotoApiError):
    """Rate limiting errors"""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class YotoValidationError(YotoApiError):
    """Request validation errors"""

    pass


class YotoNotFoundError(YotoApiError):
    """Resource not found"""

    pass


class YotoServerError(YotoApiError):
    """Server-side errors"""

    pass


class YotoNetworkError(YotoApiError):
    """Network connectivity errors"""

    pass


class YotoTimeoutError(YotoApiError):
    """Request timeout errors"""

    pass


# ============================================================================
# Request/Response Models
# ============================================================================


class DeviceAuthResponse(BaseModel):
    """Response from device authorization flow"""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int = 5


class TokenResponse(BaseModel):
    """OAuth token response"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class AudioUploadUrlResponse(BaseModel):
    """Response from audio upload URL request"""

    class Upload(BaseModel):
        upload_url: Optional[str] = Field(None, alias="uploadUrl")
        upload_id: str = Field(..., alias="uploadId")

    upload: Upload


class TranscodedAudioResponse(BaseModel):
    """Response from transcoded audio endpoint"""

    class Transcode(BaseModel):
        class Progress(BaseModel):
            phase: str
            percent: float
            updated_at: datetime = Field(..., alias="updatedAt")

            model_config = ConfigDict(extra="ignore")

        class TranscodeInfo(BaseModel):
            duration: float
            codec: str
            format: str
            sample_rate: int = Field(..., alias="sampleRate")
            channels: str
            bitrate: int
            metadata: dict[str, Any]
            input_format: str = Field(..., alias="inputFormat")
            file_size: Optional[int] = Field(None, alias="fileSize")

            model_config = ConfigDict(extra="ignore")

        model_config = ConfigDict(extra="ignore")

        upload_id: str = Field(..., alias="uploadId")
        upload_filename: str = Field(..., alias="uploadFilename")
        upload_sha256: str = Field(..., alias="uploadSha256")
        created_at: datetime = Field(..., alias="createdAt")
        options: dict[str, Any]
        started_at: Optional[datetime] = Field(None, alias="startedAt")
        progress: Progress | None = None
        ffmpeg: Optional[dict[str, Any]] = None
        transcoded_at: Optional[datetime] = Field(None, alias="transcodedAt")
        transcoded_info: Optional[TranscodeInfo] = Field(None, alias="transcodedInfo")
        transcoded_sha256: Optional[str] = Field(None, alias="transcodedSha256")
        upload_info: Optional[TranscodeInfo] = Field(None, alias="uploadInfo")

    transcode: Transcode


class CoverImageUploadResponse(BaseModel):
    """Response from cover image upload"""

    cover_image: str = Field(..., alias="coverImage")
    cover_type: Optional[str] = Field(None, alias="coverType")


class IconUploadResponse(BaseModel):
    """Response from icon upload"""

    icon_id: str = Field(..., alias="iconId")
    url: str


class CoverType(str, Enum):
    """Cover image types"""

    SQUARE = "square"
    RECTANGLE = "rectangle"


# ============================================================================
# Token Storage
# ============================================================================


@dataclass
class TokenData:
    """Token data with expiration tracking"""

    access_token: str
    refresh_token: Optional[str]
    expires_at: float

    def is_expired(self, buffer_seconds: float = 30.0) -> bool:
        """Check if token is expired (with buffer)"""
        return time.time() >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenData:
        """Create from dictionary"""
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=data["expires_at"],
        )

    @classmethod
    def from_token_response(cls, response: TokenResponse) -> TokenData:
        """Create from token response"""
        expires_at = time.time() + response.expires_in
        return cls(
            access_token=response.access_token,
            refresh_token=response.refresh_token,
            expires_at=expires_at,
        )


class TokenStorage:
    """Manages token persistence"""

    def __init__(self, token_file: Path):
        self.token_file = token_file

    def save(self, token_data: TokenData) -> None:
        """Save tokens to file"""
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with self.token_file.open("w") as f:
                json.dump(token_data.to_dict(), f, indent=2)
            logger.debug(f"Saved tokens to {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise YotoApiError(f"Token save failed: {e}") from e

    def load(self) -> Optional[TokenData]:
        """Load tokens from file"""
        if not self.token_file.exists():
            return None

        try:
            with self.token_file.open("r") as f:
                data = json.load(f)
            return TokenData.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load tokens: {e}")
            return None

    def clear(self) -> None:
        """Clear stored tokens"""
        if self.token_file.exists():
            self.token_file.unlink()
            logger.debug("Cleared stored tokens")


# ============================================================================
# Authentication Client
# ============================================================================


class YotoAuthClient:
    """
    Handles OAuth authentication and token management for Yoto API.

    Supports device code flow and automatic token refresh.
    """

    def __init__(
        self,
        config: YotoApiConfig,
        token_storage: TokenStorage,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.config = config
        self.token_storage = token_storage
        self._client = http_client
        self._token_data: Optional[TokenData] = None
        self._token_lock = asyncio.Lock()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _decode_jwt(self, token: str) -> Optional[dict[str, Any]]:
        """Decode JWT token (without verification)"""
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
        """Check if token is expired"""
        decoded = self._decode_jwt(token)
        if not decoded or "exp" not in decoded:
            return True
        return decoded["exp"] < time.time() + 30

    async def initialize(self) -> None:
        """Initialize authentication (load existing tokens)"""
        self._token_data = self.token_storage.load()
        if self._token_data and self._token_data.is_expired():
            logger.info("Stored token expired, will need refresh")

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
                    self.token_storage.save(token_data)
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
            self.token_storage.save(token_data)
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
        """Check if client is authenticated"""
        return self._token_data is not None and not self._token_data.is_expired()

    def clear_tokens(self) -> None:
        """Clear all stored tokens"""
        self._token_data = None
        self.token_storage.clear()


# ============================================================================
# Main API Client
# ============================================================================


class YotoApiClient:
    """
    Production-ready Yoto API client.

    Provides clean interface to all Yoto API endpoints with:
    - Automatic authentication and token refresh
    - Comprehensive error handling
    - Request retry logic
    - Type-safe requests and responses

    Example:
        ```python
        from pathlib import Path
        from yoto_up.yoto_api_client import YotoApiClient, YotoApiConfig

        config = YotoApiConfig(client_id="your_client_id")

        async with YotoApiClient(config, token_file=Path("tokens.json")) as client:
            # Authenticate if needed
            if not client.is_authenticated():
                await client.authenticate()

            # Get user's content
            cards = await client.get_my_content()

            # Create new card
            card = await client.create_card(title="My Playlist")
        ```
    """

    def __init__(
        self,
        config: YotoApiConfig,
        token_file: Path,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize Yoto API client.

        Args:
            config: API configuration
            token_file: Path to token storage file
            http_client: Optional pre-configured HTTP client
        """
        self.config = config
        self._http_client = http_client

        # Initialize authentication
        token_storage = TokenStorage(token_file)
        self.auth = YotoAuthClient(config, token_storage, http_client)

        # Request tracking
        self._request_count = 0

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self._http_client

    async def initialize(self) -> None:
        """Initialize the client"""
        await self.auth.initialize()

    async def close(self) -> None:
        """Close all connections"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self.auth.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Convert HTTP errors to specific exceptions"""
        status = error.response.status_code
        text = error.response.text

        if status == 401:
            raise YotoAuthError(f"Unauthorized: {text}") from error
        elif status == 403:
            raise YotoAuthError(f"Forbidden: {text}") from error
        elif status == 404:
            raise YotoNotFoundError(f"Not found: {text}") from error
        elif status == 422:
            raise YotoValidationError(f"Validation error: {text}") from error
        elif status == 429:
            retry_after = error.response.headers.get("Retry-After")
            raise YotoRateLimitError(
                f"Rate limited: {text}",
                retry_after=float(retry_after) if retry_after else None,
            ) from error
        elif 500 <= status < 600:
            raise YotoServerError(f"Server error {status}: {text}") from error
        else:
            raise YotoApiError(f"HTTP {status}: {text}") from error

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        require_auth: bool = True,
        retry_count: int = 0,
    ) -> httpx.Response:
        """
        Make authenticated API request with retry logic.

        Args:
            method: HTTP method
            path: API path (relative to base_url)
            params: Query parameters
            json: JSON body
            data: Form data
            files: File uploads
            headers: Additional headers
            require_auth: Whether authentication is required
            retry_count: Current retry attempt

        Returns:
            HTTP response

        Raises:
            Various YotoApiError subclasses
        """
        url = urljoin(self.config.base_url, path)

        # Build headers
        request_headers = headers or {}
        if require_auth:
            token = await self.auth.get_valid_token()
            request_headers["Authorization"] = f"Bearer {token}"

        # Add JSON content type if needed
        if json is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"

        self._request_count += 1

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=request_headers,
            )
            response.raise_for_status()
            return response

        except httpx.TimeoutException as e:
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (
                    self.config.retry_backoff**retry_count
                )
                logger.warning(f"Request timeout, retrying in {delay}s...")
                await asyncio.sleep(delay)
                return await self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=headers,
                    require_auth=require_auth,
                    retry_count=retry_count + 1,
                )
            raise YotoTimeoutError(
                f"Request timeout after {retry_count + 1} attempts"
            ) from e

        except httpx.HTTPStatusError as e:
            # Handle 401 by refreshing token and retrying once
            if e.response.status_code == 401 and require_auth and retry_count == 0:
                logger.info("Got 401, refreshing token and retrying...")
                try:
                    await self.auth.refresh_access_token()
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json=json,
                        data=data,
                        files=files,
                        headers=headers,
                        require_auth=require_auth,
                        retry_count=retry_count + 1,
                    )
                except YotoAuthError:
                    pass  # Fall through to raise original error

            # Handle rate limiting
            if e.response.status_code == 429:
                rate_error = YotoRateLimitError("Rate limited", None)
                retry_after = e.response.headers.get("Retry-After")
                if retry_after and retry_count < self.config.max_retries:
                    delay = float(retry_after)
                    logger.warning(f"Rate limited, waiting {delay}s...")
                    await asyncio.sleep(delay)
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json=json,
                        data=data,
                        files=files,
                        headers=headers,
                        require_auth=require_auth,
                        retry_count=retry_count + 1,
                    )
                raise rate_error from e

            # Convert to specific exception
            self._handle_http_error(e)

        except httpx.RequestError as e:
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (
                    self.config.retry_backoff**retry_count
                )
                logger.warning(f"Network error, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
                return await self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=headers,
                    require_auth=require_auth,
                    retry_count=retry_count + 1,
                )
            raise YotoNetworkError(
                f"Network error after {retry_count + 1} attempts: {e}"
            ) from e

        raise YotoApiError("Unhandled request error")

    # ========================================================================
    # Authentication Methods
    # ========================================================================

    async def authenticate(
        self,
        callback: Optional[Callable[[str, str], None]] = None,
        timeout: int = 300,
    ) -> None:
        """
        Perform device code authentication flow.

        Args:
            callback: Optional callback(verification_url, user_code) for custom UI
            timeout: Maximum time to wait for authentication

        Raises:
            YotoAuthError: If authentication fails
        """
        # Request device code
        device_auth = await self.auth.get_device_code()

        # Notify user
        if callback:
            callback(device_auth.verification_uri_complete, device_auth.user_code)
        else:
            logger.info(f"Visit: {device_auth.verification_uri_complete}")
            logger.info(
                f"Or go to {device_auth.verification_uri} and enter: {device_auth.user_code}"
            )

        # Poll for token
        await self.auth.poll_for_token(
            device_code=device_auth.device_code,
            interval=device_auth.interval,
            timeout=timeout,
        )

    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self.auth.is_authenticated()

    def reset_authentication(self) -> None:
        """Clear all authentication tokens"""
        self.auth.clear_tokens()

    # ========================================================================
    # Content Management
    # ========================================================================

    async def get_my_content(self) -> list[Card]:
        """
        Get all user's MYO (Make Your Own) content.

        Returns:
            List of Card objects
        """
        response = await self._request("GET", "/content/mine")
        data = response.json()

        # Handle both {"cards": [...]} and direct list responses
        cards_data = data.get("cards", data) if isinstance(data, dict) else data
        return [Card.model_validate(card) for card in cards_data]

    async def get_card(self, card_id: str) -> Card:
        """
        Get specific card by ID.

        Args:
            card_id: Card ID

        Returns:
            Card object
        """
        response = await self._request("GET", f"/content/{card_id}")
        data = response.json()
        card_data = data.get("card", data)
        return Card.model_validate(card_data)

    async def _create_or_update_card(self, card: Card) -> Card:
        # Use exclude_none=True to avoid sending null values for optional fields
        # The API doesn't accept null values for optional fields like content.activity
        payload = card.model_dump(exclude_none=True)
        response = await self._request("POST", "/content", json=payload)
        data = response.json()
        card_data = data.get("card", data)
        return Card.model_validate(card_data)

    async def create_card(self, card: Card) -> Card:
        """
        Create a new card.
        Args:
            card: Card object to create
        Returns:
            Created Card object
        return await self._create_or_update_card(card)
        """
        if card.cardId:
            raise YotoValidationError("Card ID should not be set for creation")
        return await self._create_or_update_card(card)

    async def update_card(self, card: Card) -> Card:
        """
        Update existing card.

        Args:
            card: Card object with updates

        Returns:
            Updated Card object
        """
        if not card.cardId:
            raise YotoValidationError("Card ID is required for update")
        return await self._create_or_update_card(card)

    async def delete_card(self, card_id: str) -> None:
        """
        Delete a card.

        Args:
            card_id: Card ID to delete
        """
        await self._request("DELETE", f"/content/{card_id}")

    # ========================================================================
    # Media Upload
    # ========================================================================

    def calculate_sha256(self, file_path: Path) -> tuple[str, bytes]:
        """
        Calculate SHA-256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (hex_hash, file_bytes)
        """
        hasher = hashlib.sha256()
        with file_path.open("rb") as f:
            file_bytes = f.read()
            hasher.update(file_bytes)
        return hasher.hexdigest(), file_bytes

    async def get_audio_upload_url(
        self,
        sha256: str,
        filename: Optional[str] = None,
    ) -> AudioUploadUrlResponse:
        """
        Get signed upload URL for audio file.

        If file already exists, uploadUrl will be None.

        Args:
            sha256: SHA-256 hash of file
            filename: Optional filename

        Returns:
            Upload URL response
        """
        params = {"sha256": sha256}
        if filename:
            params["filename"] = filename

        response = await self._request(
            "GET", "/media/transcode/audio/uploadUrl", params=params
        )
        return AudioUploadUrlResponse.model_validate(response.json())

    async def upload_audio_file(
        self,
        upload_url: str,
        audio_bytes: bytes,
        mime_type: str = "audio/mpeg",
    ) -> None:
        """
        Upload audio file to signed URL.

        Args:
            upload_url: Signed upload URL
            audio_bytes: Audio file bytes
            mime_type: MIME type
        """
        headers = {"Content-Type": mime_type}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.put(
                upload_url,
                content=audio_bytes,
                headers=headers,
            )
            response.raise_for_status()

    async def poll_for_transcoding(
        self,
        upload_id: str,
        loudnorm: bool = False,
        poll_interval: float = 2.0,
        max_attempts: int = 120,
        callback: Optional[Callable[[int, int], None]] = None,
    ) -> TranscodedAudioResponse:
        """
        Poll for audio transcoding completion.

        Args:
            upload_id: Upload ID from upload URL response
            loudnorm: Whether loudness normalization was requested
            poll_interval: Seconds between polls
            max_attempts: Maximum polling attempts
            callback: Optional progress callback(attempt, max_attempts)

        Returns:
            Transcoded audio response

        Raises:
            YotoApiError: If transcoding fails or times out
        """
        url = f"/media/upload/{upload_id}/transcoded"
        params = {"loudnorm": "true" if loudnorm else "false"}

        for attempt in range(max_attempts):
            if callback:
                callback(attempt + 1, max_attempts)

            try:
                response = await self._request("GET", url, params=params)
                return TranscodedAudioResponse.model_validate(response.json())
            except YotoNotFoundError:
                # Not ready yet
                if attempt < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                else:
                    raise YotoApiError(
                        f"Transcoding timeout after {max_attempts} attempts"
                    )

        raise YotoApiError("Transcoding failed")

    async def upload_cover_image(
        self,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
        image_data: Optional[bytes] = None,
        autoconvert: bool = True,
        cover_type: Optional[CoverType] = None,
    ) -> CoverImageUploadResponse:
        """
        Upload cover image.

        Args:
            image_path: Local image file path
            image_url: Remote image URL
            autoconvert: Whether to auto-convert image format
            cover_type: Cover type (square/rectangle)

        Returns:
            Cover image upload response
        """
        if not image_path and not image_url:
            raise YotoValidationError("Either image_path or image_url required")

        data = {}
        if autoconvert:
            data["autoconvert"] = "true"
        if cover_type:
            data["coverType"] = cover_type.value
        if image_url:
            data["imageUrl"] = image_url

        files = None
        if image_path:
            files = {"image": (image_path.name, image_path.open("rb"), "image/jpeg")}
        elif image_data:
            files = {"image": ("cover.jpg", image_data, "image/jpeg")}

        try:
            response = await self._request(
                "POST",
                "/media/image/cover",
                data=data,
                files=files,
            )
            return CoverImageUploadResponse.model_validate(response.json())
        finally:
            if files:
                files["image"][1].close()

    # ========================================================================
    # Device Management
    # ========================================================================

    async def get_devices(self) -> list[Device]:
        """
        Get all devices.

        Returns:
            List of Device objects
        """
        response = await self._request("GET", "/devices")
        data = response.json()
        devices_data = data.get("devices", data) if isinstance(data, dict) else data
        return [Device.model_validate(device) for device in devices_data]

    async def get_device_status(self, device_id: str) -> DeviceStatus:
        """
        Get device status.

        Args:
            device_id: Device ID

        Returns:
            DeviceStatus object
        """
        response = await self._request("GET", f"/devices/{device_id}/status")
        return DeviceStatus.model_validate(response.json())

    async def get_device_config(self, device_id: str) -> DeviceConfig:
        """
        Get device configuration.

        Args:
            device_id: Device ID

        Returns:
            DeviceConfig object
        """
        response = await self._request("GET", f"/devices/{device_id}/config")
        return DeviceConfig.model_validate(response.json())

    async def update_device_config(
        self,
        device_id: str,
        name: str,
        config: DeviceConfig,
    ) -> DeviceConfig:
        """
        Update device configuration.

        Args:
            device_id: Device ID
            name: Device name
            config: DeviceConfig object with updates

        Returns:
            Updated DeviceConfig
        """
        payload = {"name": name, **config.model_dump(exclude_none=True)}
        response = await self._request(
            "PUT", f"/devices/{device_id}/config", json=payload
        )
        return DeviceConfig.model_validate(response.json())

    # ========================================================================
    # Helpers
    # ========================================================================

    def get_track_from_transcoded_audio(
        self,
        response: TranscodedAudioResponse,
        track_details: Optional[dict] = None,
    ) -> Track:
        """
        Create a Track object from transcoded audio response.

        Args:
            response: TranscodedAudioResponse from upload
            track_details: Optional overrides for track properties

        Returns:
            Track object
        """
        info = response.transcoded_info
        title = "Unknown Track"
        if info and info.metadata and info.metadata.title:
            title = info.metadata.title

        track_kwargs = {
            "key": "01",
            "title": title,
            "trackUrl": f"yoto:#{response.transcoded_sha256}",
            "duration": info.duration if info else None,
            "fileSize": info.file_size if info else None,
            "channels": info.channels if info else None,
            "format": info.format if info else None,
            "type": "audio",
            "overlayLabel": "1",
            "display": TrackDisplay(
                icon16x16="yoto:#aUm9i3ex3qqAMYBv-i-O-pYMKuMJGICtR3Vhf289u2Q"
            ),
        }

        if track_details:
            track_kwargs.update(track_details)

        return Track(**track_kwargs)

    def get_chapter_from_transcoded_audio(
        self,
        response: TranscodedAudioResponse,
        chapter_details: Optional[dict] = None,
    ) -> Chapter:
        """
        Create a Chapter object from transcoded audio response.

        Args:
            response: TranscodedAudioResponse from upload
            chapter_details: Optional overrides for chapter properties

        Returns:
            Chapter object
        """
        track = self.get_track_from_transcoded_audio(response)

        title = track.title
        if chapter_details and "title" in chapter_details:
            title = chapter_details["title"]

        chapter_kwargs = {
            "key": "01",
            "title": title,
            "overlayLabel": "1",
            "tracks": [track],
            "display": ChapterDisplay(
                icon16x16="yoto:#aUm9i3ex3qqAMYBv-i-O-pYMKuMJGICtR3Vhf289u2Q"
            ),
        }

        if chapter_details:
            chapter_kwargs.update(chapter_details)

        return Chapter(**chapter_kwargs)

    async def get_public_icons(self):
        """
        Get public icons from the API.
        """
        response = await self._request("GET", "/media/displayIcons/user/yoto")
        return DisplayIconManifest.model_validate(response.json())

    async def get_user_icons(self):
        """
        Get user-uploaded icons from the API.
        """
        response = await self._request("GET", "/media/displayIcons/user/me")
        return DisplayIconManifest.model_validate(response.json())
