"""Field preferences for AI output customization.

This module provides storage and retrieval of per-field custom instructions
that modify how the AI generates item data.

Two-tier preference model:
1. Defaults = hardcoded values + environment variables (immutable after init)
2. User overrides = settings page config (stored in config/field_preferences.json, can be reset)

The defaults are resolved once at import time and cached. User overrides from
the settings UI are stored as a sparse mapping in config/field_preferences.json and overlaid on top.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Logical location; the Docker image links this file into its data volume.
CONFIG_DIR = Path("config")
PREFERENCES_FILE = CONFIG_DIR / "field_preferences.json"
_preferences_lock = threading.RLock()


class FieldPreferencesLoadError(RuntimeError):
    """Saved preferences cannot be read safely; the original file is preserved."""


class FieldPreferences(BaseSettings):
    """Field preferences with built-in defaults and env var support.

    Defaults are resolved once at import time (hardcoded → env vars).
    User overrides from settings UI are stored in config/field_preferences.json and overlaid on top.

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

    # Tag ID to auto-apply to all detected items
    # Env var: HBC_AI_DEFAULT_TAG_ID
    # Backward compatibility: Also accepts HBC_AI_DEFAULT_LABEL_ID (pre-v0.23 name)
    default_tag_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "default_tag_id", "default_label_id", "HBC_AI_DEFAULT_TAG_ID", "HBC_AI_DEFAULT_LABEL_ID"
        ),
    )

    # Item naming instructions - env var: HBC_AI_NAME
    name: str = "[Type] [Brand] [Model] [Specs], Title Case, item type first for searchability"

    # Naming examples - env var: HBC_AI_NAMING_EXAMPLES
    naming_examples: str = (
        '"Ball Bearing 6900-2RS 10x22x6mm", "Acrylic Paint Vallejo Game Color Bone White", "LED Strip COB Green 5V 1M"'
    )

    # Description instructions - env var: HBC_AI_DESCRIPTION
    description: str = "Product features and specifications - what IS this item. Max 1000 chars, NEVER mention quantity"

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

    @property
    def using_legacy_label_env(self) -> bool:
        """Check if the deprecated HBC_AI_DEFAULT_LABEL_ID env var is being used.

        Returns True if default_tag_id has a value AND the legacy env var is set.
        """
        import os

        return self.default_tag_id is not None and bool(os.environ.get("HBC_AI_DEFAULT_LABEL_ID"))

    def get_effective_customizations(self) -> dict[str, str]:
        """Get customizations as dict for prompt integration.

        Returns dict with all prompt fields (excludes metadata like
        output_language and default_tag_id).

        Returns:
            Dict mapping field names to their effective instructions.
        """
        return self.model_dump(exclude={"output_language", "default_tag_id"})


@lru_cache(maxsize=1)
def get_defaults() -> FieldPreferences:
    """Get the immutable defaults (hardcoded + env vars, resolved once).

    This is cached to avoid re-reading environment variables on every call.
    The defaults are effectively immutable after application startup.

    Returns:
        FieldPreferences with env vars applied over hardcoded defaults.
    """
    return FieldPreferences()


def normalize_field_overrides(value: object) -> dict[str, str]:
    """Validate sparse saved values, canonicalizing the pre-v0.23 tag alias.

    Null means no override. Validation does not resolve environment defaults.
    """
    if not isinstance(value, dict):
        raise ValueError("Field preferences must be a mapping")
    canonical = dict(value)
    if "default_label_id" in canonical:
        canonical.setdefault("default_tag_id", canonical["default_label_id"])
        del canonical["default_label_id"]
    result = {}
    for key, item in canonical.items():
        if key not in FieldPreferences.model_fields or (item is not None and not isinstance(item, str)):
            raise ValueError("Invalid field preference")
        if item is not None:
            result[key] = item
    return result


def _load_overrides() -> dict[str, str]:
    """Read JSON without rewriting it or exposing parser diagnostics."""
    with _preferences_lock:
        try:
            return normalize_field_overrides(json.loads(PREFERENCES_FILE.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return {}
        except OSError, ValueError:
            pass
        raise FieldPreferencesLoadError("Failed to load field preferences; original file was preserved")


def load_field_preferences() -> FieldPreferences:
    """Resolve hardcoded defaults, process environment and saved JSON overrides."""
    return FieldPreferences.model_validate(get_defaults().model_dump() | _load_overrides())


def save_field_preferences(preferences: FieldPreferences) -> None:
    """Atomically save only non-null differences from current defaults."""
    defaults = get_defaults()
    overrides = normalize_field_overrides(
        {
            field: value
            for field in FieldPreferences.model_fields
            if (value := getattr(preferences, field)) is not None and value != getattr(defaults, field)
        }
    )
    with _preferences_lock:
        destination = PREFERENCES_FILE.resolve(strict=False)
        directory = destination.parent
        directory.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=directory, prefix=f".{PREFERENCES_FILE.name}.", suffix=".tmp")
        temporary_path = Path(name)
        try:
            temporary_file = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = -1
            with temporary_file:
                json.dump(overrides, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, destination)
        except BaseException:
            if descriptor != -1:
                with suppress(OSError):
                    os.close(descriptor)
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
            raise


def load_user_overrides() -> dict[str, str | None]:
    """Return all UI fields, with None wherever no override was saved."""
    return dict.fromkeys(FieldPreferences.model_fields) | _load_overrides()


def reset_field_preferences() -> FieldPreferences:
    """Remove JSON overrides and return the current environment defaults."""
    with _preferences_lock:
        PREFERENCES_FILE.resolve(strict=False).unlink(missing_ok=True)
    return get_defaults()
