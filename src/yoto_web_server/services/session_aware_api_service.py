"""
Session-Aware API Service - Manages Yoto API with session-based authentication.

Provides:
- Session-based token management (no disk persistence)
- Automatic token refresh using refresh tokens from cookies
- Session rehydration after server restart
"""

from __future__ import annotations

import time
from contextvars import ContextVar

import httpx
from loguru import logger

from yoto_web_server.api.client import YotoApiClient
from yoto_web_server.api.config import YotoApiConfig
from yoto_web_server.api.exceptions import YotoAuthError
from yoto_web_server.api.models import TokenData
from yoto_web_server.core.config import get_settings
from yoto_web_server.services.session_service import CookiePayload, SessionService

# Context variable for session ID (set by middleware)
_session_id_context: ContextVar[str | None] = ContextVar("session_id", default=None)


def get_session_id_context() -> ContextVar[str | None]:
    """Get the session ID context variable."""
    return _session_id_context


class SessionAwareApiService:
    """
    API Service that manages Yoto API authentication via sessions.

    Unlike disk-based token storage, this:
    - Does NOT use disk-based token storage
    - Stores access tokens in session memory only
    - Stores refresh tokens in encrypted cookies only
    - Can rehydrate sessions after restart
    """

    def __init__(self, session_service: SessionService) -> None:
        """
        Initialize session-aware API service.

        Args:
            session_service: Session service for managing sessions
        """
        self.session_service = session_service
        settings = get_settings()
        self._client_id = settings.yoto_client_id
        self._config = YotoApiConfig(
            client_id=self._client_id,
            base_url=settings.yoto_base_url,
            auth_url=settings.yoto_auth_url,
            timeout=settings.yoto_api_timeout,
        )
        self._api_clients: dict[str, YotoApiClient] = {}
        self._current_session_id: str | None = None

    def _get_session_id(self, session_id: str | None = None) -> str:
        """
        Get session ID from parameter, current instance, or context variable.

        Args:
            session_id: Explicit session ID (if provided)

        Returns:
            Session ID

        Raises:
            ValueError: If no session ID is available
        """
        if session_id:
            return session_id

        if self._current_session_id:
            return self._current_session_id

        ctx_session_id = _session_id_context.get()
        if ctx_session_id:
            return ctx_session_id

        raise ValueError("session_id is required for API calls")

    def set_current_session_id(self, session_id: str) -> None:
        """
        Set the current session ID for this service instance.

        Called by the dependency to bind the session for the request.

        Args:
            session_id: Session ID for this request
        """
        self._current_session_id = session_id

    async def get_or_create_api_client(
        self,
        session_id: str,
        access_token: str,
    ) -> YotoApiClient:
        """
        Get or create API client for a session.

        Args:
            session_id: Session ID
            access_token: Access token for the session

        Returns:
            YotoApiClient configured with the access token
        """
        if session_id in self._api_clients:
            client = self._api_clients[session_id]
            if client.auth._token_data:
                client.auth._token_data.access_token = access_token
            return client

        client = YotoApiClient(config=self._config)

        client.auth._token_data = TokenData(
            access_token=access_token,
            refresh_token=None,
            expires_at=time.time() + 600,
        )

        self._api_clients[session_id] = client
        logger.debug(f"Created API client for session: {session_id[:8]}...")

        return client

    async def get_client(self) -> YotoApiClient:
        """
        Get the YotoApiClient for the current session.

        Returns:
            YotoApiClient configured with the current session's access token.
        """
        session_id = self._get_session_id()
        session = self.session_service.get_session(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found in memory")

        return await self.get_or_create_api_client(session_id, session.access_token)

    def remove_api_client(self, session_id: str) -> None:
        """
        Remove API client for a session (on logout).

        Args:
            session_id: Session ID
        """
        if session_id in self._api_clients:
            del self._api_clients[session_id]
            logger.debug(f"Removed API client for session: {session_id[:8]}...")

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> tuple[str, float, str, float]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: OAuth refresh token

        Returns:
            tuple of (new_access_token, access_expiry, new_refresh_token, refresh_expiry)

        Raises:
            YotoAuthError: If refresh fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._config.auth_url}/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": self._client_id,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                    raise YotoAuthError(f"Token refresh failed: {response.status_code}")

                token_data = response.json()

                access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in", 600)

                if not access_token:
                    raise YotoAuthError("No access token in refresh response")

                current_time = time.time()
                access_expiry = current_time + expires_in
                refresh_expiry = current_time + (30 * 24 * 60 * 60)

                logger.info("Access token refreshed successfully")
                return access_token, access_expiry, new_refresh_token, refresh_expiry

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token refresh: {e}")
            raise YotoAuthError(f"Token refresh failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise YotoAuthError(f"Token refresh failed: {e}") from e

    async def rehydrate_session_from_cookie(
        self,
        cookie_payload: CookiePayload,
    ) -> tuple[str, CookiePayload]:
        """
        Rehydrate a session after server restart using cookie refresh token.

        Args:
            cookie_payload: Cookie payload with refresh token

        Returns:
            tuple of (session_id, new_cookie_payload)

        Raises:
            YotoAuthError: If refresh fails
        """
        logger.info(f"Rehydrating session from cookie: {cookie_payload.session_id[:8]}...")

        (
            access_token,
            access_expiry,
            new_refresh_token,
            refresh_expiry,
        ) = await self.refresh_access_token(cookie_payload.refresh_token)

        self.session_service.rehydrate_session(
            session_id=cookie_payload.session_id,
            access_token=access_token,
            access_token_expiry=access_expiry,
            created_at=cookie_payload.created_at,
        )

        new_cookie_payload = CookiePayload(
            session_id=cookie_payload.session_id,
            refresh_token=new_refresh_token,
            refresh_token_expiry=refresh_expiry,
            created_at=cookie_payload.created_at,
        )

        return cookie_payload.session_id, new_cookie_payload

    async def refresh_session_access_token(
        self,
        session_id: str,
        cookie_payload: CookiePayload,
    ) -> CookiePayload:
        """
        Refresh the access token for an existing session.

        Args:
            session_id: Session ID
            cookie_payload: Current cookie payload with refresh token

        Returns:
            New cookie payload with rotated refresh token
        """
        (
            access_token,
            access_expiry,
            new_refresh_token,
            refresh_expiry,
        ) = await self.refresh_access_token(cookie_payload.refresh_token)

        self.session_service.update_access_token(
            session_id=session_id,
            access_token=access_token,
            access_token_expiry=access_expiry,
        )

        if session_id in self._api_clients:
            client = self._api_clients[session_id]
            if client.auth._token_data:
                client.auth._token_data.access_token = access_token
                client.auth._token_data.expires_at = access_expiry

        new_cookie_payload = CookiePayload(
            session_id=session_id,
            refresh_token=new_refresh_token,
            refresh_token_expiry=refresh_expiry,
            created_at=cookie_payload.created_at,
        )

        return new_cookie_payload

    async def create_session_from_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int = 600,  # Default 10 minutes
    ) -> tuple[str, CookiePayload]:
        """
        Create a new session from OAuth tokens.

        Called after successful OAuth flow completion.

        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Access token TTL in seconds

        Returns:
            tuple of (session_id, cookie_payload)
        """
        current_time = time.time()
        access_expiry = current_time + expires_in
        # Refresh token valid for 30 days
        refresh_expiry = current_time + (30 * 24 * 60 * 60)

        session_id, cookie_payload = self.session_service.create_session(
            access_token=access_token,
            access_token_expiry=access_expiry,
            refresh_token=refresh_token,
            refresh_token_expiry=refresh_expiry,
        )

        logger.info(f"Created session from OAuth tokens: {session_id[:8]}...")
        return session_id, cookie_payload

    async def logout_session(self, session_id: str) -> None:
        """
        Logout a session - removes from memory.

        Args:
            session_id: Session ID to logout
        """
        self.remove_api_client(session_id)
        self.session_service.delete_session(session_id)
        logger.info(f"Logged out session: {session_id[:8]}...")

    def is_session_authenticated(self, session_id: str | None) -> bool:
        """
        Check if a session is authenticated.

        Args:
            session_id: Session ID to check

        Returns:
            True if session exists and has valid access token
        """
        if not session_id:
            return False

        session = self.session_service.get_session(session_id)
        if not session:
            return False

        # Check if access token expired
        return not session.is_access_token_expired()

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        return await self.session_service.cleanup_expired_sessions()
