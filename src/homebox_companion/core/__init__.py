"""Core infrastructure for Homebox Companion."""

from .config import Settings, settings
from .exceptions import (
    CapabilityNotSupportedError,
    HomeboxAPIError,
    HomeboxAuthError,
    HomeboxCompanionError,
    HomeboxConnectionError,
    HomeboxTimeoutError,
    JSONRepairError,
    LLMServiceError,
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
    "HomeboxAuthError",
    "HomeboxConnectionError",
    "HomeboxTimeoutError",
    "HomeboxAPIError",
    "LLMServiceError",
    "CapabilityNotSupportedError",
    "JSONRepairError",
    # Logging
    "logger",
    "setup_logging",
]
