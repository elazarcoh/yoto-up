"""
CLI entry point for the Yoto Up Server.
"""

import webbrowser
import time
import threading
from typing import Optional
import sys
import logging

import typer
import uvicorn
from loguru import logger
from yoto_up_server.logging_config import configure_logging, EndpointsFilter


app = typer.Typer(help="Yoto Up Server CLI")


def open_browser(url: str, delay: float = 1.0):
    """Open the browser after a delay to allow the server to start."""

    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
            logger.info(f"Opened browser at {url}")
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


@app.command()
def main(
    host: str = typer.Option("127.0.0.1", help="Server host"),
    port: int = typer.Option(8000, help="Server port"),
    reload: bool = typer.Option(True, help="Enable auto-reload on code changes"),
    no_browser: bool = typer.Option(False, help="Don't automatically open browser"),
    log_level: str = typer.Option("info", help="Logging level"),
    debug: bool = typer.Option(
        False, help="Enable debug mode (debug logging + debug output directory)"
    ),
):
    """Start the Yoto Up Server."""

    url = f"http://{host}:{port}"

    # Determine actual log level for uvicorn
    actual_log_level = log_level
    if debug:
        actual_log_level = "debug"

    # Open browser if requested
    if not no_browser:
        open_browser(url, delay=1.5)

    logger.info(f"Starting Yoto Up Server at {url}")

    if debug:
        logger.info("Debug mode enabled")

    # Run the server with debug mode in environment
    import os

    if debug:
        os.environ["YOTO_UP_DEBUG"] = "true"
        os.environ["YOTO_UP_DEBUG_DIR"] = "./debug"

    # Determine actual log level for uvicorn
    actual_log_level = log_level
    if debug:
        actual_log_level = "debug"

    # Run the server
    uvicorn.run(
        "yoto_up_server.main:app",
        host=host,
        port=port,
        reload=reload,
        # log_level=actual_log_level,
    )


if __name__ == "__main__":
    app()
