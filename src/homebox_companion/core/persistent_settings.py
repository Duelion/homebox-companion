"""Unified settings management with YAML persistence.

Consolidates LLM profiles and field preferences into a single settings.yaml file.
Bootstraps from environment variables on first run, then uses the file exclusively.

Settings flow:
1. First boot: env vars → create settings.yaml
2. Runtime: load from settings.yaml
3. Settings UI: modify and save to settings.yaml
"""

from __future__ import annotations

import re
import threading
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Self

import yaml
from loguru import logger
from pydantic import BaseModel, Field, SecretStr, model_validator

from .field_preferences import FieldPreferences

# Data directory for persistent storage (mounted volume in Docker).
# This is relative to the working directory, which should be the project root
# when running via `uv run` or from Docker (where WORKDIR is set appropriately).
DATA_DIR = Path("data")
SETTINGS_FILE = DATA_DIR / "settings.yaml"

# Current schema version for migrations
CURRENT_VERSION = 2


class ProfileStatus(StrEnum):
    """Status of an LLM profile.

    PRIMARY: Currently in use for all AI operations
    FALLBACK: Used when primary profile fails
    OFF: Available but not used
    """

    PRIMARY = "primary"
    FALLBACK = "fallback"
    OFF = "off"


class ModelProfile(BaseModel):
    """Configuration for a single LLM provider/model.

    Attributes:
        name: User-defined identifier for this profile
        model: LiteLLM model string (e.g., 'gpt-4o', 'ollama/mistral')
        api_key: Optional API key (stored securely, never sent to frontend)
        api_base: Optional custom API base URL (for Ollama, Azure, etc.)
        status: Whether this profile is active, fallback, or disabled
    """

    name: str
    model: str
    api_key: SecretStr | None = None
    api_base: str | None = None
    status: ProfileStatus = ProfileStatus.OFF


class CustomFieldDefinition(BaseModel):
    """A user-defined Homebox custom field with AI instruction.

    Attributes:
        name: Field name as it appears in Homebox (e.g., "Storage Location")
        ai_instruction: AI prompt instruction for this field
    """

    name: str
    ai_instruction: str

    @property
    def field_key(self) -> str:
        """Python-safe key derived from the display name.

        Strips non-alphanumeric characters, collapses underscores, and
        ensures the result is a valid Python identifier.

        Examples:
            "Storage Location" → "storage_location"
            "Price ($)"        → "price"
            "A/B Test"         → "a_b_test"
        """
        key = re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")
        return key if key else "field"

    @property
    def prompt_key(self) -> str:
        """CamelCase key for AI prompts and JSON schema aliases.

        Uses Pydantic's built-in ``to_camel`` to match the casing convention
        of default fields (e.g. modelNumber, serialNumber) so customs and
        defaults are consistent in the prompt.

        Examples:
            "Main Material"                → "mainMaterial"
            "Can it be used to boil water?" → "canItBeUsedToBoilWater"
            "Price ($)"                    → "price"
        """
        from pydantic.alias_generators import to_camel

        return to_camel(self.field_key)


