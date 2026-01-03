"""Centralized logging configuration for Homebox Companion."""

from __future__ import annotations

import sys

from loguru import logger

from .config import settings


def _patcher(record: dict) -> None:
    """Ensure request_id exists in extra for all log records.

    This handles logs emitted outside request context (startup, shutdown, background tasks).
    """
    if "request_id" not in record["extra"]:
        record["extra"]["request_id"] = "-"


def setup_logging() -> None:
    """Configure loguru for the application.

    Sets up:
    - Console logging with colorized output (includes request-ID when available)
    - File logging with daily rotation
    """
    # Remove default handler
    logger.remove()

    # Configure patcher to ensure request_id exists in all log records
    logger.configure(patcher=_patcher)  # type: ignore[arg-type]

    # Console handler with colors
    # {extra[request_id]} is set by RequestIDMiddleware via logger.contextualize()
    # Default "-" in ContextVar handles logs outside request context
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{extra[request_id]:>12}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    # File handler with rotation by size OR time (whichever comes first)
    logger.add(
        "logs/homebox_companion_{time:YYYY-MM-DD}.log",
        rotation="50 MB",  # Rotate if file exceeds 50MB OR at midnight
        retention="7 days",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{extra[request_id]:>12} | "
            "{name}:{function}:{line} - {message}"
        ),
        level=settings.log_level,
    )


# Export logger for use throughout the application
__all__ = ["logger", "setup_logging"]
