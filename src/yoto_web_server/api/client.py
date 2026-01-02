"""
Yoto API Client.

Production-ready async client for the Yoto API with:
- Automatic authentication and token refresh
- Comprehensive error handling
- Request retry logic
- Type-safe requests and responses
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from loguru import logger

from yoto_web_server.api.auth import YotoAuthClient
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
    AudioUploadUrlResponse,
    Card,
    CoverImageUploadResponse,
    CoverType,
    Device,
    DeviceConfig,
    DeviceConfigUpdate,
    DeviceStatus,
    DisplayIconManifest,
    IconUploadResponse,
    NewCardRequest,
    TranscodedAudioResponse,
)


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
        from yoto_web_server.api import YotoApiClient, YotoApiConfig

        config = YotoApiConfig(client_id="your_client_id")

        async with YotoApiClient(config) as client:
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
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize Yoto API client.

        Args:
            config: API configuration
            http_client: Optional pre-configured HTTP client
        """
        self.config = config
        self._http_client = http_client

        # Initialize authentication
        self.auth = YotoAuthClient(config, http_client)

        # Request tracking
        self._request_count = 0

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self._http_client

    async def initialize(self) -> None:
        """Initialize the client."""
        await self.auth.initialize()

    async def close(self) -> None:
        """Close all connections."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self.auth.close()

    async def __aenter__(self) -> YotoApiClient:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        await self.close()

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """Convert HTTP errors to specific exceptions."""
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
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        content: bytes | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
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
            content: Raw bytes to send as request body
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
                content=content,
                files=files,
                headers=request_headers,
            )
            response.raise_for_status()
            return response

        except httpx.TimeoutException as e:
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (self.config.retry_backoff**retry_count)
                logger.warning(f"Request timeout, retrying in {delay}s...")
                await asyncio.sleep(delay)
                return await self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    data=data,
                    content=content,
                    files=files,
                    headers=headers,
                    require_auth=require_auth,
                    retry_count=retry_count + 1,
                )
            raise YotoTimeoutError(f"Request timeout after {retry_count + 1} attempts") from e

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
                except YotoAuthError as auth_error:
                    raise auth_error  # Re-raise to trigger login redirect

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
                delay = self.config.retry_delay * (self.config.retry_backoff**retry_count)
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
            raise YotoNetworkError(f"Network error after {retry_count + 1} attempts: {e}") from e

        raise YotoApiError("Unhandled request error")

    # ========================================================================
    # Authentication Methods
    # ========================================================================

    async def authenticate(
        self,
        callback: Callable[[str, str], None] | None = None,
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
        """Check if client is authenticated."""
        return self.auth.is_authenticated()

    def reset_authentication(self) -> None:
        """Clear all authentication tokens."""
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

    async def _create_or_update_card(self, card: NewCardRequest | Card) -> Card:
        """Create or update a card."""
        # Use exclude_none=True to avoid sending null values
        payload = card.model_dump(exclude_none=True)
        response = await self._request("POST", "/content", json=payload)
        data = response.json()
        card_data = data.get("card", data)
        return Card.model_validate(card_data)

    async def create_card(self, card: NewCardRequest) -> Card:
        """
        Create a new card.

        Args:
            card: Card object to create

        Returns:
            Created Card object
        """
        if card.card_id:
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
        if not card.card_id:
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
        filename: str | None = None,
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
        params: dict[str, str] = {"sha256": sha256}
        if filename:
            params["filename"] = filename

        response = await self._request("GET", "/media/transcode/audio/uploadUrl", params=params)
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
        callback: Callable[[int, int], None] | None = None,
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
                result = TranscodedAudioResponse.model_validate(response.json())

                # Check if transcoding is complete by looking for transcoded_sha256
                if result.transcode.transcoded_sha256:
                    return result

                # Transcoding still in progress, wait and retry
                if attempt < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                else:
                    raise YotoApiError(
                        f"Transcoding timeout after {max_attempts} attempts"
                    ) from None
            except YotoNotFoundError:
                # Not ready yet
                if attempt < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                else:
                    raise YotoApiError(
                        f"Transcoding timeout after {max_attempts} attempts"
                    ) from None

        raise YotoApiError("Transcoding failed")

    async def upload_cover_image(
        self,
        image_path: Path | None = None,
        image_url: str | None = None,
        image_data: bytes | None = None,
        autoconvert: bool = True,
        cover_type: CoverType | None = None,
    ) -> CoverImageUploadResponse:
        """
        Upload cover image.

        Args:
            image_path: Local image file path
            image_url: Remote image URL
            image_data: Raw image bytes
            autoconvert: Whether to auto-convert image format
            cover_type: Cover type (square/rectangle)

        Returns:
            Cover image upload response
        """
        if not image_path and not image_url and not image_data:
            raise YotoValidationError("Either image_path, image_url, or image_data required")

        params: dict[str, str] = {}
        if autoconvert:
            params["autoconvert"] = "true"
        if cover_type:
            params["coverType"] = cover_type.value
        if image_url:
            params["imageUrl"] = image_url

        content = None
        headers = {}

        if image_path:
            content = image_path.read_bytes()
            headers["Content-Type"] = "image/jpeg"  # Assuming JPEG as per docs
        elif image_data:
            content = image_data
            headers["Content-Type"] = "image/jpeg"

        # If image_url is provided, we don't send body content, just the param
        if image_url:
            content = None
            headers = {}

        response = await self._request(
            "POST",
            "/media/coverImage/user/me/upload",
            params=params,
            content=content,
            headers=headers,
        )
        return CoverImageUploadResponse.model_validate(response.json())

    async def upload_icon(
        self,
        icon_bytes: bytes,
        filename: str = "icon.png",
        auto_convert: bool = True,
    ) -> IconUploadResponse:
        """
        Upload a custom icon.

        Args:
            icon_bytes: The icon image data
            filename: Filename for the upload
            auto_convert: Whether to auto-convert the image

        Returns:
            IconUploadResponse with the new icon ID
        """
        params = {
            "autoConvert": str(auto_convert).lower(),
            "filename": filename,
        }

        # Detect MIME type from filename extension
        ext = Path(filename).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".gif": "image/gif",
        }
        mime_type = mime_types.get(ext, "application/octet-stream")

        headers = {"Content-Type": mime_type}

        response = await self._request(
            "POST",
            "/media/displayIcons/user/me/upload",
            params=params,
            content=icon_bytes,
            headers=headers,
        )

        data = response.json()
        if "displayIcon" in data:
            data = data["displayIcon"]

        return IconUploadResponse.model_validate(data)

    # ========================================================================
    # Device Management
    # ========================================================================

    async def get_devices(self) -> list[Device]:
        """
        Get all devices.

        Returns:
            List of Device objects
        """
        response = await self._request("GET", "/device-v2/devices/mine")
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
        response = await self._request("GET", f"/device-v2/{device_id}/status")
        return DeviceStatus.model_validate(response.json())

    async def get_device_config(self, device_id: str) -> DeviceConfig:
        """
        Get device configuration.

        Args:
            device_id: Device ID

        Returns:
            DeviceConfig object
        """
        response = await self._request("GET", f"/device-v2/{device_id}/config")
        return DeviceConfig.model_validate(response.json())

    async def update_device_config(
        self,
        device_id: str,
        config: DeviceConfigUpdate,
    ) -> None:
        response = await self._request(
            "PUT",
            f"/device-v2/{device_id}/config",
            json=config.model_dump(exclude_none=True),
        )
        response.raise_for_status()

    # ========================================================================
    # Icons
    # ========================================================================

    async def get_public_icons(self) -> DisplayIconManifest:
        """Get public icons from the API."""
        response = await self._request("GET", "/media/displayIcons/user/yoto")
        return DisplayIconManifest.model_validate(response.json())

    async def get_user_icons(self) -> DisplayIconManifest:
        """Get user-uploaded icons from the API."""
        response = await self._request("GET", "/media/displayIcons/user/me")
        return DisplayIconManifest.model_validate(response.json())
