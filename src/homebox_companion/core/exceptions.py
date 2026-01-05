"""Custom exceptions for Homebox Companion.

Domain exceptions carry HTTP metadata, error codes, and safe context
for centralized exception handling in the FastAPI layer.
"""

from __future__ import annotations

from typing import Any, Literal

LogLevel = Literal["debug", "info", "warning", "error"]


class HomeboxCompanionError(Exception):
    """Base domain exception with HTTP metadata.

    All domain exceptions inherit from this class and can be handled
    by a single FastAPI exception handler.

    Attributes:
        status_code: HTTP status code to return to clients.
        error_code: Stable string code for clients/monitoring (e.g., "AUTH_FAILED").
        log_level: Severity level for logging this exception type.
        user_message: Safe, user-friendly message (no sensitive data).
        context: Additional safe metadata for logging (url, upstream_status, etc.).
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    log_level: LogLevel = "error"

    def __init__(
        self,
        message: str = "",
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.user_message = user_message or "An unexpected error occurred"
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Structured representation for logging."""
        return {
            "error_code": self.error_code,
            "message": str(self),
            "user_message": self.user_message,
            **self.context,
        }


# =============================================================================
# Authentication Errors
# =============================================================================


class HomeboxAuthError(HomeboxCompanionError):
    """Authentication or authorization failure.

    Raised when:
    - Credentials are invalid (login)
    - Session token expired
    - Access forbidden (403)
    """

    status_code = 401
    error_code = "AUTH_FAILED"
    log_level: LogLevel = "warning"


# =============================================================================
# Connection Errors
# =============================================================================


class HomeboxConnectionError(HomeboxCompanionError):
    """DNS resolution or connection refused errors.

    Separate from timeout for monitoring/retry logic differentiation.
    """

    status_code = 503
    error_code = "HOMEBOX_UNAVAILABLE"
    log_level: LogLevel = "warning"


class HomeboxTimeoutError(HomeboxCompanionError):
    """Request timeout - server reachable but slow/unresponsive."""

    status_code = 503
    error_code = "HOMEBOX_TIMEOUT"
    log_level: LogLevel = "warning"


# =============================================================================
# API Errors
# =============================================================================


class HomeboxAPIError(HomeboxCompanionError):
    """Homebox returned an error response (5xx, unexpected 4xx)."""

    status_code = 502
    error_code = "HOMEBOX_ERROR"
    log_level: LogLevel = "error"


# =============================================================================
# LLM/AI Errors
# =============================================================================


class LLMServiceError(HomeboxCompanionError):
    """LLM API service unavailable or erroring."""

    status_code = 502
    error_code = "LLM_UNAVAILABLE"
    log_level: LogLevel = "error"


class CapabilityNotSupportedError(HomeboxCompanionError):
    """Model doesn't support required capability (e.g., vision)."""

    status_code = 400
    error_code = "CAPABILITY_UNSUPPORTED"
    log_level: LogLevel = "warning"


class JSONRepairError(HomeboxCompanionError):
    """AI returned malformed JSON that couldn't be repaired."""

    status_code = 502
    error_code = "JSON_REPAIR_FAILED"
    log_level: LogLevel = "warning"

