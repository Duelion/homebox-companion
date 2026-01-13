"""Unified settings management with YAML persistence.

Consolidates LLM profiles and field preferences into a single settings.yaml file.
Bootstraps from environment variables on first run, then uses the file exclusively.

Settings flow:
1. First boot: env vars → create settings.yaml
2. Runtime: load from settings.yaml
3. Settings UI: modify and save to settings.yaml
"""

from __future__ import annotations

import threading
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Self

import yaml
from loguru import logger
from pydantic import BaseModel, Field, SecretStr, model_validator

from .field_preferences import FieldPreferences

# Data directory for persistent storage (mounted volume in Docker)
DATA_DIR = Path("data")
SETTINGS_FILE = DATA_DIR / "settings.yaml"

# Current schema version for migrations
CURRENT_VERSION = 1


class ProfileStatus(str, Enum):
    """Status of an LLM profile.

    ACTIVE: Currently in use for all AI operations
    FALLBACK: Used when active profile fails
    DISABLED: Available but not used
    """

    ACTIVE = "active"
    FALLBACK = "fallback"
    DISABLED = "disabled"


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
    status: ProfileStatus = ProfileStatus.DISABLED


class Settings(BaseModel):
    """Unified application settings.

    Contains all persistent configuration:
    - LLM profiles (multi-provider support)
    - Field preferences (AI output customization)

    Attributes:
        version: Schema version for migrations
        llm_profiles: List of configured LLM providers
        field_preferences: AI output field customizations
    """

    version: int = CURRENT_VERSION
    llm_profiles: list[ModelProfile] = []
    field_preferences: FieldPreferences = Field(default_factory=FieldPreferences)

    @model_validator(mode="after")
    def validate_profile_constraints(self) -> Self:
        """Ensure exactly one ACTIVE and at most one FALLBACK profile."""
        if not self.llm_profiles:
            return self

        actives = [p for p in self.llm_profiles if p.status == ProfileStatus.ACTIVE]
        fallbacks = [p for p in self.llm_profiles if p.status == ProfileStatus.FALLBACK]

        if len(actives) != 1:
            raise ValueError(
                f"Exactly one profile must be ACTIVE, found {len(actives)}"
            )
        if len(fallbacks) > 1:
            raise ValueError(
                f"At most one profile can be FALLBACK, found {len(fallbacks)}"
            )

        return self


def _settings_to_yaml_dict(settings: Settings) -> dict:
    """Convert Settings to a YAML-friendly dict."""
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
    }


def _yaml_dict_to_settings(data: dict) -> Settings:
    """Convert YAML dict to Settings, handling SecretStr conversion."""
    profiles = []
    for p in data.get("llm_profiles", []):
        profiles.append(
            ModelProfile(
                name=p["name"],
                model=p["model"],
                api_key=SecretStr(p["api_key"]) if p.get("api_key") else None,
                api_base=p.get("api_base"),
                status=ProfileStatus(p.get("status", "disabled")),
            )
        )

    field_prefs = data.get("field_preferences", {})

    return Settings(
        version=data.get("version", CURRENT_VERSION),
        llm_profiles=profiles,
        field_preferences=FieldPreferences.model_validate(field_prefs),
    )


def bootstrap_from_env() -> Settings:
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
                status=ProfileStatus.ACTIVE,
            )
        )
        logger.info(f"Bootstrapped default LLM profile from env: {model}")

    # Migrate existing field_preferences.json if it exists
    from .field_preferences import PREFERENCES_FILE, load_field_preferences

    field_prefs = FieldPreferences()
    if PREFERENCES_FILE.exists():
        field_prefs = load_field_preferences()
        logger.info("Migrated existing field_preferences.json to settings.yaml")

    return Settings(
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

    # Future migrations go here:
    # if version < 2:
    #     data = _migrate_v1_to_v2(data)
    #     version = 2

    data["version"] = CURRENT_VERSION
    return data


def load_settings() -> Settings:
    """Load settings from YAML file, bootstrapping if needed.

    Returns:
        Settings instance with all configuration
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


def save_settings(settings: Settings) -> None:
    """Save settings to YAML file.

    Thread-safe with file locking to prevent race conditions.
    Automatically clears the settings cache to ensure fresh data on next access.

    Args:
        settings: Settings instance to persist
    """
    with _settings_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        yaml_dict = _settings_to_yaml_dict(settings)

        # Use default_flow_style=False for readable multi-line output
        yaml_content = yaml.dump(yaml_dict, default_flow_style=False, allow_unicode=True)

        SETTINGS_FILE.write_text(yaml_content, encoding="utf-8")
        logger.debug("Settings saved to settings.yaml")

    # Clear cache after releasing lock to ensure fresh data on next access
    _get_settings_cached.cache_clear()


@lru_cache(maxsize=1)
def _get_settings_cached() -> Settings:
    """Internal cached settings loader."""
    return load_settings()


def get_settings() -> Settings:
    """Get settings instance.

    Returns a copy to prevent mutation of cached data.
    Use clear_settings_cache() after modifications to refresh.
    """
    return _get_settings_cached().model_copy(deep=True)


def clear_settings_cache() -> None:
    """Clear the settings cache to force reload on next access."""
    _get_settings_cached.cache_clear()


def get_active_profile() -> ModelProfile | None:
    """Get the currently active LLM profile.

    Returns:
        The profile with status=ACTIVE, or None if no profiles configured
    """
    settings = get_settings()
    for profile in settings.llm_profiles:
        if profile.status == ProfileStatus.ACTIVE:
            return profile
    return None


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
