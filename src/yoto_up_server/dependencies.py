"""
FastAPI dependencies for request-scoped services.
"""

from pathlib import Path
from typing import Annotated, Any, Optional, TypeVar, overload
from fastapi import Depends, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer
from dependency_injector import providers
from dependency_injector import wiring
from loguru import logger

from yoto_up.yoto_api_client import YotoApiClient
from yoto_up_server.container import Container
from yoto_up_server.services.session_service import SessionService
from yoto_up_server.services.session_aware_api_service import SessionAwareApiService
from yoto_up_server.middleware.session_middleware import (
    get_session_from_request,
    get_session_id_from_request,
    get_cookie_payload_from_request,
    set_session_cookie,
    SESSION_COOKIE_SECURE,
)
from yoto_up_server.services.audio_processor import AudioProcessorService
from yoto_up_server.services.upload_manager import UploadManager
from yoto_up_server.services.upload_processing_service import UploadProcessingService
from yoto_up_server.services.upload_session_service import UploadSessionService

security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""

    pass


T = TypeVar("T")


@overload
def ContainerDepends(x: providers.Provider[T]) -> T: ...


@overload
def ContainerDepends(x: Any): ...


def ContainerDepends(x):
    @wiring.inject
    def _(dep=wiring.Provide[x]):
        return dep

    return Depends(_)


def get_container(request: Request) -> Container:
    """Get the DI container from the request app state."""
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]
SessionServiceDep = Annotated[SessionService, ContainerDepends(Container.session_service)]
SessionAwareApiServiceDep = Annotated[
    SessionAwareApiService, ContainerDepends(Container.session_aware_api_service)
]
DebugEnabledDep = Annotated[bool, ContainerDepends(Container.debug_enabled)]
DebugDirDep = Annotated[Path, ContainerDepends(Container.debug_dir)]
AudioProcessorDep = Annotated[
    AudioProcessorService, ContainerDepends(Container.audio_processor)
]
UploadSessionServiceDep = Annotated[
    UploadSessionService, ContainerDepends(Container.upload_session_service)
]
UploadProcessingServiceDep = Annotated[
    UploadProcessingService, ContainerDepends(Container.upload_processing_service)
]
UploadManagerDep = Annotated[UploadManager, ContainerDepends(Container.upload_manager)]


def get_session_id(request: Request) -> str:
    """Get session ID from request cookies."""
    session_id = get_session_id_from_request(request)
    if not session_id:
        raise ValueError("No session ID found in request")
    return session_id


SessionIdDep = Annotated[str, Depends(get_session_id)]


async def require_session_auth(
    request: Request,
    response: Response,
    session_api_service: SessionAwareApiServiceDep,
    session_service: SessionServiceDep,
) -> SessionAwareApiService:
    """
    Dependency that requires session-based authentication.

    Handles:
    - Validating existing session from memory
    - Rehydrating session from cookie after restart
    - Refreshing expired access tokens
    - Setting updated cookies with rotated refresh tokens

    Raises AuthenticationError if authentication fails.
    """
    # Get session data from request state (set by middleware)
    session = get_session_from_request(request)
    session_id = get_session_id_from_request(request)
    cookie_payload = get_cookie_payload_from_request(request)

    # Case 1: No session cookie at all
    if not cookie_payload:
        logger.debug("No session cookie found")
        raise AuthenticationError("Not authenticated")

    # Case 2: Session exists in memory
    if session:
        # Check if access token expired
        if session.is_access_token_expired():
            logger.info(f"Access token expired for session: {session_id[:8]}..., refreshing")

            try:
                # Refresh access token
                new_cookie_payload = await session_api_service.refresh_session_access_token(
                    session_id=session_id,
                    refresh_token=cookie_payload.refresh_token,
                )

                # Update cookie with rotated refresh token
                set_session_cookie(
                    response,
                    session_service,
                    new_cookie_payload,
                    secure=SESSION_COOKIE_SECURE,
                )

                logger.info(f"Access token refreshed for session: {session_id[:8]}...")

            except Exception as e:
                logger.error(f"Failed to refresh access token: {e}")
                raise AuthenticationError("Token refresh failed") from e

        # Set current session ID on service for this request
        session_api_service.set_current_session_id(session_id)
        return session_api_service

    # Case 3: Session not in memory but cookie exists (post-restart)
    logger.info(f"Session not in memory, rehydrating from cookie: {session_id[:8]}...")

    try:
        # Rehydrate session from cookie
        rehydrated_session_id, new_cookie_payload = (
            await session_api_service.rehydrate_session_from_cookie(cookie_payload)
        )

        # Update cookie with rotated refresh token
        set_session_cookie(
            response,
            session_service,
            new_cookie_payload,
            secure=SESSION_COOKIE_SECURE,
        )

        logger.info(f"Session rehydrated: {rehydrated_session_id[:8]}...")
        
        # Set current session ID on service for this request
        session_api_service.set_current_session_id(rehydrated_session_id)
        return session_api_service

    except Exception as e:
        logger.error(f"Failed to rehydrate session: {e}")
        raise AuthenticationError("Session rehydration failed") from e


AuthenticatedSessionApiDep = Annotated[SessionAwareApiService, Depends(require_session_auth)]


async def get_yoto_client(
    session_api: AuthenticatedSessionApiDep,
) -> YotoApiClient:
    """
    Get the YotoApiClient for the current authenticated session.
    
    This dependency ensures the user is authenticated and returns a configured client.
    """
    return await session_api.get_client()


YotoClientDep = Annotated[YotoApiClient, Depends(get_yoto_client)]
