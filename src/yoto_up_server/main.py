"""
Yoto Up Server - FastAPI application entry point.

This is the main entry point for the FastAPI-based web application.
Run with: uvicorn yoto_up_server.main:app --reload
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, encoders
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from loguru import logger
from pydom import render, html as d
from pydom.element import Element
from pydom.component import Component
from dependency_injector.wiring import Provide

from yoto_up_server.container import Container
from yoto_up_server.routers import auth, cards, icons, playlists, upload
from yoto_up_server.templates.base import render_page
from yoto_up_server.templates.home import HomePage
from yoto_up_server.dependencies import AuthenticationError
from yoto_up_server.middleware.session_middleware import SessionMiddleware
import dotenv


# Application root directory
APP_ROOT = Path(__file__).parent
STATIC_DIR = APP_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Load environment variables from .env file
    dotenv.load_dotenv()

    # Initialize the DI container
    container = Container()
    app.state.container = container

    # In-memory OAuth state storage (for CSRF protection)
    app.state.oauth_states = {}

    logger.info("Yoto Up Server starting...")

    # Log debug mode status
    if container.debug_enabled():
        logger.info(f"Debug mode enabled. Output directory: {container.debug_dir()}")

    # Ensure static directory exists
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Yoto Up Server shutting down...")
    # Cleanup any sessions
    session_api_service = container.session_aware_api_service()
    cleaned = await session_api_service.cleanup_expired_sessions()
    logger.info(f"Cleaned up {cleaned} expired sessions")


encoders.encoders_by_class_tuples[render] = (Element, Component)
app = FastAPI(
    title="Yoto Up Server",
    description="Web-based Yoto card management application",
    version="0.1.0",
    lifespan=lifespan,
)


# Add session middleware
app.add_middleware(
    SessionMiddleware,
    require_https=False,  # Set to True in production with HTTPS
)


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> HTMLResponse:
    """
    Handle authentication errors by showing a session-expired modal
    and redirecting to the login page.
    """

    html_response = (
        d.Div(
            classes="fixed inset-0 flex items-center justify-center bg-black/50 z-[9999]"
        )(
            d.Div(
                classes="bg-white rounded-lg shadow-lg p-6 max-w-md w-full text-center",
            )(
                d.H2(classes="text-xl font-bold text-gray-900 m-0 mb-4")(
                    "Session Expired"
                ),
                d.P(classes="text-gray-600 m-0 mb-6 leading-relaxed")(
                    "Your authentication session has expired. Please log in again."
                ),
                d.A(
                    href="/auth",
                    classes="inline-block px-6 py-2.5 bg-indigo-600 text-white rounded-md font-medium cursor-pointer no-underline transition-colors duration-200 hover:bg-indigo-700",
                )("Go to Login"),
            ),
            d.Script()("""//js
                // Auto-redirect to login page after 3 seconds
                setTimeout(() => {
                    window.location.href = '/auth';
                }, 3000);
            """),
        ),
    )
    return HTMLResponse(
        content=render_page(
            title="Session Expired",
            content=html_response,
            request=request,
        ),
        status_code=401,
    )


# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(cards.router, prefix="/cards", tags=["Cards"])
# app.include_router(icons.router, prefix="/icons", tags=["Icons"])  # DISABLED: Icons removed
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(upload.router, prefix="/upload", tags=["Upload"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> str:
    """Render the home page."""
    from yoto_up_server.middleware.session_middleware import get_session_id_from_request

    container: Container = request.app.state.container
    session_api_service = container.session_aware_api_service()

    # Check session-based authentication
    session_id = get_session_id_from_request(request)
    is_authenticated = session_api_service.is_session_authenticated(session_id)

    return render_page(
        title="Yoto Up",
        content=HomePage(is_authenticated=is_authenticated),
        request=request,
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
