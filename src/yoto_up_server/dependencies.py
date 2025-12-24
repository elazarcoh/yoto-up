"""
FastAPI dependencies for request-scoped services.
"""

from pathlib import Path
from typing import Annotated, Any, Optional, TypeVar, overload
from fastapi import Depends, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError

from yoto_up_server.container import Container
from yoto_up_server.services.api_service import ApiService
from dependency_injector import providers
from dependency_injector import wiring

from yoto_up_server.services.audio_processor import AudioProcessorService
from yoto_up_server.services.icon_service import IconService
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
ApiServiceDep = Annotated[ApiService, ContainerDepends(Container.api_service)]
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
IconServiceDep = Annotated[IconService, ContainerDepends(Container.icon_service)]
UploadManagerDep = Annotated[UploadManager, ContainerDepends(Container.upload_manager)]


async def require_auth(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(security)
    ] = None,
    *,
    api_service: ApiServiceDep,
) -> ApiService:
    """
    Dependency that requires authentication.

    Loads saved tokens from disk and initializes the API service.
    Raises AuthenticationError if no valid tokens exist.
    """

    # Initialize API service (loads tokens from disk if available)
    await api_service.initialize()

    # Now check if authentication is valid
    if not api_service.is_authenticated():
        raise AuthenticationError("Authentication session expired")

    return api_service


AuthenticatedApiDep = Annotated[ApiService, Depends(require_auth)]
