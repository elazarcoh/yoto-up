"""
Yoto Up Server - FastAPI application entry point.

This is the main entry point for the FastAPI-based web application.
Run with: uvicorn yoto_up_server.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

import dotenv
from fastapi import FastAPI, Request, encoders
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydom import html as d
from pydom import render
from pydom.component import Component
from pydom.element import Element

from yoto_web_server.api.exceptions import YotoAuthError
from yoto_web_server.container import Container
from yoto_web_server.dependencies import AuthenticationError, YotoApiDep
from yoto_web_server.logging_config import configure_logging
from yoto_web_server.middleware.session_middleware import SessionMiddleware
from yoto_web_server.routers import auth, devices, icons, playlists
from yoto_web_server.templates.base import render_page
from yoto_web_server.templates.home import HomePage

# Application root directory
APP_ROOT = Path(__file__).parent
STATIC_DIR = APP_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Load environment variables from .env file
    dotenv.load_dotenv()

    # Configure logging first

    configure_logging()

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

    # Initialize icon service (fetches public manifest)
    icon_service = container.icon_service()
    try:
        await icon_service.initialize()
        logger.info("Icon service initialized successfully")
    except Exception as e:
        logger.warning(f"Icon service initialization failed: {e}")

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


async def authentication_error_handler(request: Request, exc: AuthenticationError) -> HTMLResponse:
    """
    Handle authentication errors by showing a session-expired modal
    and redirecting to the login page.
    """

    html_response = d.Div(
        classes="fixed inset-0 flex items-center justify-center bg-black/50 z-[9999]"
    )(
        d.Div(
            classes="bg-white rounded-lg shadow-lg p-6 max-w-md w-full text-center",
        )(
            d.H2(classes="text-xl font-bold text-gray-900 m-0 mb-4")("Session Expired"),
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
    )
    return HTMLResponse(
        content=render_page(
            title="Session Expired",
            content=html_response,
            request=request,
        ),
        status_code=401,
    )


async def client_auth_error(request: Request, exc: YotoAuthError):
    """
    Handle authentication errors by showing a session-expired modal
    and redirecting to the login page.
    """

    html_response = d.Div(
        classes="fixed inset-0 flex items-center justify-center bg-black/50 z-[9999]"
    )(
        d.Div(
            classes="bg-white rounded-lg shadow-lg p-6 max-w-md w-full text-center",
        )(
            d.H2(classes="text-xl font-bold text-gray-900 m-0 mb-4")("Session Expired"),
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
    )
    return HTMLResponse(
        content=render_page(
            title="Session Expired",
            content=html_response,
            request=request,
        ),
        status_code=401,
    )


# Register exception handlers
app.exception_handler(AuthenticationError)(authentication_error_handler)
app.exception_handler(YotoAuthError)(client_auth_error)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(icons.router, tags=["Icons"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(devices.router, prefix="/devices", tags=["Devices"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, *, client: YotoApiDep) -> str:
    """Render the home page."""

    # Check session-based authentication
    is_authenticated = client.is_authenticated()

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
