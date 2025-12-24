"""
Yoto Up Server - FastAPI application entry point.

This is the main entry point for the FastAPI-based web application.
Run with: uvicorn yoto_up_server.main:app --reload
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, encoders
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from loguru import logger
from pydom import render
from pydom.element import Element
from pydom.component import Component

from yoto_up_server.container import Container
from yoto_up_server.routers import auth, cards, icons, playlists, upload
from yoto_up_server.templates.base import render_page
from yoto_up_server.templates.home import HomePage


# Application root directory
APP_ROOT = Path(__file__).parent
STATIC_DIR = APP_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
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

encoders.encoders_by_class_tuples[render] = (Element, Component)
app = FastAPI(
    title="Yoto Up Server",
    description="Web-based Yoto card management application",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(cards.router, prefix="/cards", tags=["Cards"])
app.include_router(icons.router, prefix="/icons", tags=["Icons"])
app.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
app.include_router(upload.router, prefix="/upload", tags=["Upload"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> str:
    """Render the home page."""
    container: Container = request.app.state.container
    api_service = container.api_service()
    
    is_authenticated = api_service.is_authenticated()
    
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
