"""Field preferences for AI output customization.

This module provides storage and retrieval of per-field custom instructions
that modify how the AI generates item data.

Two-tier preference model:
1. Defaults = hardcoded values + environment variables (immutable after init)
2. User overrides = settings page config (stored in JSON, can be reset)

The defaults are resolved once at import time and cached. User overrides from
the settings UI are stored in a sparse JSON file and overlaid on top.

Settings are persisted to {data_dir}/field_preferences.json
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from homebox_companion.core.config import settings


def _get_prefs_path() -> Path:
    """Get the field preferences file path based on settings.data_dir."""
    return Path(settings.data_dir) / "field_preferences.json"


class FieldPreferences(BaseSettings):
    """Field preferences with built-in defaults and env var support.

    Defaults are resolved once at import time (hardcoded → env vars).
    User overrides from settings UI are stored in JSON and overlaid on top.

    All fields have hardcoded defaults. Environment variables (HBC_AI_*)
    automatically override these via pydantic-settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="HBC_AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Language for AI output - env var: HBC_AI_OUTPUT_LANGUAGE
    output_language: str = "English"

    # Label ID to auto-apply - env var: HBC_AI_DEFAULT_LABEL_ID
    default_label_id: str | None = None

    # Item naming instructions - env var: HBC_AI_NAME
    name: str = "[Type] [Brand] [Model] [Specs], Title Case, item type first for searchability"

    # Naming examples - env var: HBC_AI_NAMING_EXAMPLES
    naming_examples: str = (
        '"Ball Bearing 6900-2RS 10x22x6mm", '
        '"Acrylic Paint Vallejo Game Color Bone White", '
        '"LED Strip COB Green 5V 1M"'
    )

    # Description instructions - env var: HBC_AI_DESCRIPTION
    description: str = (
        "Product features and specifications - what IS this item. "
        "Max 1000 chars, NEVER mention quantity"
    )

    # Quantity counting instructions - env var: HBC_AI_QUANTITY
    quantity: str = "Count identical items together, separate different variants"

    # Manufacturer extraction - env var: HBC_AI_MANUFACTURER
    manufacturer: str = "Only when brand/logo is VISIBLE. Include recognizable brands only."

    # Model number extraction - env var: HBC_AI_MODEL_NUMBER
    model_number: str = "Only when model/part number TEXT is clearly visible on label"

    # Serial number extraction - env var: HBC_AI_SERIAL_NUMBER
    serial_number: str = "Only when S/N text is visible on sticker/label/engraving"

    # Purchase price extraction - env var: HBC_AI_PURCHASE_PRICE
    purchase_price: str = "Only from visible price tag/receipt. Just the number."

    # Purchase from extraction - env var: HBC_AI_PURCHASE_FROM
    purchase_from: str = "Only from visible packaging/receipt or user-specified"

    # Notes instructions - env var: HBC_AI_NOTES
    notes: str = (
        "Only for visible issues: damage, missing parts, safety hazards. "
        "Also note if sealed/new-in-box. Leave null for normal items."
    )

    def get_effective_customizations(self) -> dict[str, str]:
        """Get customizations as dict for prompt integration.

        Returns dict with all prompt fields (excludes metadata like
        output_language and default_label_id).

        Returns:
            Dict mapping field names to their effective instructions.
        """
        return self.model_dump(exclude={"output_language", "default_label_id"})


@lru_cache(maxsize=1)
def get_defaults() -> FieldPreferences:
    """Get the immutable defaults (hardcoded + env vars, resolved once).

    This is cached to avoid re-reading environment variables on every call.
    The defaults are effectively immutable after application startup.

    Returns:
        FieldPreferences with env vars applied over hardcoded defaults.
    """
    return FieldPreferences()


def load_field_preferences() -> FieldPreferences:
    """Load preferences: defaults + user overrides from file.

    Priority (highest first):
    1. File-based user overrides ({data_dir}/field_preferences.json)
    2. Defaults (hardcoded + environment variables)

    Returns:
        FieldPreferences instance with merged values.
    """
    defaults = get_defaults()
    prefs_file = _get_prefs_path()

    if not prefs_file.exists():
        return defaults

    try:
        file_data = json.loads(prefs_file.read_text(encoding="utf-8"))
        # User overrides on top of defaults
        merged = defaults.model_dump() | {k: v for k, v in file_data.items() if v is not None}
        return FieldPreferences.model_validate(merged)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Invalid field preferences config file, using defaults: {e}")
        return defaults


def save_field_preferences(preferences: FieldPreferences) -> None:
    """Save only user overrides (fields that differ from defaults).

    This creates a sparse JSON file containing only customized fields,
    making it clear what the user actually changed.

    Args:
        preferences: The preferences to save.
    """
    defaults = get_defaults()
    overrides = {}

    for field in FieldPreferences.model_fields:
        user_val = getattr(preferences, field)
        default_val = getattr(defaults, field)
        if user_val != default_val:
            overrides[field] = user_val

    prefs_file = _get_prefs_path()
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    prefs_file.write_text(json.dumps(overrides, indent=2), encoding="utf-8")


def reset_field_preferences() -> FieldPreferences:
    """Reset to defaults by deleting the overrides file.

    Returns:
        FieldPreferences with defaults (user overrides cleared).
    """
    prefs_file = _get_prefs_path()
    if prefs_file.exists():
        prefs_file.unlink()
    return get_defaults()
