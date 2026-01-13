"""Centralized logging configuration for Homebox Companion."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import loguru

from .config import settings

# LLM debug log directory
LLM_DEBUG_LOG_DIR = "logs"


def get_log_level_value() -> int:
    """Get the numeric value of the current log level using loguru.

    Returns:
        Numeric log level (TRACE=5, DEBUG=10, INFO=20, etc.).
        Returns INFO level (20) if the configured level is invalid.
    """
    try:
        return logger.level(settings.log_level.upper()).no
    except ValueError:
        # Invalid level name, default to INFO
        return 20


def _patcher(record: dict) -> None:
    """Ensure request_id exists in extra for all log records.

    This handles logs emitted outside request context (startup, shutdown, background tasks).
    """
    if "request_id" not in record["extra"]:
        record["extra"]["request_id"] = "-"


def _llm_debug_filter(record: loguru.Record) -> bool:
    """Filter to only pass LLM debug log entries."""
    return record["extra"].get("llm_debug", False)


def _exclude_llm_debug_filter(record: loguru.Record) -> bool:
    """Exclude LLM debug entries from the main log file."""
    return not record["extra"].get("llm_debug", False)


def setup_logging() -> None:
    """Configure loguru for the application.

    Sets up:
    - Console logging with colorized output (includes request-ID when available)
    - File logging with daily rotation
    - LLM debug logging with separate file and rotation
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
    # Excludes LLM debug logs which go to their own dedicated file
    logger.add(
        "logs/homebox_companion_{time:YYYY-MM-DD}.log",
        rotation="50 MB",  # Rotate if file exceeds 50MB OR at midnight
        retention="7 days",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[request_id]:>12} | {name}:{function}:{line} - {message}"
        ),
        level=settings.log_level,
        filter=_exclude_llm_debug_filter,
    )

    # LLM debug log handler - separate file for raw LLM interactions
    # Uses JSON lines format for easy parsing by the API
    # Detail level varies based on configured log level (see llm_client.py)
    logger.add(
        f"{LLM_DEBUG_LOG_DIR}/llm_debug_{{time:YYYY-MM-DD}}.log",
        rotation="10 MB",  # Smaller rotation for debug data
        retention="3 days",  # Shorter retention - debug data ages quickly
        format="{message}",  # Pure JSON, no metadata prefix
        filter=_llm_debug_filter,
        level="TRACE",  # Always capture (detail controlled by entry content)
    )


# Export logger for use throughout the application
__all__ = ["logger", "setup_logging", "get_log_level_value", "LLM_DEBUG_LOG_DIR"]
