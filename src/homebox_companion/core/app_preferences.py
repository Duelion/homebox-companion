"""Application preferences management.

This module provides storage and retrieval of application-level preferences
that can be customized by users through the Settings UI.

Settings are persisted to {data_dir}/app_preferences.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from homebox_companion.core.config import settings


def _get_prefs_path() -> Path:
    """Get the app preferences file path based on settings.data_dir."""
    return Path(settings.data_dir) / "app_preferences.json"


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

    # Enrichment settings
    enrichment_enabled: bool = Field(
        default=False,
        description="Enable AI-powered product specification enrichment",
    )
    enrichment_auto_enrich: bool = Field(
        default=False,
        description="Automatically enrich items after AI detection",
    )
    enrichment_cache_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Cache duration for enrichment results (hours)",
    )


def load_app_preferences() -> AppPreferences:
    """Load application preferences from file.

    Returns:
        AppPreferences instance with values from file, or defaults.
    """
    prefs_file = _get_prefs_path()
    if not prefs_file.exists():
        return AppPreferences()

    try:
        file_data = json.loads(prefs_file.read_text(encoding="utf-8"))
        return AppPreferences.model_validate(file_data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Invalid app preferences file, using defaults: {e}")
        return AppPreferences()


def save_app_preferences(prefs: AppPreferences) -> None:
    """Save application preferences to file.

    Args:
        prefs: The preferences to save.
    """
    prefs_file = _get_prefs_path()
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    data = prefs.model_dump()
    prefs_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"App preferences saved to {prefs_file}")


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
