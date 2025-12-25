"""
Session Service - Manages session-based authentication with soft persistence.

Implements the following requirements:
- Cookie-based sessions with encrypted OAuth refresh tokens
- In-memory session store for access tokens
- Session rehydration after server restart using refresh tokens
- No external persistence (no DB, Redis, or filesystem)
- Proper token rotation and security
"""

import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from loguru import logger


@dataclass
class SessionData:
    """In-memory session data (ephemeral, lost on restart)."""

    session_id: str
    access_token: str
    access_token_expiry: float
    created_at: float
    # Background job state could go here
    jobs: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.jobs is None:
            self.jobs = {}

    def is_access_token_expired(self) -> bool:
        """Check if access token has expired."""
        return time.time() >= self.access_token_expiry


@dataclass
class CookiePayload:
    """Data stored in the session cookie (persistent across restarts)."""

    session_id: str
    refresh_token: str
    refresh_token_expiry: float
    created_at: float

    def is_refresh_token_expired(self) -> bool:
        """Check if refresh token has expired."""
        return time.time() >= self.refresh_token_expiry

    def to_string(self) -> str:
        """Serialize to string for cookie storage."""
        return f"{self.session_id}|{self.refresh_token}|{self.refresh_token_expiry}|{self.created_at}"

    @classmethod
    def from_string(cls, data: str) -> "CookiePayload":
        """Deserialize from cookie string."""
        parts = data.split("|")
        if len(parts) != 4:
            raise ValueError("Invalid cookie payload format")

        return cls(
            session_id=parts[0],
            refresh_token=parts[1],
            refresh_token_expiry=float(parts[2]),
            created_at=float(parts[3]),
        )


