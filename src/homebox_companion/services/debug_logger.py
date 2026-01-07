"""Debug logging service.

Provides file-based debug logging that can be enabled/disabled at runtime.
Logs are written to the data directory for easy access from the container.

The debug mode automatically resets to disabled on container restart
since it's stored in memory only.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class DebugLogger:
    """Debug logger that writes to a file in the data directory.

    This is separate from the main application logger and is specifically
    for debugging issues that users encounter. It can be enabled/disabled
    at runtime and automatically resets on container restart.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._enabled = False  # In-memory only, resets on restart
        self._log_file = data_dir / "debug.log"
        self._max_entries = 1000  # Keep last N entries to prevent huge files

    @property
    def enabled(self) -> bool:
        """Check if debug logging is enabled."""
        return self._enabled

    @property
    def log_file_path(self) -> Path:
        """Get the path to the debug log file."""
        return self._log_file

    def enable(self) -> None:
        """Enable debug logging."""
        self._enabled = True
        self._write_entry("DEBUG_MODE", "Debug logging enabled")
        logger.info(f"Debug logging enabled, writing to {self._log_file}")

    def disable(self) -> None:
        """Disable debug logging."""
        if self._enabled:
            self._write_entry("DEBUG_MODE", "Debug logging disabled")
        self._enabled = False
        logger.info("Debug logging disabled")

    def log(
        self,
        category: str,
        message: str,
        data: dict[str, Any] | None = None,
        level: str = "INFO",
    ) -> None:
        """Write a debug log entry.

        Args:
            category: Log category (e.g., "API", "ENRICHMENT", "THEME")
            message: Human-readable message
            data: Optional structured data to include
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        if not self._enabled:
            return

        self._write_entry(category, message, data, level)

    def _write_entry(
        self,
        category: str,
        message: str,
        data: dict[str, Any] | None = None,
        level: str = "INFO",
    ) -> None:
        """Write an entry to the log file."""
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": level,
                "category": category,
                "message": message,
            }
            if data:
                entry["data"] = data

            # Ensure data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Append to log file
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            # Trim file if too large
            self._trim_log_file()

        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")

    def _trim_log_file(self) -> None:
        """Trim log file to keep only the last N entries."""
        try:
            if not self._log_file.exists():
                return

            lines = self._log_file.read_text(encoding="utf-8").strip().split("\n")
            if len(lines) > self._max_entries:
                # Keep last N entries
                trimmed = lines[-self._max_entries:]
                self._log_file.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to trim debug log: {e}")

    def get_recent_logs(self, count: int = 100) -> list[dict[str, Any]]:
        """Get the most recent log entries.

        Args:
            count: Number of entries to return

        Returns:
            List of log entries (newest first)
        """
        try:
            if not self._log_file.exists():
                return []

            lines = self._log_file.read_text(encoding="utf-8").strip().split("\n")
            entries = []
            for line in reversed(lines[-count:]):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return entries
        except Exception as e:
            logger.error(f"Failed to read debug logs: {e}")
            return []

    def clear(self) -> int:
        """Clear the debug log file.

        Returns:
            Number of entries that were cleared
        """
        try:
            if not self._log_file.exists():
                return 0

            lines = self._log_file.read_text(encoding="utf-8").strip().split("\n")
            count = len([l for l in lines if l.strip()])
            self._log_file.unlink()
            logger.info(f"Cleared {count} debug log entries")
            return count
        except Exception as e:
            logger.error(f"Failed to clear debug log: {e}")
            return 0


# Singleton instance (initialized lazily)
_debug_logger: DebugLogger | None = None


def get_debug_logger() -> DebugLogger:
    """Get the debug logger singleton."""
    global _debug_logger
    if _debug_logger is None:
        from homebox_companion.core.config import settings
        _debug_logger = DebugLogger(Path(settings.data_dir))
    return _debug_logger


def debug_log(
    category: str,
    message: str,
    data: dict[str, Any] | None = None,
    level: str = "INFO",
) -> None:
    """Convenience function to write a debug log entry."""
    get_debug_logger().log(category, message, data, level)
