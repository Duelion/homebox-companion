"""Field preferences for AI output customization.

This module provides storage and retrieval of per-field custom instructions
that modify how the AI generates item data.

Preferences are loaded with the following priority (highest first):
1. File-based preferences (config/field_preferences.json) - set via UI
2. Environment variables (HBC_AI_*) - set via docker-compose or .env
3. Default values (None/empty)

This allows Docker users to set persistent defaults via env vars while
still being able to override them temporarily via the UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .config import settings

# Default storage location
CONFIG_DIR = Path("config")
PREFERENCES_FILE = CONFIG_DIR / "field_preferences.json"


class FieldPreferences(BaseModel):
    """User-defined instructions for each AI output field.

    Each field accepts an optional string with custom instructions that
    will be injected into AI prompts. Empty/None values use default behavior.

    Attributes:
        output_language: Language for AI output (default: English). Note that
            custom field instructions should still be written in English.
        default_label_id: ID of a label to automatically add to all items
            created via Homebox Companion. This is applied on the frontend,
            not sent to the LLM.
        name: Instructions for item naming (e.g., "Always put brand first")
        description: Instructions for descriptions (e.g., "Focus on condition")
        quantity: Instructions for counting (e.g., "Count each variant separately")
        manufacturer: Instructions for manufacturer extraction
        model_number: Instructions for model number extraction
        serial_number: Instructions for serial number extraction
        purchase_price: Instructions for price extraction
        purchase_from: Instructions for retailer extraction
        notes: Instructions for notes (e.g., "Include storage recommendations")
    """

    output_language: str | None = None  # Default is English (handled in prompts)
    default_label_id: str | None = None  # Auto-tag items with this label
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: str | None = None
    purchase_from: str | None = None
    notes: str | None = None
    naming_examples: str | None = None  # Custom examples for item naming

    def has_any_preferences(self) -> bool:
        """Check if any field has a non-empty preference set."""
        return any(
            getattr(self, field) and getattr(self, field).strip()
            for field in self.__class__.model_fields
        )

    def to_customizations_dict(self) -> dict[str, str]:
        """Convert to dict with keys matching FIELD_DEFAULTS for prompt integration.

        Returns dict with keys that match the FIELD_DEFAULTS keys in ai/prompts.py:
        name, description, quantity, manufacturer, model_number, serial_number,
        purchase_price, purchase_from, notes.

        Only non-empty values are included. output_language is excluded as it's
        handled separately in prompt building.

        Returns:
            Dict mapping field names to their custom instructions.
        """
        result = {}
        # Exclude fields that aren't LLM prompt customizations
        excluded_fields = {"output_language", "default_label_id"}
        for field in self.__class__.model_fields:
            if field in excluded_fields:
                continue
            value = getattr(self, field)
            if value and value.strip():
                # Keep snake_case to match FIELD_DEFAULTS keys
                result[field] = value.strip()
        return result

    def get_output_language(self) -> str:
        """Get the configured output language, defaulting to English.

        Returns:
            The output language string.
        """
        if self.output_language and self.output_language.strip():
            return self.output_language.strip()
        return "English"

    # Keep old method for backwards compatibility but mark it as the new one
    def to_prompt_dict(self) -> dict[str, str]:
        """Alias for to_customizations_dict() for backwards compatibility."""
        return self.to_customizations_dict()


def _get_env_defaults() -> dict[str, Any]:
    """Get field preferences from environment variables.

    Returns:
        Dict of non-None env var values for field preferences.
    """
    env_prefs = {}
    # Map env var settings to field preference keys
    env_mapping = {
        "ai_output_language": "output_language",
        "ai_default_label_id": "default_label_id",
        "ai_name": "name",
        "ai_description": "description",
        "ai_quantity": "quantity",
        "ai_manufacturer": "manufacturer",
        "ai_model_number": "model_number",
        "ai_serial_number": "serial_number",
        "ai_purchase_price": "purchase_price",
        "ai_purchase_from": "purchase_from",
        "ai_notes": "notes",
        "ai_naming_examples": "naming_examples",
    }

    for env_key, pref_key in env_mapping.items():
        value = getattr(settings, env_key, None)
        if value is not None:
            env_prefs[pref_key] = value

    return env_prefs


def load_field_preferences() -> FieldPreferences:
    """Load field preferences with env vars as defaults, file as override.

    Priority (highest first):
    1. File-based preferences (config/field_preferences.json)
    2. Environment variables (HBC_AI_*)
    3. Default values (None)

    Returns:
        FieldPreferences instance with merged values.
    """
    # Start with env var defaults
    env_defaults = _get_env_defaults()

    # Load file preferences if they exist
    file_prefs: dict[str, Any] = {}
    if PREFERENCES_FILE.exists():
        try:
            with open(PREFERENCES_FILE, encoding="utf-8") as f:
                file_prefs = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # Invalid file - ignore
            pass

    # Merge: env defaults first, then file overrides (file wins)
    # Only override with file values that are not None/empty
    merged = {**env_defaults}
    for key, value in file_prefs.items():
        if value is not None:
            merged[key] = value

    return FieldPreferences.model_validate(merged)


def save_field_preferences(preferences: FieldPreferences) -> None:
    """Save field preferences to storage.

    Args:
        preferences: The preferences to save.
    """
    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(preferences.model_dump(), f, indent=2)


def reset_field_preferences() -> FieldPreferences:
    """Reset field preferences to env var defaults (or empty if no env vars).

    This removes the config file, allowing env var defaults to take effect.

    Returns:
        FieldPreferences instance with env var defaults.
    """
    # Remove the config file to reset to env var defaults
    if PREFERENCES_FILE.exists():
        PREFERENCES_FILE.unlink()

    # Return preferences with env var defaults
    env_defaults = _get_env_defaults()
    return FieldPreferences.model_validate(env_defaults)


def get_preferences_as_dict() -> dict[str, Any]:
    """Get field preferences as a dictionary.

    Returns:
        Dict representation of current preferences.
    """
    return load_field_preferences().model_dump()