class SessionService:
    """
    Manages session-based authentication with soft persistence.

    Architecture:
    - Cookie stores: session_id, encrypted refresh_token, expiry, created_at
    - Memory stores: access_token, access_token_expiry, job state
    - After restart: rehydrate session from cookie refresh token
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize session service.

        Args:
            encryption_key: 32-byte key for Fernet encryption.
                          If None, generates a new key (sessions won't survive restart).
        """
        # Generate or use provided encryption key
        if encryption_key is None:
            # Generate new key - WARNING: sessions won't survive restart without persistent key
            self._encryption_key = Fernet.generate_key()
            logger.warning(
                "Generated ephemeral encryption key. Sessions will not survive server restart. "
                "Provide a persistent key in production."
            )
        else:
            self._encryption_key = encryption_key

        self._cipher = Fernet(self._encryption_key)

        # In-memory session store (cleared on restart)
        self._sessions: Dict[str, SessionData] = {}

    def create_session(
        self,
        access_token: str,
        access_token_expiry: float,
        refresh_token: str,
        refresh_token_expiry: float,
    ) -> tuple[str, CookiePayload]:
        """
        Create a new session with both in-memory and cookie data.

        Args:
            access_token: OAuth access token (short-lived)
            access_token_expiry: Unix timestamp when access token expires
            refresh_token: OAuth refresh token (long-lived)
            refresh_token_expiry: Unix timestamp when refresh token expires

        Returns:
            tuple of (session_id, cookie_payload)
        """
        # Generate unique session ID
        session_id = secrets.token_urlsafe(32)
        created_at = time.time()

        # Create in-memory session data
        session_data = SessionData(
            session_id=session_id,
            access_token=access_token,
            access_token_expiry=access_token_expiry,
            created_at=created_at,
        )
        self._sessions[session_id] = session_data

        # Create cookie payload with refresh token
        cookie_payload = CookiePayload(
            session_id=session_id,
            refresh_token=refresh_token,
            refresh_token_expiry=refresh_token_expiry,
            created_at=created_at,
        )

        logger.info(f"Created new session: {session_id[:8]}...")
        return session_id, cookie_payload

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Get in-memory session data by session ID.

        Returns None if session doesn't exist in memory.
        This will be None after a server restart until rehydrated.
        """
        return self._sessions.get(session_id)

    def rehydrate_session(
        self,
        session_id: str,
        access_token: str,
        access_token_expiry: float,
        created_at: float,
    ) -> SessionData:
        """
        Rehydrate a session from cookie data after server restart.

        Creates a new in-memory session entry with fresh access token
        obtained by refreshing the refresh token from the cookie.

        Args:
            session_id: Session ID from cookie
            access_token: New access token obtained from refresh
            access_token_expiry: Expiry time for new access token
            created_at: Original session creation time from cookie

        Returns:
            SessionData for the rehydrated session
        """
        session_data = SessionData(
            session_id=session_id,
            access_token=access_token,
            access_token_expiry=access_token_expiry,
            created_at=created_at,
        )
        self._sessions[session_id] = session_data

        logger.info(f"Rehydrated session: {session_id[:8]}... from cookie")
        return session_data

    def update_access_token(
        self,
        session_id: str,
        access_token: str,
        access_token_expiry: float,
    ) -> None:
        """
        Update access token in existing session (after refresh).

        Args:
            session_id: Session ID
            access_token: New access token
            access_token_expiry: New expiry time
        """
        session = self._sessions.get(session_id)
        if session:
            session.access_token = access_token
            session.access_token_expiry = access_token_expiry
            logger.debug(f"Updated access token for session: {session_id[:8]}...")
        else:
            logger.warning(
                f"Attempted to update non-existent session: {session_id[:8]}..."
            )

    def delete_session(self, session_id: str) -> None:
        """
        Delete a session from memory (logout).

        Note: This only clears in-memory state.
        Cookie must be cleared separately by the caller.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id[:8]}...")

    def encrypt_cookie(self, payload: CookiePayload) -> str:
        """
        Encrypt cookie payload for storage.

        Args:
            payload: Cookie payload to encrypt

        Returns:
            Encrypted string suitable for cookie value
        """
        plaintext = payload.to_string().encode("utf-8")
        encrypted = self._cipher.encrypt(plaintext)
        return encrypted.decode("utf-8")

    def decrypt_cookie(self, encrypted_value: str) -> CookiePayload:
        """
        Decrypt and parse cookie value.

        Args:
            encrypted_value: Encrypted cookie string

        Returns:
            Decrypted CookiePayload

        Raises:
            ValueError: If decryption fails or payload is invalid
        """
        try:
            encrypted_bytes = encrypted_value.encode("utf-8")
            decrypted = self._cipher.decrypt(encrypted_bytes)
            plaintext = decrypted.decode("utf-8")
            return CookiePayload.from_string(plaintext)
        except Exception as e:
            logger.warning(f"Cookie decryption failed: {e}")
            raise ValueError("Invalid or corrupted cookie") from e

    def validate_and_decrypt_cookie(
        self, encrypted_value: Optional[str]
    ) -> Optional[CookiePayload]:
        """
        Validate and decrypt cookie, checking expiry.

        Args:
            encrypted_value: Encrypted cookie string or None

        Returns:
            CookiePayload if valid, None otherwise
        """
        if not encrypted_value:
            return None

        try:
            payload = self.decrypt_cookie(encrypted_value)

            # Check if refresh token expired
            if payload.is_refresh_token_expired():
                logger.info(
                    f"Cookie refresh token expired for session: {payload.session_id[:8]}..."
                )
                return None

            return payload

        except ValueError:
            return None

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from memory.

        Returns:
            Number of sessions cleaned up
        """
        expired = [
            sid
            for sid, session in self._sessions.items()
            if session.is_access_token_expired()
        ]

        for sid in expired:
            del self._sessions[sid]
            logger.debug(f"Cleaned up expired session: {sid[:8]}...")

        return len(expired)

    def get_active_session_count(self) -> int:
        """Get count of active sessions in memory."""
        return len(self._sessions)
