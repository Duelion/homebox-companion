"""Application preferences management.

This module provides storage and retrieval of application-level preferences
that can be customized by users through the Settings UI.

Settings are persisted to config/app_preferences.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

# Default storage location
CONFIG_DIR = Path("config")
APP_PREFS_FILE = CONFIG_DIR / "app_preferences.json"


class AppPreferences(BaseModel):
    """Application preferences that can be customized via UI.

    These preferences allow users to override environment-variable defaults
    without needing to modify their deployment configuration.
    """

    # Connection settings
    homebox_url_override: str | None = Field(
        default=None,
        description="Override for HOMEBOX_URL environment variable",
    )
    image_quality_override: str | None = Field(
        default=None,
        description="Override for HBC_IMAGE_QUALITY (low, medium, high)",
    )

    # Behavior settings
    duplicate_detection_enabled: bool = Field(
        default=True,
        description="Enable duplicate detection by serial number",
    )


def load_app_preferences() -> AppPreferences:
    """Load application preferences from file.

    Returns:
        AppPreferences instance with values from file, or defaults.
    """
    if not APP_PREFS_FILE.exists():
        return AppPreferences()

    try:
        file_data = json.loads(APP_PREFS_FILE.read_text(encoding="utf-8"))
        return AppPreferences.model_validate(file_data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Invalid app preferences file, using defaults: {e}")
        return AppPreferences()


def save_app_preferences(prefs: AppPreferences) -> None:
    """Save application preferences to file.

    Args:
        prefs: The preferences to save.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = prefs.model_dump()
    APP_PREFS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("App preferences saved")


def get_effective_homebox_url(prefs: AppPreferences) -> str:
    """Get the effective Homebox URL, considering override.

    Args:
        prefs: The app preferences.

    Returns:
        The Homebox URL to use (override or from settings).
    """
    from homebox_companion.core.config import settings

    if prefs.homebox_url_override:
        return prefs.homebox_url_override
    return settings.api_url


def get_effective_image_quality(prefs: AppPreferences) -> str:
    """Get the effective image quality, considering override.

    Args:
        prefs: The app preferences.

    Returns:
        The image quality to use (override or from settings).
    """
    from homebox_companion.core.config import settings

    if prefs.image_quality_override:
        return prefs.image_quality_override
    return settings.image_quality