class PersistentSettings(BaseModel):
    """Unified application settings stored in YAML.

    Note: This is distinct from core.config.Settings which handles env vars.
    This class manages user-configurable settings persisted to settings.yaml.

    Contains all persistent configuration:
    - LLM profiles (multi-provider support)
    - Field preferences (AI output customization)
    - Custom fields (user-defined Homebox fields with AI instructions)

    Attributes:
        version: Schema version for migrations
        llm_profiles: List of configured LLM providers
        field_preferences: AI output field customizations
        custom_fields: User-defined Homebox custom fields
    """

    version: int = CURRENT_VERSION
    llm_profiles: list[ModelProfile] = Field(default_factory=list)
    field_preferences: FieldPreferences = Field(default_factory=FieldPreferences)
    custom_fields: list[CustomFieldDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_profile_constraints(self) -> Self:
        """Ensure exactly one ACTIVE and at most one FALLBACK profile."""
        if not self.llm_profiles:
            return self

        actives = [p for p in self.llm_profiles if p.status == ProfileStatus.PRIMARY]
        fallbacks = [p for p in self.llm_profiles if p.status == ProfileStatus.FALLBACK]

        if len(actives) != 1:
            raise ValueError(f"Exactly one profile must be PRIMARY, found {len(actives)}")
        if len(fallbacks) > 1:
            raise ValueError(f"At most one profile can be FALLBACK, found {len(fallbacks)}")

        return self


def _settings_to_yaml_dict(settings: PersistentSettings) -> dict:
    """Convert PersistentSettings to a YAML-friendly dict."""
    profiles = []
    for p in settings.llm_profiles:
        profile_dict = {
            "name": p.name,
            "model": p.model,
            "status": p.status.value,
        }
        if p.api_key:
            profile_dict["api_key"] = p.api_key.get_secret_value()
        if p.api_base:
            profile_dict["api_base"] = p.api_base
        profiles.append(profile_dict)

    return {
        "version": settings.version,
        "llm_profiles": profiles,
        "field_preferences": settings.field_preferences.model_dump(),
        "custom_fields": [{"name": cf.name, "ai_instruction": cf.ai_instruction} for cf in settings.custom_fields],
    }


def _yaml_dict_to_settings(data: dict) -> PersistentSettings:
    """Convert YAML dict to PersistentSettings, handling SecretStr conversion."""
    profiles = []
    for p in data.get("llm_profiles", []):
        profiles.append(
            ModelProfile(
                name=p["name"],
                model=p["model"],
                api_key=SecretStr(p["api_key"]) if p.get("api_key") else None,
                api_base=p.get("api_base"),
                status=ProfileStatus(p.get("status", "off")),
            )
        )

    field_prefs = data.get("field_preferences", {})

    custom_fields = [
        CustomFieldDefinition(name=cf["name"], ai_instruction=cf["ai_instruction"])
        for cf in data.get("custom_fields", [])
    ]

    return PersistentSettings(
        version=data.get("version", CURRENT_VERSION),
        llm_profiles=profiles,
        field_preferences=FieldPreferences.model_validate(field_prefs),
        custom_fields=custom_fields,
    )


def bootstrap_from_env() -> PersistentSettings:
    """Create initial settings from environment variables.

    Called on first boot when no settings.yaml exists.
    Reads HBC_LLM_MODEL and HBC_LLM_API_KEY to create a default profile.
    """
    from .config import settings as env_settings

    profiles = []

    # Create default profile from env vars if configured
    model = env_settings.effective_llm_model
    api_key = env_settings.effective_llm_api_key
    api_base = env_settings.llm_api_base

    if model:
        profiles.append(
            ModelProfile(
                name="default",
                model=model,
                api_key=SecretStr(api_key) if api_key else None,
                api_base=api_base,
                status=ProfileStatus.PRIMARY,
            )
        )
        logger.info(f"Bootstrapped default LLM profile from env: {model}")

    # Migrate existing field_preferences.json if it exists
    from .field_preferences import PREFERENCES_FILE, load_field_preferences

    field_prefs = FieldPreferences()
    if PREFERENCES_FILE.exists():
        field_prefs = load_field_preferences()
        logger.info("Migrated existing field_preferences.json to settings.yaml")

    return PersistentSettings(
        version=CURRENT_VERSION,
        llm_profiles=profiles,
        field_preferences=field_prefs,
    )


def migrate_settings(data: dict) -> dict:
    """Apply migrations to bring settings to current version.

    Args:
        data: Raw YAML data dict

    Returns:
        Migrated data dict at CURRENT_VERSION
    """
    version = data.get("version", 1)

    if version < CURRENT_VERSION:
        logger.info(f"Migrating settings from v{version} to v{CURRENT_VERSION}")

    # v1 → v2: Add custom_fields list
    if version < 2:
        data.setdefault("custom_fields", [])
        version = 2

    data["version"] = CURRENT_VERSION
    return data


def load_settings() -> PersistentSettings:
    """Load settings from YAML file, bootstrapping if needed.

    Returns:
        PersistentSettings instance with all configuration
    """
    if not SETTINGS_FILE.exists():
        logger.info("No settings.yaml found, bootstrapping from environment")
        settings = bootstrap_from_env()
        save_settings(settings)
        return settings

    try:
        raw_data = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8"))
        if raw_data is None:
            raw_data = {}

        # Apply any needed migrations
        migrated_data = migrate_settings(raw_data)

        settings = _yaml_dict_to_settings(migrated_data)

        # Save if migration occurred
        if raw_data.get("version", 1) < CURRENT_VERSION:
            save_settings(settings)

        return settings

    except Exception as e:
        logger.error(f"Failed to load settings.yaml: {e}")
        logger.warning("Using bootstrapped settings as fallback")
        return bootstrap_from_env()


# Lock for thread-safe settings file access
_settings_lock = threading.Lock()


def save_settings(settings: PersistentSettings) -> None:
    """Save settings to YAML file.

    Thread-safe with file locking to prevent race conditions.
    Automatically clears the settings cache to ensure fresh data on next access.

    Args:
        settings: PersistentSettings instance to persist
    """
    with _settings_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        yaml_dict = _settings_to_yaml_dict(settings)

        # Use default_flow_style=False for readable multi-line output
        yaml_content = yaml.dump(yaml_dict, default_flow_style=False, allow_unicode=True)

        SETTINGS_FILE.write_text(yaml_content, encoding="utf-8")
        logger.debug("Settings saved to settings.yaml")

        # Clear cache inside lock to prevent race conditions
        _get_settings_cached.cache_clear()

        # Invalidate LLM Router so it rebuilds with new profiles
        from .llm_router import invalidate_router

        invalidate_router()


@lru_cache(maxsize=1)
def _get_settings_cached() -> PersistentSettings:
    """Internal cached settings loader."""
    return load_settings()


def get_settings() -> PersistentSettings:
    """Get persistent settings instance.

    Returns a copy to prevent mutation of cached data.
    Use clear_settings_cache() after modifications to refresh.
    """
    return _get_settings_cached().model_copy(deep=True)


def clear_settings_cache() -> None:
    """Clear the settings cache to force reload on next access."""
    _get_settings_cached.cache_clear()


def get_fallback_profile() -> ModelProfile | None:
    """Get the fallback LLM profile.

    Returns:
        The profile with status=FALLBACK, or None if no fallback configured
    """
    settings = get_settings()
    for profile in settings.llm_profiles:
        if profile.status == ProfileStatus.FALLBACK:
            return profile
    return None


def get_primary_profile() -> ModelProfile | None:
    """Get the primary LLM profile.

    Returns:
        The profile with status=PRIMARY, or None if no profiles configured
    """
    settings = get_settings()
    for profile in settings.llm_profiles:
        if profile.status == ProfileStatus.PRIMARY:
            return profile
    return None
