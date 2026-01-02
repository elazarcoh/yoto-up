"""
FastAPI dependencies for request-scoped services.
"""

from pathlib import Path
from typing import Annotated, Any, TypeVar, overload

from dependency_injector import providers, wiring
from fastapi import Depends, Request, Response
from loguru import logger

from yoto_web_server.api.client import YotoApiClient
from yoto_web_server.container import Container
from yoto_web_server.middleware.session_middleware import (
    SESSION_COOKIE_SECURE,
    get_cookie_payload_from_request,
    get_session_from_request,
    get_session_id_from_request,
    set_session_cookie,
)
from yoto_web_server.services.icon_service import IconService
from yoto_web_server.services.mqtt_service import MqttService
from yoto_web_server.services.audio_processor import AudioProcessorService
from yoto_web_server.services.session_aware_api_service import SessionAwareApiService
from yoto_web_server.services.session_service import SessionService
from yoto_web_server.services.upload_session_service import UploadSessionService
from yoto_web_server.services.upload_processing_service import UploadProcessingService


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""

    pass


T = TypeVar("T")


@overload
def ContainerDepends(x: providers.Provider[T]) -> T: ...


@overload
def ContainerDepends(x: Any) -> Any: ...


def ContainerDepends(x: Any) -> Any:
    @wiring.inject
    def _(dep: Any = wiring.Provide[x]) -> Any:
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
IconServiceDep = Annotated[IconService, ContainerDepends(Container.icon_service)]
UploadSessionServiceDep = Annotated[
    UploadSessionService, ContainerDepends(Container.upload_session_service)
]
UploadProcessingServiceDep = Annotated[
    UploadProcessingService, ContainerDepends(Container.upload_processing_service)
]
MqttServiceDep = Annotated[MqttService, ContainerDepends(Container.mqtt_service)]
AudioProcessorServiceDep = Annotated[
    AudioProcessorService, ContainerDepends(Container.audio_processor)
]


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
    session = get_session_from_request(request)
    session_id = get_session_id_from_request(request)
    cookie_payload = get_cookie_payload_from_request(request)

    if session_id is None:
        logger.debug("No session ID found in request")
        raise AuthenticationError("Not authenticated")

    if not cookie_payload:
        logger.debug("No session cookie found")
        raise AuthenticationError("Not authenticated")

    # Case: Session exists in memory
    if session:
        if session.session_id != session_id:
            logger.error(
                f"Session ID mismatch: cookie {session_id[:8]}... vs memory {session.session_id[:8]}..."
            )
            raise AuthenticationError("Session ID mismatch")

        # Check if access token expired
        if session.is_access_token_expired():
            logger.info(f"Access token expired for session: {session_id[:8]}..., refreshing")

            try:
                new_cookie_payload = await session_api_service.refresh_session_access_token(
                    session_id=session_id,
                    cookie_payload=cookie_payload,
                )
                set_session_cookie(
                    response,
                    session_service,
                    new_cookie_payload,
                    secure=SESSION_COOKIE_SECURE,
                )
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise AuthenticationError("Token refresh failed")

        session_api_service.set_current_session_id(session_id)
        return session_api_service

    # Case: Session not in memory, try to rehydrate from cookie
    logger.info(f"Rehydrating session from cookie: {session_id[:8]}...")

    try:
        _, new_cookie_payload = await session_api_service.rehydrate_session_from_cookie(
            cookie_payload
        )
        set_session_cookie(
            response,
            session_service,
            new_cookie_payload,
            secure=SESSION_COOKIE_SECURE,
        )
        session_api_service.set_current_session_id(session_id)
        return session_api_service
    except Exception as e:
        logger.error(f"Session rehydration failed: {e}")
        raise AuthenticationError("Session expired")


AuthenticatedSessionApiDep = Annotated[SessionAwareApiService, Depends(require_session_auth)]


async def get_yoto_client(session_api: AuthenticatedSessionApiDep) -> YotoApiClient:
    """Get authenticated Yoto API client for current session."""
    return await session_api.get_client()


YotoApiDep = Annotated[YotoApiClient, Depends(get_yoto_client)]
