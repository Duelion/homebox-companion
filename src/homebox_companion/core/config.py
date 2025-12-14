"""Centralized configuration for Homebox Companion.

All environment variables use the HBC_ prefix to avoid
clashes with other applications on the same system.

Environment Variables:
    HBC_HOMEBOX_URL: Base URL of your Homebox instance (default: demo server).
        We automatically append /api/v1 to this URL.
    HBC_OPENAI_API_KEY: Your OpenAI API key for vision detection
    HBC_OPENAI_MODEL: OpenAI model to use (default: gpt-5-mini)
    HBC_SERVER_HOST: Host to bind the web server to (default: 0.0.0.0)
    HBC_SERVER_PORT: Port for the web server (default: 8000). In production,
        this single port serves both the API and the static frontend.
    HBC_LOG_LEVEL: Logging level (default: INFO)
    HBC_DISABLE_UPDATE_CHECK: Set to true to disable GitHub update checks (default: false)
    HBC_MAX_UPLOAD_SIZE_MB: Maximum file upload size in MB (default: 20)
    HBC_CORS_ORIGINS: Allowed CORS origins, comma-separated or "*" for all (default: "*")
    HBC_IMAGE_QUALITY: Image quality for Homebox uploads (default: medium).
        Options: raw (original), high (2560px, 85%), medium (1920px, 75%), low (1280px, 60%)

AI Output Customization env vars (HBC_AI_*) are handled separately in
field_preferences.py via FieldPreferencesDefaults.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Demo server for testing - users should replace with their own instance
DEMO_HOMEBOX_URL = "https://demo.homebox.software"


class ImageQuality(str, Enum):
    """Image quality levels for Homebox uploads.

    Controls compression applied to images before uploading to Homebox.
    Compression happens server-side during AI analysis to avoid slowing down mobile devices.
    """

    RAW = "raw"        # No compression, original file
    HIGH = "high"      # 2560px max, 85% JPEG quality
    MEDIUM = "medium"  # 1920px max, 75% JPEG quality (default)
    LOW = "low"        # 1280px max, 60% JPEG quality


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

    # Web server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Logging configuration
    log_level: str = "INFO"

    # Update check configuration
    disable_update_check: bool = False
    github_repo: str = "Duelion/homebox-companion"

    # Security configuration
    max_upload_size_mb: int = 20  # Maximum file upload size in MB
    cors_origins: str = "*"  # Comma-separated origins or "*" for all

    # Image processing configuration
    image_quality: ImageQuality = ImageQuality.MEDIUM

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

    @computed_field
    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def image_quality_params(self) -> tuple[int | None, int]:
        """Get image compression parameters based on quality setting.

        Returns:
            Tuple of (max_dimension, jpeg_quality).
            max_dimension is None for 'raw' quality (no resizing).
        """
        quality_map = {
            ImageQuality.RAW: (None, 100),
            ImageQuality.HIGH: (2560, 85),
            ImageQuality.MEDIUM: (1920, 75),
            ImageQuality.LOW: (1280, 60),
        }
        return quality_map[self.image_quality]

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
