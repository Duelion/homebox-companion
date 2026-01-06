"""AI provider configuration management.

This module provides storage and retrieval of AI provider settings,
allowing users to configure which AI provider to use and their credentials.

Supported providers:
- ollama: Local Ollama server
- openai: OpenAI API (GPT-4 Vision, etc.)
- anthropic: Anthropic API (Claude)
- litellm: LiteLLM proxy (existing cloud provider)

Settings are persisted to {data_dir}/ai_config.json
"""

from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from homebox_companion.core.config import settings


def _get_config_path() -> Path:
    """Get the AI config file path based on settings.data_dir."""
    return Path(settings.data_dir) / "ai_config.json"


class AIProvider(str, Enum):
    """Supported AI providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LITELLM = "litellm"  # Existing cloud provider


class OllamaConfig(BaseModel):
    """Ollama-specific configuration."""

    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "minicpm-v"
    timeout: int = 120


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""

    enabled: bool = False
    api_key: SecretStr | None = None
    model: str = "gpt-4o"
    max_tokens: int = 4096

    @field_validator("api_key", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: Any) -> Any:
        if v == "" or v == "null":
            return None
        return v


class AnthropicConfig(BaseModel):
    """Anthropic/Claude-specific configuration."""

    enabled: bool = False
    api_key: SecretStr | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096

    @field_validator("api_key", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: Any) -> Any:
        if v == "" or v == "null":
            return None
        return v


class LiteLLMConfig(BaseModel):
    """LiteLLM/existing cloud provider configuration."""

    enabled: bool = True  # Default enabled for backward compatibility
    model: str = "gpt-4o"


class AIConfig(BaseSettings):
    """Main AI configuration with provider selection.

    Environment variables (HBC_*) can override defaults.
    User settings from UI are stored in JSON and take highest priority.
    """

    model_config = SettingsConfigDict(
        env_prefix="HBC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Active provider - which one to use for AI operations
    active_provider: AIProvider = AIProvider.LITELLM

    # Fallback behavior
    fallback_to_cloud: bool = True
    fallback_provider: AIProvider = AIProvider.LITELLM

    # Provider-specific configs
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)

    def get_active_config(self) -> OllamaConfig | OpenAIConfig | AnthropicConfig | LiteLLMConfig:
        """Get the configuration for the active provider."""
        return getattr(self, self.active_provider.value)

    def is_provider_configured(self, provider: AIProvider) -> bool:
        """Check if a provider has valid configuration."""
        config = getattr(self, provider.value)

        if provider == AIProvider.OLLAMA:
            return config.enabled and bool(config.url)
        elif provider == AIProvider.OPENAI:
            return config.enabled and config.api_key is not None
        elif provider == AIProvider.ANTHROPIC:
            return config.enabled and config.api_key is not None
        elif provider == AIProvider.LITELLM:
            return config.enabled
        return False

    def to_safe_dict(self) -> dict[str, Any]:
        """Convert to dict with API keys masked for frontend display."""
        data = self.model_dump()

        # Mask API keys
        if data["openai"]["api_key"]:
            key = data["openai"]["api_key"]
            data["openai"]["api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

        if data["anthropic"]["api_key"]:
            key = data["anthropic"]["api_key"]
            data["anthropic"]["api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

        return data


@lru_cache(maxsize=1)
def get_ai_defaults() -> AIConfig:
    """Get the immutable defaults (hardcoded + env vars, resolved once).

    This is cached to avoid re-reading environment variables on every call.

    Returns:
        AIConfig with env vars applied over hardcoded defaults.
    """
    return AIConfig()


def load_ai_config() -> AIConfig:
    """Load AI config: defaults + user overrides from file.

    Priority (highest first):
    1. File-based user overrides (config/ai_config.json)
    2. Defaults (hardcoded + environment variables)

    Returns:
        AIConfig instance with merged values.
    """
    defaults = get_ai_defaults()

    config_file = _get_config_path()
    if not config_file.exists():
        return defaults

    try:
        file_data = json.loads(config_file.read_text(encoding="utf-8"))

        # Deep merge for nested provider configs
        merged = defaults.model_dump()

        # Update top-level fields
        for key in ["active_provider", "fallback_to_cloud", "fallback_provider"]:
            if key in file_data:
                merged[key] = file_data[key]

        # Update provider configs
        for provider in ["ollama", "openai", "anthropic", "litellm"]:
            if provider in file_data and file_data[provider]:
                merged[provider].update(file_data[provider])

        return AIConfig.model_validate(merged)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Invalid AI config file, using defaults: {e}")
        return defaults


def save_ai_config(config: AIConfig) -> None:
    """Save AI configuration to file.

    Args:
        config: The configuration to save.
    """
    config_file = _get_config_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict, handling SecretStr
    data = {
        "active_provider": config.active_provider.value,
        "fallback_to_cloud": config.fallback_to_cloud,
        "fallback_provider": config.fallback_provider.value,
        "ollama": config.ollama.model_dump(),
        "openai": {
            **config.openai.model_dump(),
            "api_key": config.openai.api_key.get_secret_value() if config.openai.api_key else None,
        },
        "anthropic": {
            **config.anthropic.model_dump(),
            "api_key": config.anthropic.api_key.get_secret_value() if config.anthropic.api_key else None,
        },
        "litellm": config.litellm.model_dump(),
    }

    config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"AI config saved to {config_file}: active_provider={config.active_provider.value}")


def reset_ai_config() -> AIConfig:
    """Reset to defaults by deleting the config file.

    Returns:
        AIConfig with defaults.
    """
    config_file = _get_config_path()
    if config_file.exists():
        config_file.unlink()
    # Clear the cache so defaults are re-evaluated
    get_ai_defaults.cache_clear()
    return get_ai_defaults()


def clear_ai_config_cache() -> None:
    """Clear the cached defaults (useful after config changes)."""
    get_ai_defaults.cache_clear()
