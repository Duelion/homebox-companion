"""Custom exceptions for Homebox Companion."""

from __future__ import annotations


class HomeboxCompanionError(Exception):
    """Base exception for all Homebox Companion errors."""

    pass


class AuthenticationError(HomeboxCompanionError):
    """Raised when authentication fails (401 Unauthorized)."""

    pass


class APIError(HomeboxCompanionError):
    """Raised when an API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(HomeboxCompanionError):
    """Raised when there's a configuration issue."""

    pass


class DetectionError(HomeboxCompanionError):
    """Raised when item detection fails."""

    pass






