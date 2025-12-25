"""
Session Middleware - Manages cookie-based session authentication.

Handles:
- Session cookie creation and validation
- Session rehydration after server restart
- Automatic access token refresh
- CSRF protection via SameSite cookies
"""

from typing import Optional
from contextvars import ContextVar

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from dependency_injector.wiring import Provide

from yoto_up_server.services.session_service import (
    SessionService,
    CookiePayload,
    SessionData,
)


# Cookie configuration constants
SESSION_COOKIE_NAME = "yoto_session"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True  # Set to False for local development without HTTPS
SESSION_COOKIE_SAMESITE = "lax"  # CSRF protection

# Context variable for current session ID
_session_id_context: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

# Dependency injection for session service
_session_service: SessionService = Provide["session_service"]


class SessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for cookie-based session management.

    Attaches session data to request.state.session if a valid session exists.
    """

    def __init__(
        self,
        app: ASGIApp,
        require_https: bool = True,
    ):
        """
        Initialize session middleware.

        Args:
            app: ASGI application
            session_service: Session service instance
            require_https: Whether to require HTTPS for secure cookies
        """
        super().__init__(app)
        self.require_https = require_https

    async def dispatch(self, request: Request, call_next):
        """
        Process request and handle session.

        Attaches session data to request.state if valid session cookie exists.
        Also sets context variable for async operations.
        """
        # Extract session cookie
        cookie_value = request.cookies.get(SESSION_COOKIE_NAME)

        # Initialize session state on request
        request.state.session = None
        request.state.session_id = None
        request.state.cookie_payload = None
        
        session_id_token = None

        if cookie_value:
            # Validate and decrypt cookie
            cookie_payload = _session_service.validate_and_decrypt_cookie(
                cookie_value
            )

            if cookie_payload:
                # Store cookie payload for potential refresh
                request.state.cookie_payload = cookie_payload
                request.state.session_id = cookie_payload.session_id
                
                # Set context variable for async operations
                session_id_token = _session_id_context.set(cookie_payload.session_id)

                # Check if session exists in memory
                session_data = _session_service.get_session(
                    cookie_payload.session_id
                )

                if session_data:
                    # Session exists in memory
                    request.state.session = session_data
                    logger.debug(
                        f"Session loaded from memory: {cookie_payload.session_id[:8]}..."
                    )
                else:
                    # Session not in memory (likely after restart)
                    # Will be rehydrated by auth dependency if needed
                    logger.debug(
                        f"Session cookie valid but not in memory: {cookie_payload.session_id[:8]}... "
                        "(will rehydrate on authenticated request)"
                    )

        try:
            # Process request
            response = await call_next(request)
        finally:
            # Clear context variable after request
            if session_id_token is not None:
                _session_id_context.reset(session_id_token)

        return response


def set_session_cookie(
    response: Response,
    session_service: SessionService,
    cookie_payload: CookiePayload,
    secure: bool = SESSION_COOKIE_SECURE,
) -> None:
    """
    Set encrypted session cookie on response.

    Args:
        response: FastAPI response object
        session_service: Session service for encryption
        cookie_payload: Cookie payload to encrypt and set
        secure: Whether to set Secure flag (requires HTTPS)
    """
    encrypted_value = session_service.encrypt_cookie(cookie_payload)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=encrypted_value,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=SESSION_COOKIE_HTTPONLY,
        secure=secure,
        samesite=SESSION_COOKIE_SAMESITE,
        path="/",
    )

    logger.debug(f"Set session cookie for: {cookie_payload.session_id[:8]}...")


def clear_session_cookie(response: Response) -> None:
    """
    Clear session cookie (logout).

    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=SESSION_COOKIE_HTTPONLY,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
    )

    logger.debug("Cleared session cookie")


def get_session_from_request(request: Request) -> Optional[SessionData]:
    """
    Helper to get session data from request state.

    Args:
        request: FastAPI request

    Returns:
        SessionData if exists, None otherwise
    """
    return getattr(request.state, "session", None)


def get_session_id_from_request(request: Request) -> Optional[str]:
    """
    Helper to get session ID from request state.

    Args:
        request: FastAPI request

    Returns:
        Session ID if exists, None otherwise
    """
    return getattr(request.state, "session_id", None)


def get_cookie_payload_from_request(request: Request) -> Optional[CookiePayload]:
    """
    Helper to get cookie payload from request state.

    Args:
        request: FastAPI request

    Returns:
        CookiePayload if exists, None otherwise
    """
    return getattr(request.state, "cookie_payload", None)
