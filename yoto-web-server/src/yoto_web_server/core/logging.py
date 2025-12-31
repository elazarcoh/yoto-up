"""
Logging configuration for Yoto Web Server.

Configures loguru with proper formatting and filters for noisy logs.
"""

import logging
import sys
from typing import Any

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Handler that intercepts all log requests and passes them to loguru.

    For more info see:
    https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Propagate logs to loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where the logged message originated
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


class EndpointsFilter:
    """
    Filter to exclude noisy polling endpoints from logs.

    Used to filter out high-frequency endpoints like /upload-sessions
    that would otherwise flood the logs.
    """

    def __init__(self, excluded_prefixes: list[str]) -> None:
        """
        Initialize the filter.

        Args:
            excluded_prefixes: List of URL path prefixes to exclude from logging.
        """
        self.excluded_prefixes = excluded_prefixes

    def __call__(self, record: dict[str, Any]) -> bool:
        """
        Filter function for loguru.

        Returns:
            True if the record should be logged, False otherwise.
        """
        message = record.get("message", "")
        return not any(prefix in message for prefix in self.excluded_prefixes)


def configure_logging(log_level: str = "info", debug: bool = False) -> None:
    """
    Configure loguru logging for the application.

    Args:
        log_level: Logging level (debug, info, warning, error, critical, trace)
        debug: Whether debug mode is enabled
    """
    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.NOTSET)

    # Configure uvicorn loggers
    loggers = (
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict
        if name.startswith("uvicorn.")
    )
    for uvicorn_logger in loggers:
        uvicorn_logger.handlers = []

    logging.getLogger("uvicorn").handlers = [intercept_handler]

    # Determine actual log level
    actual_level = "debug" if debug else log_level

    # Create filter for polling endpoints
    polling_filter = EndpointsFilter(["/upload-sessions"])

    # Add stdout handler with custom format
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        level=actual_level.upper(),
        colorize=True,
        filter=polling_filter,
    )

    logger.info(f"Logging configured at level: {actual_level.upper()}")
