"""Centralized configuration for Homebox Companion.

All environment variables use the HBC_ prefix to avoid
clashes with other applications on the same system.

Environment Variables:
    HBC_HOMEBOX_URL: Base URL of your Homebox instance (default: demo server).
        We automatically append /api/v1 to this URL for API calls.
    HBC_LINK_BASE_URL: Optional public-facing URL for Homebox links shown to users.
        Defaults to HBC_HOMEBOX_URL if not set. Useful when the API is accessed
        internally (e.g., 127.0.0.1) but users access via a public domain.
    HBC_OPENAI_API_KEY: (Legacy) API key for LLM provider (use HBC_LLM_API_KEY instead)
    HBC_OPENAI_MODEL: (Legacy) LLM model to use (use HBC_LLM_MODEL instead, default: gpt-5-mini)
    HBC_LLM_API_KEY: API key for the configured LLM provider (preferred)
    HBC_LLM_MODEL: LLM model identifier (preferred)
    HBC_LLM_API_BASE: Optional API base URL for LLM-compatible gateways
    HBC_LLM_ALLOW_UNSAFE_MODELS: If true, allow models not in the curated allowlist (best-effort)
    HBC_LLM_TIMEOUT: LLM request timeout in seconds (default: 120)
    HBC_LLM_STREAM_TIMEOUT: LLM streaming timeout in seconds (default: 300)
    HBC_SERVER_HOST: Host to bind the web server to (default: 0.0.0.0)
    HBC_SERVER_PORT: Port for the web server (default: 8000). In production,
        this single port serves both the API and the static frontend.
    HBC_LOG_LEVEL: Logging level (default: INFO)
    HBC_DISABLE_UPDATE_CHECK: Set to true to disable GitHub update checks (default: false)
    HBC_MAX_UPLOAD_SIZE_MB: Maximum file upload size in MB (default: 20)
    HBC_CORS_ORIGINS: Allowed CORS origins, comma-separated or "*" for all (default: "*")
    HBC_IMAGE_QUALITY: Image quality for Homebox uploads (default: medium).
        Options: raw (original), high (2560px, 85%), medium (1920px, 75%), low (1280px, 60%)
    HBC_CHAT_ENABLED: Enable the conversational assistant (default: true)
    HBC_CHAT_MAX_HISTORY: Max messages in conversation context (default: 20)
    HBC_CHAT_APPROVAL_TIMEOUT: Seconds before pending approvals expire (default: 300)

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

    RAW = "raw"  # No compression, original file
    HIGH = "high"  # 2560px max, 85% JPEG quality
    MEDIUM = "medium"  # 1920px max, 75% JPEG quality (default)
    LOW = "low"  # 1280px max, 60% JPEG quality


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
    # Optional public-facing URL for links (defaults to homebox_url)
    link_base_url: str = ""

    # Backward compatibility: Also accepts HBC_OPENAI_API_KEY and HBC_OPENAI_MODEL
    # These are legacy env vars from before the LiteLLM migration
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    # LLM configuration (preferred)
    llm_api_key: str = ""
    llm_model: str = ""
    llm_api_base: str | None = None
    llm_allow_unsafe_models: bool = False

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

    # LLM request timeout (in seconds)
    llm_timeout: int = 120
    # LLM streaming timeout (in seconds) - longer for large responses
    llm_stream_timeout: int = 300

    # Demo mode - enables pre-filled credentials for demo deployments
    demo_mode: bool = False

    # Capture limits (frontend-enforced, configurable for users who want to risk larger sessions)
    capture_max_images: int = 30  # Max images per capture session
    capture_max_file_size_mb: int = 10  # Max file size per image in MB

    # Rate limiting configuration (prevents hitting OpenAI API limits)
    # Default values are 80% of Tier 1 limits for safety margin
    rate_limit_enabled: bool = True  # Set to false to disable rate limiting
    rate_limit_rpm: int = 400  # Requests per minute (Tier 1 limit: 500)
    rate_limit_tpm: int = 400_000  # Tokens per minute (Tier 1 limit: 500k for gpt-5-mini)
    rate_limit_burst_multiplier: float = 1.5  # Burst capacity multiplier

    # Chat/MCP configuration
    chat_enabled: bool = True  # Enable the conversational assistant
    chat_max_history: int = 20  # Max messages in conversation context
    chat_approval_timeout: int = 300  # Seconds before pending approvals expire
    chat_max_response_tokens: int = 0  # 0 = no limit (LLM decides naturally)

    # Auth rate limiting (brute-force protection)
    auth_rate_limit_rpm: int = 10  # Login attempts per minute per IP

    @computed_field
    @property
    def api_url(self) -> str:
        """Full Homebox API URL with /api/v1 path appended."""
        base = self.homebox_url.rstrip("/")
        return f"{base}/api/v1"

    @computed_field
    @property
    def effective_link_base_url(self) -> str:
        """Public-facing URL for user links (HBC_LINK_BASE_URL or fallback to HBC_HOMEBOX_URL)."""
        return (self.link_base_url or self.homebox_url).rstrip("/")

    @computed_field
    @property
    def effective_llm_api_key(self) -> str:
        """Effective LLM API key (HBC_LLM_API_KEY preferred, fallback to HBC_OPENAI_API_KEY)."""
        return (self.llm_api_key or self.openai_api_key or "").strip()

    @computed_field
    @property
    def effective_llm_model(self) -> str:
        """Effective LLM model (HBC_LLM_MODEL preferred, fallback to HBC_OPENAI_MODEL)."""
        return (self.llm_model or self.openai_model or "gpt-5-mini").strip()

    @computed_field
    @property
    def using_legacy_openai_env(self) -> bool:
        """True when the app is configured via legacy HBC_OPENAI_* variables."""
        return not bool(self.llm_api_key or self.llm_model)

    @computed_field
    @property
    def is_demo_mode(self) -> bool:
        """Check if demo mode is enabled.

        Demo mode is enabled when:
        - HBC_DEMO_MODE=true environment variable is set, OR
        - The Homebox URL points to the official demo server (demo.homebox.software)
        """
        if self.demo_mode:
            return True
        # Auto-detect demo mode when connected to the official demo server
        return "demo.homebox.software" in self.homebox_url.lower()

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
        if not self.effective_llm_api_key:
            issues.append(
                "HBC_LLM_API_KEY is not set (and no legacy HBC_OPENAI_API_KEY fallback). "
                "Vision detection will not work without an API key."
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
