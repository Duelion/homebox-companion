"""Logs API routes for debugging and reference."""

import os
from glob import glob

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class LogsResponse(BaseModel):
    """Response containing log entries."""

    logs: str
    filename: str | None
    total_lines: int
    truncated: bool


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    lines: int = Query(default=200, ge=1, le=2000, description="Number of lines to return"),
    date: str | None = Query(default=None, description="Log date in YYYY-MM-DD format"),
) -> LogsResponse:
    """Return recent application logs.

    Reads from the most recent log file (or a specific date if provided).
    Returns the last N lines for display in the Settings page.
    """
    logs_dir = "logs"

    # Find log files
    if date:
        log_pattern = os.path.join(logs_dir, f"homebox_companion_{date}.log")
        log_files = glob(log_pattern)
    else:
        log_pattern = os.path.join(logs_dir, "homebox_companion_*.log")
        log_files = sorted(glob(log_pattern), reverse=True)

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
            all_lines = f.readlines()

        total_lines = len(all_lines)
        truncated = total_lines > lines

        # Get last N lines
        recent_lines = all_lines[-lines:] if truncated else all_lines
        logs_content = "".join(recent_lines)

        return LogsResponse(
            logs=logs_content,
            filename=filename,
            total_lines=total_lines,
            truncated=truncated,
        )
    except Exception as e:
        return LogsResponse(
            logs=f"Error reading log file: {e}",
            filename=filename,
            total_lines=0,
            truncated=False,
        )

