"""Core infrastructure for Homebox Companion."""

from .config import Settings, settings
from .exceptions import (
    APIError,
    AuthenticationError,
    CapabilityNotSupportedError,
    ConfigurationError,
    DetectionError,
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
    "AuthenticationError",  # Legacy alias for HomeboxAuthError
    "APIError",
    "ConfigurationError",
    "DetectionError",
    # Logging
    "logger",
    "setup_logging",
]





