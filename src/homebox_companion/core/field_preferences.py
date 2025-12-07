"""Field preferences for AI output customization.

This module provides storage and retrieval of per-field custom instructions
that modify how the AI generates item data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

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


def load_field_preferences() -> FieldPreferences:
    """Load field preferences from storage.

    Returns:
        FieldPreferences instance with saved values, or defaults if not found.
    """
    if not PREFERENCES_FILE.exists():
        return FieldPreferences()

    try:
        with open(PREFERENCES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return FieldPreferences.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        # Invalid file - return defaults
        return FieldPreferences()


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
    """Reset field preferences to defaults.

    Returns:
        Fresh FieldPreferences instance with all defaults.
    """
    default_prefs = FieldPreferences()

    # Save the defaults to file
    save_field_preferences(default_prefs)

    return default_prefs


def get_preferences_as_dict() -> dict[str, Any]:
    """Get field preferences as a dictionary.

    Returns:
        Dict representation of current preferences.
    """
    return load_field_preferences().model_dump()
