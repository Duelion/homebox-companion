"""Core infrastructure for Homebox Companion."""

from .config import Settings, get_settings, settings
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    DetectionError,
    HomeboxCompanionError,
)
from .logging import logger, setup_logging

__all__ = [
    # Configuration
    "Settings",
    "get_settings",
    "settings",
    # Exceptions
    "HomeboxCompanionError",
    "AuthenticationError",
    "APIError",
    "ConfigurationError",
    "DetectionError",
    # Logging
    "logger",
    "setup_logging",
]





