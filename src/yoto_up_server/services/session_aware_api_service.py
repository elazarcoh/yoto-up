"""
Session-Aware API Service - Manages Yoto API with session-based authentication.

This service integrates with SessionService to provide:
- Session-based token management (no disk persistence)
- Automatic token refresh using refresh tokens from cookies
- Session rehydration after server restart
"""

import time
from typing import Optional

import httpx
from loguru import logger

from yoto_up.yoto_api_client import YotoApiClient, YotoApiConfig, YotoAuthError
from yoto_up.yoto_app import config as yoto_config
from yoto_up_server.services.session_service import SessionService, CookiePayload
from yoto_up_server.middleware.session_middleware import _session_id_context


class SessionAwareApiService:
    """
    API Service that manages Yoto API authentication via sessions.

    Unlike the original ApiService, this:
    - Does NOT use disk-based token storage
    - Stores access tokens in session memory only
    - Stores refresh tokens in encrypted cookies only
    - Can rehydrate sessions after restart
    """

    def __init__(self, session_service: SessionService):
        """
        Initialize session-aware API service.

        Args:
            session_service: Session service for managing sessions
        """
        self.session_service = session_service
        self._client_id: str = yoto_config.CLIENT_ID
        self._config = YotoApiConfig(client_id=self._client_id)
        # Per-session API clients (keyed by session_id)
        self._api_clients: dict[str, YotoApiClient] = {}
        # Current session ID for this request (set by dependency)
        self._current_session_id: str = None

    def _get_session_id(self, session_id: str = None) -> str:
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
        
        # Try current session ID from dependency
        if self._current_session_id:
            return self._current_session_id
        
        # Try to get from context variable
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
        # Check if we already have a client for this session
        if session_id in self._api_clients:
            client = self._api_clients[session_id]
            # Update access token via auth client if token data exists
            if client.auth._token_data:
                client.auth._token_data.access_token = access_token
            return client

        # Create new API client for this session
        # Use a dummy token file (we won't actually use it)
        from pathlib import Path
        import tempfile
        
        temp_token_file = Path(tempfile.gettempdir()) / f"session_{session_id[:8]}.json"
        
        client = YotoApiClient(config=self._config, token_file=temp_token_file)
        
        # Manually set token data via auth client
        from yoto_up.yoto_api_client import TokenData
        import time
        
        client.auth._token_data = TokenData(
            access_token=access_token,
            refresh_token=None,  # Refresh tokens handled by session service
            expires_at=time.time() + 600,  # 10 minutes
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
            # Clean up temp token file if it exists
            from pathlib import Path
            import tempfile
            
            temp_token_file = Path(tempfile.gettempdir()) / f"session_{session_id[:8]}.json"
            try:
                if temp_token_file.exists():
                    temp_token_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp token file: {e}")
            
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
                    "https://login.yotoplay.com/oauth/token",
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

                # Extract tokens
                access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in", 600)  # Default 10 minutes

                if not access_token:
                    raise YotoAuthError("No access token in refresh response")

                # Calculate expiry times
                current_time = time.time()
                access_expiry = current_time + expires_in
                # Refresh token typically valid for 30 days
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

        # Refresh access token using cookie refresh token
        access_token, access_expiry, new_refresh_token, refresh_expiry = (
            await self.refresh_access_token(cookie_payload.refresh_token)
        )

        # Rehydrate in-memory session
        self.session_service.rehydrate_session(
            session_id=cookie_payload.session_id,
            access_token=access_token,
            access_token_expiry=access_expiry,
            created_at=cookie_payload.created_at,
        )

        # Create new cookie payload with rotated refresh token
        new_cookie_payload = CookiePayload(
            session_id=cookie_payload.session_id,
            refresh_token=new_refresh_token,
            refresh_token_expiry=refresh_expiry,
            created_at=cookie_payload.created_at,
        )

        return cookie_payload.session_id, new_cookie_payload

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

    async def refresh_session_access_token(
        self,
        session_id: str,
        refresh_token: str,
    ) -> CookiePayload:
        """
        Refresh access token for an existing session.

        Updates the in-memory session with new access token.
        Returns new cookie payload with rotated refresh token.

        Args:
            session_id: Session ID
            refresh_token: Current refresh token

        Returns:
            New CookiePayload with rotated refresh token

        Raises:
            YotoAuthError: If refresh fails
        """
        # Refresh access token
        access_token, access_expiry, new_refresh_token, refresh_expiry = (
            await self.refresh_access_token(refresh_token)
        )

        # Update in-memory session
        self.session_service.update_access_token(
            session_id=session_id,
            access_token=access_token,
            access_token_expiry=access_expiry,
        )

        # Get original session creation time
        session = self.session_service.get_session(session_id)
        created_at = session.created_at if session else time.time()

        # Create new cookie payload
        new_cookie_payload = CookiePayload(
            session_id=session_id,
            refresh_token=new_refresh_token,
            refresh_token_expiry=refresh_expiry,
            created_at=created_at,
        )

        logger.info(f"Refreshed access token for session: {session_id[:8]}...")
        return new_cookie_payload

    def logout_session(self, session_id: str) -> None:
        """
        Logout a session (clear in-memory state).

        Caller must also clear the session cookie.

        Args:
            session_id: Session ID to logout
        """
        # Remove in-memory session
        self.session_service.delete_session(session_id)

        # Remove API client
        self.remove_api_client(session_id)

        logger.info(f"Logged out session: {session_id[:8]}...")

    def is_session_authenticated(self, session_id: Optional[str]) -> bool:
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
        if session.is_access_token_expired():
            return False

        return True

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from memory.

        Returns:
            Number of sessions cleaned up
        """
        # Cleanup sessions
        count = self.session_service.cleanup_expired_sessions()

        # Cleanup corresponding API clients
        for session_id in list(self._api_clients.keys()):
            if not self.session_service.get_session(session_id):
                self.remove_api_client(session_id)

        return count

    def get_current_session_id_and_token(self) -> tuple[str, str]:
        """
        Get the current session ID and access token from context.
        
        This is a helper method for route handlers to get the current session context.
        In a real implementation, this would use context variables.
        
        For now, this returns None and requires session_id to be passed explicitly.
        """
        # NOTE: This is a placeholder. The actual session context should come from
        # the request context set by middleware.
        return None, None

    def clear_tokens(self, session_id: str = None) -> None:
        """
        Clear tokens for a session (on error or logout).

        Args:
            session_id: Session ID (optional, uses context if not provided)
        """
        try:
            session_id = self._get_session_id(session_id)
        except ValueError:
            # No session_id available, nothing to clear
            return

        # Remove API client which clears the token data
        self.remove_api_client(session_id)

    # Proxy methods for YotoApiClient API calls
    # ============================================================================

    async def get_my_content(self) -> list:
        """
        Get user's content from Yoto API.
        
        Returns:
            List of Card objects
        """
        client = await self.get_client()
        return await client.get_my_content()

    async def get_card(self, card_id: str) -> Optional:
        """
        Get a specific card by ID.
        
        Args:
            card_id: Card ID to fetch
            
        Returns:
            Card object or None if not found
        """
        client = await self.get_client()
        return await client.get_card(card_id)

    async def create_card(self, card):
        """
        Create a new card.
        
        Args:
            card: Card object to create
            
        Returns:
            Created Card object with ID
        """
        client = await self.get_client()
        return await client.create_card(card)

    async def update_card(self, card):
        """
        Update an existing card.
        
        Args:
            card: Card object to update
            
        Returns:
            Updated Card object
        """
        client = await self.get_client()
        return await client.update_card(card)

    async def delete_card(self, card_id: str) -> None:
        """
        Delete a card.
        
        Args:
            card_id: Card ID to delete
        """
        client = await self.get_client()
        return await client.delete_card(card_id)
