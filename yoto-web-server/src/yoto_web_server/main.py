"""
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from yoto_web_server.container import Container
from yoto_web_server.core.config import get_settings
from yoto_web_server.core.logging import configure_logging
from yoto_web_server.middleware.session_middleware import SessionMiddleware
from yoto_web_server.routers import auth, devices, icons, playlists
from yoto_web_server.templates.base import render_page
from yoto_web_server.templates.home import HomePage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager."""
    settings = get_settings()
    configure_logging(debug=settings.yoto_up_debug)
    logger.info("Starting Yoto Web Server")

    # Initialize container
    container = Container()
    container.wire(
        modules=[
            "yoto_web_server.dependencies",
            "yoto_web_server.routers.auth",
            "yoto_web_server.routers.playlists",
            "yoto_web_server.routers.icons",
            "yoto_web_server.routers.devices",
            "yoto_web_server.middleware.session_middleware",
        ]
    )
    app.state.container = container

    logger.info(f"Server running at http://{settings.host}:{settings.port}")

    yield

    # Cleanup
    logger.info("Shutting down Yoto Web Server")
    container.unwire()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Yoto Web Server",
        description="A web interface for managing Yoto card content",
        version="0.1.0",
        docs_url="/docs" if settings.yoto_up_debug else None,
        redoc_url="/redoc" if settings.yoto_up_debug else None,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        SessionMiddleware,
        require_https=settings.session_cookie_secure,
    )

    # Include routers
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
    app.include_router(icons.router, prefix="/icons", tags=["icons"])
    app.include_router(devices.router, prefix="/devices", tags=["devices"])

    # Mount static files
    import importlib.resources

    static_path = importlib.resources.files("yoto_web_server") / "static"
    if static_path.is_dir():  # type: ignore
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Root route
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        """Home page."""
        return render_page(
            title="Yoto Web Server",
            content=HomePage(),
            request=request,
        )

    # Health check
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create app instance for uvicorn
app = create_app()
