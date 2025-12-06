"""Centralized configuration for Homebox Companion.

All environment variables use the HBC_ prefix to avoid
clashes with other applications on the same system.

Environment Variables:
    HBC_HOMEBOX_URL: Base URL of your Homebox instance (default: demo server).
        We automatically append /api/v1 to this URL.
    HBC_OPENAI_API_KEY: Your OpenAI API key for vision detection
    HBC_OPENAI_MODEL: OpenAI model to use (default: gpt-5-mini)
    HBC_OPENAI_BASE_URL: Custom base URL for OpenAI-compatible API endpoints
        (optional). Use this for local models, Azure OpenAI, or other compatible
        providers. If not set, uses the official OpenAI API.
    HBC_SERVER_HOST: Host to bind the web server to (default: 0.0.0.0)
    HBC_SERVER_PORT: Port for the web server (default: 8000). In production,
        this single port serves both the API and the static frontend.
    HBC_LOG_LEVEL: Logging level (default: INFO)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Demo server for testing - users should replace with their own instance
DEMO_HOMEBOX_URL = "https://demo.homebox.software"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All environment variables use the HBC_ prefix to ensure
    they don't conflict with other applications.

    Uses pydantic-settings for automatic environment variable loading,
    type coercion, and validation.
    """

    model_config = SettingsConfigDict(
        env_prefix="HBC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Homebox configuration - user provides base URL, we append /api/v1
    homebox_url: str = DEMO_HOMEBOX_URL

    # OpenAI configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_base_url: str | None = None

    # Web server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Logging configuration
    log_level: str = "INFO"

    @computed_field
    @property
    def api_url(self) -> str:
        """Full Homebox API URL with /api/v1 path appended."""
        base = self.homebox_url.rstrip("/")
        return f"{base}/api/v1"

    @computed_field
    @property
    def is_demo_mode(self) -> bool:
        """Check if using the demo server."""
        return self.homebox_url.rstrip("/") == DEMO_HOMEBOX_URL

    def validate_config(self) -> list[str]:
        """Validate settings and return list of issues."""
        issues = []
        if not self.openai_api_key:
            issues.append(
                "HBC_OPENAI_API_KEY is not set. "
                "Vision detection will not work without an OpenAI API key."
            )
        return issues


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Using lru_cache ensures the settings are only loaded once,
    making this effectively a singleton while allowing for
    easier testing (cache can be cleared).
    """
    return Settings()


# Module-level singleton instance for easy import
# Settings are read from environment variables when this module is first imported
settings = get_settings()
