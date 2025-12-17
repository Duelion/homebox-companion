"""Field preferences for AI output customization.

This module provides storage and retrieval of per-field custom instructions
that modify how the AI generates item data.

Preferences are loaded with the following priority (highest first):
1. File-based preferences (config/field_preferences.json) - set via UI
2. Environment variables (HBC_AI_*) - set via docker-compose or .env
3. Hardcoded defaults (defined in FieldPreferencesDefaults)

This allows Docker users to set persistent defaults via env vars while
still being able to override them temporarily via the UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default storage location
CONFIG_DIR = Path("config")
PREFERENCES_FILE = CONFIG_DIR / "field_preferences.json"


class FieldPreferencesDefaults(BaseSettings):
    """Default values for AI field preferences, loaded from env vars.

    Uses pydantic_settings to automatically load from HBC_AI_* environment
    variables. Each field has a hardcoded default that is used when no
    env var is set.

    This is the single source of truth for all default values.
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
    name: str = (
        "[Type] [Brand] [Model] [Specs], Title Case, "
        "item type first for searchability"
    )

    # Naming examples - env var: HBC_AI_NAMING_EXAMPLES
    naming_examples: str = (
        '"Ball Bearing 6900-2RS 10x22x6mm", '
        '"Acrylic Paint Vallejo Game Color Bone White", '
        '"LED Strip COB Green 5V 1M"'
    )

    # Description instructions - env var: HBC_AI_DESCRIPTION
    description: str = "Condition/attributes only, max 1000 chars, NEVER mention quantity"

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
        'ONLY for defects/damage/warnings - leave null for normal items. '
        'GOOD: "Cracked lens", "Missing screws" | BAD: "Appears new", "Made in China"'
    )


class FieldPreferences(BaseModel):
    """User-defined instructions for each AI output field.

    Each field accepts an optional string with custom instructions that
    will be injected into AI prompts. None values mean "use default".

    This model is used for file-based storage (config/field_preferences.json)
    where users can override the defaults via the UI.
    """

    output_language: str | None = None
    default_label_id: str | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: str | None = None
    purchase_from: str | None = None
    notes: str | None = None
    naming_examples: str | None = None

    def has_any_preferences(self) -> bool:
        """Check if any field has a non-empty preference set."""
        return any(
            getattr(self, field) and getattr(self, field).strip()
            for field in self.__class__.model_fields
        )

    def to_customizations_dict(self) -> dict[str, str]:
        """Convert to dict for prompt integration.

        Returns dict with keys used by prompt builders:
        name, description, quantity, manufacturer, model_number, serial_number,
        purchase_price, purchase_from, notes, naming_examples.

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
                result[field] = value.strip()
        return result

    def get_output_language(self) -> str:
        """Get the configured output language.

        Returns user's custom language if set, otherwise the effective default
        (from env var or hardcoded "English").

        Returns:
            The output language string.
        """
        if self.output_language and self.output_language.strip():
            return self.output_language.strip()
        # Use effective default (env var or hardcoded)
        return get_defaults().output_language

    def to_prompt_dict(self) -> dict[str, str]:
        """Alias for to_customizations_dict() for backwards compatibility."""
        return self.to_customizations_dict()

    def get_effective_customizations(self) -> dict[str, str]:
        """Get customizations merged with effective defaults.

        Returns a dict where each field has a value - either the user's
        custom value if set, or the effective default (from env var or
        hardcoded fallback).

        This ensures prompt builders always receive values and don't need
        their own fallback defaults.

        Returns:
            Dict mapping field names to their effective instructions.
        """
        defaults = get_defaults()
        result = {}

        # Fields that are prompt customizations (not metadata like output_language)
        prompt_fields = [
            "name",
            "description",
            "quantity",
            "manufacturer",
            "model_number",
            "serial_number",
            "purchase_price",
            "purchase_from",
            "notes",
            "naming_examples",
        ]

        for field in prompt_fields:
            user_value = getattr(self, field)
            if user_value and user_value.strip():
                # User has set a custom value
                result[field] = user_value.strip()
            else:
                # Use effective default (env var or hardcoded)
                result[field] = getattr(defaults, field)

        return result


def get_defaults() -> FieldPreferencesDefaults:
    """Get the effective defaults (env vars with hardcoded fallbacks).

    Returns a fresh instance each time to pick up any env var changes.

    Returns:
        FieldPreferencesDefaults with env vars applied over hardcoded defaults.
    """
    return FieldPreferencesDefaults()


def load_field_preferences() -> FieldPreferences:
    """Load field preferences with env vars as defaults, file as override.

    Priority (highest first):
    1. File-based preferences (config/field_preferences.json)
    2. Environment variables (HBC_AI_*)
    3. Hardcoded defaults

    Returns:
        FieldPreferences instance with merged values.
    """
    # Get defaults (env vars override hardcoded)
    defaults = get_defaults()

    # Load file preferences if they exist
    file_prefs: dict[str, Any] = {}
    if PREFERENCES_FILE.exists():
        try:
            with open(PREFERENCES_FILE, encoding="utf-8") as f:
                file_prefs = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # Invalid file - ignore
            pass

    # Start with defaults, then overlay file preferences
    merged: dict[str, Any] = {}
    for field in FieldPreferences.model_fields:
        # File value takes precedence if it's not None
        file_value = file_prefs.get(field)
        if file_value is not None:
            merged[field] = file_value
        else:
            # Use env/default value
            default_value = getattr(defaults, field)
            # For FieldPreferences, we store None if it matches the hardcoded default
            # This allows "reset" to properly restore env var defaults
            merged[field] = default_value if field == "default_label_id" else None

    # If file has values, use them (they override defaults)
    for key, value in file_prefs.items():
        if value is not None and key in FieldPreferences.model_fields:
            merged[key] = value

    return FieldPreferences.model_validate(merged)


def save_field_preferences(preferences: FieldPreferences) -> None:
    """Save field preferences to storage.

    Args:
        preferences: The preferences to save.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(preferences.model_dump(), f, indent=2)


def reset_field_preferences() -> FieldPreferences:
    """Reset field preferences to defaults.

    This removes the config file, clearing all custom preferences.
    Returns all fields as None, allowing defaults from env vars or hardcoded
    fallbacks to be used during prompt generation.

    Returns:
        FieldPreferences instance with all fields set to None.
    """
    if PREFERENCES_FILE.exists():
        PREFERENCES_FILE.unlink()

    # Return empty preferences - all None means "use defaults"
    # Defaults will be applied during prompt generation, not stored here
    return FieldPreferences(
        output_language=None,
        default_label_id=None,
        name=None,
        description=None,
        quantity=None,
        manufacturer=None,
        model_number=None,
        serial_number=None,
        purchase_price=None,
        purchase_from=None,
        notes=None,
        naming_examples=None,
    )


def get_preferences_as_dict() -> dict[str, Any]:
    """Get field preferences as a dictionary.

    Returns:
        Dict representation of current preferences.
    """
    return load_field_preferences().model_dump()
