"""Centralized logging configuration for Homebox Companion."""

from __future__ import annotations

import sys

from loguru import logger

from .config import settings


def setup_logging() -> None:
    """Configure loguru for the application.

    Sets up:
    - Console logging with colorized output
    - File logging with daily rotation
    """
    # Remove default handler
    logger.remove()

    # Console handler with colors
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    # File handler with rotation
    logger.add(
        "logs/homebox_companion_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
    )


# Export logger for use throughout the application
__all__ = ["logger", "setup_logging"]







