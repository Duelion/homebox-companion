"""Logs API routes for debugging and reference."""

import os
import re
import secrets
from collections import deque
from glob import glob
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from homebox_companion.core.redaction import register_secrets

from ..dependencies import require_auth

router = APIRouter()

# Strict date format validation: YYYY-MM-DD
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Logs directory - resolved once at module load relative to project root
_LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))


async def require_log_access(
    request: Request,
    _identity: Annotated[object, Depends(require_auth)],
    operator_token: Annotated[str | None, Header(alias="X-Companion-Log-Token")] = None,
) -> None:
    """Require live Homebox authorization and a separate operator credential."""
    app_settings = request.app.state.settings
    configured = app_settings.log_access_token
    if configured is None:
        raise HTTPException(
            status_code=403,
            detail="Web log access is disabled. Configure HBC_LOG_ACCESS_TOKEN on the server and restart to enable it.",
        )
    register_secrets(configured, app_settings.homebox_api_key, app_settings.llm_api_key, app_settings.openai_api_key)
    if operator_token is None or not secrets.compare_digest(
        operator_token.encode("utf-8"), configured.get_secret_value().encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="A valid operator log access token is required.")


def _get_log_files(date: str | None) -> list[str]:
    """Get log files matching the optional date filter.

    Args:
        date: Optional date string in YYYY-MM-DD format (already validated).

    Returns:
        List of matching log file paths, sorted newest first.
    """
    if date:
        pattern = os.path.join(_LOGS_DIR, f"homebox_companion_{date}.log")
        return glob(pattern)
    else:
        pattern = os.path.join(_LOGS_DIR, "homebox_companion_*.log")
        return sorted(glob(pattern), reverse=True)


def _get_llm_debug_log_files(date: str | None) -> list[str]:
    """Get LLM debug log files matching the optional date filter.

    Args:
        date: Optional date string in YYYY-MM-DD format (already validated).

    Returns:
        List of matching log file paths, sorted newest first.
    """
    if date:
        pattern = os.path.join(_LOGS_DIR, f"llm_debug_{date}.log")
        return glob(pattern)
    else:
        pattern = os.path.join(_LOGS_DIR, "llm_debug_*.log")
        return sorted(glob(pattern), reverse=True)


def _validate_date_format(date: str | None) -> None:
    """Validate date format to prevent path traversal.

    Raises:
        HTTPException: If date format is invalid.
    """
    if date and not _DATE_PATTERN.match(date):
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD.",
        )


class LogsResponse(BaseModel):
    """Response containing log entries."""

    logs: str
    filename: str | None
    total_lines: int
    truncated: bool


@router.get("/logs", response_model=LogsResponse, dependencies=[Depends(require_log_access)])
async def get_logs(
    lines: int = Query(default=200, ge=1, le=2000, description="Number of lines to return"),
    date: str | None = Query(default=None, description="Log date in YYYY-MM-DD format"),
) -> LogsResponse:
    """Return recent application logs.

    Reads from the most recent log file (or a specific date if provided).
    Returns the last N lines for display in the Settings page.

    Requires valid Homebox authorization and the separate operator log token.
    """
    _validate_date_format(date)
    log_files = _get_log_files(date)

    if not log_files:
        return LogsResponse(
            logs="No log files found.",
            filename=None,
            total_lines=0,
            truncated=False,
        )

    # Read the most recent log file
    log_file = log_files[0]
    filename = os.path.basename(log_file)

    try:
        with open(log_file, encoding="utf-8") as f:
            # Use deque to keep only the last N lines in memory
            recent_lines: deque[str] = deque(maxlen=lines)
            total_lines = 0
            for line in f:
                recent_lines.append(line)
                total_lines += 1

        truncated = total_lines > lines
        logs_content = "".join(recent_lines)

        return LogsResponse(
            logs=logs_content,
            filename=filename,
            total_lines=total_lines,
            truncated=truncated,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to read the log file.",
        ) from e


@router.get("/logs/download", dependencies=[Depends(require_log_access)])
async def download_logs(
    date: str | None = Query(default=None, description="Log date in YYYY-MM-DD format"),
) -> FileResponse:
    """Download the full log file.

    Returns the complete log file for the most recent date (or a specific date if provided).

    Requires valid Homebox authorization and the separate operator log token.
    """
    _validate_date_format(date)
    log_files = _get_log_files(date)

    if not log_files:
        raise HTTPException(status_code=404, detail="No log files found")

    log_file = log_files[0]
    filename = os.path.basename(log_file)

    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(
        path=log_file,
        filename=filename,
        media_type="text/plain",
    )


@router.get("/logs/llm-debug", response_model=LogsResponse, dependencies=[Depends(require_log_access)])
async def get_llm_debug_logs(
    lines: int = Query(default=200, ge=1, le=2000, description="Number of lines to return"),
    date: str | None = Query(default=None, description="Log date in YYYY-MM-DD format"),
) -> LogsResponse:
    """Return recent LLM debug logs.

    Reads from the most recent LLM debug log file (or a specific date if provided).
    Returns the last N lines for display in the Settings page.

    Requires valid Homebox authorization and the separate operator log token.
    """
    _validate_date_format(date)
    log_files = _get_llm_debug_log_files(date)

    if not log_files:
        return LogsResponse(
            logs="No LLM debug log files found.",
            filename=None,
            total_lines=0,
            truncated=False,
        )

    # Read the most recent log file
    log_file = log_files[0]
    filename = os.path.basename(log_file)

    try:
        with open(log_file, encoding="utf-8") as f:
            # Use deque to keep only the last N lines in memory
            recent_lines: deque[str] = deque(maxlen=lines)
            total_lines = 0
            for line in f:
                recent_lines.append(line)
                total_lines += 1

        truncated = total_lines > lines
        logs_content = "".join(recent_lines)

        return LogsResponse(
            logs=logs_content,
            filename=filename,
            total_lines=total_lines,
            truncated=truncated,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to read the LLM debug log file.",
        ) from e


@router.get("/logs/llm-debug/download", dependencies=[Depends(require_log_access)])
async def download_llm_debug_logs(
    date: str | None = Query(default=None, description="Log date in YYYY-MM-DD format"),
) -> FileResponse:
    """Download the full LLM debug log file.

    Returns the complete LLM debug log file for the most recent date (or a specific date if provided).

    Requires valid Homebox authorization and the separate operator log token.
    """
    _validate_date_format(date)
    log_files = _get_llm_debug_log_files(date)

    if not log_files:
        raise HTTPException(status_code=404, detail="No LLM debug log files found")

    log_file = log_files[0]
    filename = os.path.basename(log_file)

    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="LLM debug log file not found")

    return FileResponse(
        path=log_file,
        filename=filename,
        media_type="text/plain",
    )
