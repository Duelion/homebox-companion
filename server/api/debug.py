"""Debug logging API endpoints.

Provides endpoints for:
- Enable/disable debug logging
- View debug log status
- Get recent debug log entries
- Clear debug logs
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from homebox_companion.services.debug_logger import get_debug_logger

from ..dependencies import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


# =============================================================================
# Request/Response Models
# =============================================================================


class DebugStatusResponse(BaseModel):
    """Debug logging status."""

    enabled: bool = Field(description="Whether debug logging is currently enabled")
    log_file: str = Field(description="Path to the debug log file")
    entry_count: int = Field(description="Number of entries in the log file")


class DebugLogEntry(BaseModel):
    """A debug log entry."""

    timestamp: str
    level: str
    category: str
    message: str
    data: dict[str, Any] | None = None


class DebugLogsResponse(BaseModel):
    """Response with debug log entries."""

    entries: list[DebugLogEntry]
    total_count: int


class ClearLogsResponse(BaseModel):
    """Response from clearing debug logs."""

    cleared_count: int
    message: str


class DebugLogRequest(BaseModel):
    """Request to write a debug log entry from frontend."""

    category: str = Field(description="Log category (e.g., FRONTEND, API)")
    message: str = Field(description="Log message")
    data: dict[str, Any] | None = Field(default=None, description="Optional structured data")
    level: str = Field(default="INFO", description="Log level")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/debug/status", response_model=DebugStatusResponse)
async def get_debug_status() -> DebugStatusResponse:
    """Get current debug logging status."""
    debug_logger = get_debug_logger()
    entries = debug_logger.get_recent_logs(count=10000)  # Count all

    return DebugStatusResponse(
        enabled=debug_logger.enabled,
        log_file=str(debug_logger.log_file_path),
        entry_count=len(entries),
    )


@router.post("/debug/enable", response_model=DebugStatusResponse)
async def enable_debug_logging() -> DebugStatusResponse:
    """Enable debug logging.

    Debug logging writes detailed logs to the data directory.
    This setting automatically resets to disabled on container restart.
    """
    debug_logger = get_debug_logger()
    debug_logger.enable()

    entries = debug_logger.get_recent_logs(count=10000)
    return DebugStatusResponse(
        enabled=debug_logger.enabled,
        log_file=str(debug_logger.log_file_path),
        entry_count=len(entries),
    )


@router.post("/debug/disable", response_model=DebugStatusResponse)
async def disable_debug_logging() -> DebugStatusResponse:
    """Disable debug logging."""
    debug_logger = get_debug_logger()
    debug_logger.disable()

    entries = debug_logger.get_recent_logs(count=10000)
    return DebugStatusResponse(
        enabled=debug_logger.enabled,
        log_file=str(debug_logger.log_file_path),
        entry_count=len(entries),
    )


@router.get("/debug/logs", response_model=DebugLogsResponse)
async def get_debug_logs(count: int = 100) -> DebugLogsResponse:
    """Get recent debug log entries.

    Args:
        count: Maximum number of entries to return (default 100)
    """
    debug_logger = get_debug_logger()
    raw_entries = debug_logger.get_recent_logs(count=count)

    entries = [
        DebugLogEntry(
            timestamp=e.get("timestamp", ""),
            level=e.get("level", "INFO"),
            category=e.get("category", "UNKNOWN"),
            message=e.get("message", ""),
            data=e.get("data"),
        )
        for e in raw_entries
    ]

    return DebugLogsResponse(
        entries=entries,
        total_count=len(entries),
    )


@router.delete("/debug/logs", response_model=ClearLogsResponse)
async def clear_debug_logs() -> ClearLogsResponse:
    """Clear all debug log entries."""
    debug_logger = get_debug_logger()
    count = debug_logger.clear()

    return ClearLogsResponse(
        cleared_count=count,
        message=f"Cleared {count} debug log entries",
    )


@router.post("/debug/log")
async def write_debug_log(request: DebugLogRequest) -> dict[str, str]:
    """Write a debug log entry from the frontend.

    This allows the frontend to write logs that will be included
    in the debug log file for troubleshooting.
    """
    debug_logger = get_debug_logger()
    debug_logger.log(
        category=request.category,
        message=request.message,
        data=request.data,
        level=request.level,
    )

    return {"status": "ok"}
