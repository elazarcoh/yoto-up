"""
FastAPI dependencies for request-scoped services.
"""

from typing import Annotated, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from yoto_up_server.container import Container
from yoto_up_server.services.api_service import ApiService


security = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    """Get the DI container from app state."""
    return request.app.state.container


def get_api_service(request: Request) -> ApiService:
    """Get the API service from the container."""
    container = get_container(request)
    return container.api_service()


async def require_auth(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None,
) -> ApiService:
    """Dependency that requires authentication."""
    api_service = get_api_service(request)
    
    if not api_service.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return api_service


# Type aliases for cleaner annotations
ApiServiceDep = Annotated[ApiService, Depends(get_api_service)]
AuthenticatedApiDep = Annotated[ApiService, Depends(require_auth)]
ContainerDep = Annotated[Container, Depends(get_container)]
