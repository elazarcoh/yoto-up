"""
CLI entry point for the Yoto Web Server.
"""

import os
import threading
import time
import webbrowser

import typer
import uvicorn
from dotenv import load_dotenv
from loguru import logger

from yoto_web_server.core.config import get_settings
from yoto_web_server.core.logging import configure_logging

HERE = os.path.dirname(os.path.abspath(__file__))

app = typer.Typer(
    name="yoto-server",
    help="Yoto Web Server - Manage Yoto cards and playlists from your browser",
)


def open_browser(url: str, delay: float = 1.0) -> None:
    """Open the browser after a delay to allow the server to start."""

    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
            logger.info(f"Opened browser at {url}")
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


@app.command()
def serve(
    host: str | None = typer.Option(
        None,
        "--host",
        "-h",
        help="Server host (env: YOTO_UP_HOST or HOST). Default: 127.0.0.1",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Server port (env: YOTO_UP_PORT or PORT). Default: 8000",
    ),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload on code changes"),
    browser: bool = typer.Option(False, "--browser", help="Automatically open browser"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Logging level"),
    debug: bool = typer.Option(
        False, "--debug", "-d", help="Enable debug mode (debug logging + debug output directory)"
    ),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
) -> None:
    """Start the Yoto Web Server."""
    load_dotenv()

    configure_logging(log_level=log_level, debug=debug)

    # Precedence: CLI args > environment variables > defaults
    env_host = os.getenv("YOTO_UP_HOST") or os.getenv("HOST")
    resolved_host = host or env_host or "127.0.0.1"

    resolved_port = None
    if port is not None:
        resolved_port = port
    else:
        for name in ("YOTO_UP_PORT", "PORT"):
            v = os.getenv(name)
            if v:
                try:
                    resolved_port = int(v)
                    break
                except ValueError:
                    logger.warning(f"Environment variable {name} value is not an int: {v}")
        if resolved_port is None:
            resolved_port = 8000

    url = f"http://{resolved_host}:{resolved_port}"

    # Open browser if requested
    if browser:
        open_browser(url, delay=1.5)

    logger.info(f"Starting Yoto Web Server at {url}")

    if debug:
        logger.info("Debug mode enabled")
        os.environ["YOTO_UP_DEBUG"] = "true"
        os.environ["YOTO_UP_DEBUG_DIR"] = "./debug"

    # Determine actual log level for uvicorn
    actual_log_level = "debug" if debug else log_level

    # Ensure encryption key is set
    settings = get_settings()
    try:
        settings.get_encryption_key()
    except RuntimeError as e:
        logger.error(str(e))
        raise typer.Exit(code=1)

    # Run the server
    uvicorn.run(
        "yoto_web_server.main:app",
        host=resolved_host,
        port=resolved_port,
        reload=reload,
        reload_dirs=HERE,
        log_level=actual_log_level,
        workers=workers if not reload else 1,
    )


@app.command()
def generate_key() -> None:
    """Generate a new encryption key for session cookies."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    typer.echo(f"SESSION_ENCRYPTION_KEY={key}")
    typer.echo("\nAdd this to your .env file or set as environment variable.")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
