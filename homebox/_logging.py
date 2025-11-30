"""Logging configuration for the homebox library.

Uses loguru with sensible defaults that can be easily customized.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger

# Remove default handler and add a clean one
logger.remove()

# Default format: clean and readable
_DEFAULT_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)

# Add stderr handler with INFO level by default (can be changed via configure())
_handler_id = logger.add(
    sys.stderr,
    format=_DEFAULT_FORMAT,
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=False,  # Disable in production for security
)


def configure(
    *,
    level: str = "INFO",
    format: str | None = None,
    colorize: bool = True,
    diagnose: bool = False,
) -> Logger:
    """Configure the homebox logger.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format: Custom format string. Uses loguru format syntax.
        colorize: Whether to colorize output.
        diagnose: Show variable values in tracebacks (disable in production).

    Returns:
        The configured logger instance.

    Example:
        >>> import homebox
        >>> homebox.configure(level="DEBUG")
    """
    global _handler_id

    logger.remove(_handler_id)
    _handler_id = logger.add(
        sys.stderr,
        format=format or _DEFAULT_FORMAT,
        level=level.upper(),
        colorize=colorize,
        backtrace=True,
        diagnose=diagnose,
    )
    return logger


def get_logger() -> Logger:
    """Get the homebox logger instance."""
    return logger


__all__ = ["configure", "get_logger", "logger"]
