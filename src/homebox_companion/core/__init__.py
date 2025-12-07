"""Core infrastructure for Homebox Companion."""

from .config import Settings, settings
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    DetectionError,
    HomeboxCompanionError,
)
from .field_preferences import (
    FieldPreferences,
    load_field_preferences,
    reset_field_preferences,
    save_field_preferences,
)
from .logging import logger, setup_logging

__all__ = [
    # Configuration
    "Settings",
    "settings",
    # Field Preferences
    "FieldPreferences",
    "load_field_preferences",
    "save_field_preferences",
    "reset_field_preferences",
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





