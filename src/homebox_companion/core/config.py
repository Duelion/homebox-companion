"""Centralized configuration for Homebox Companion.

All environment variables use the HBC_ prefix to avoid
clashes with other applications on the same system.

Environment Variables:
    HBC_API_URL: Base URL of your Homebox API (default: demo server)
    HBC_OPENAI_API_KEY: Your OpenAI API key for vision detection
    HBC_OPENAI_MODEL: OpenAI model to use (default: gpt-4o-mini)
    HBC_SERVER_HOST: Host to bind the web server to (default: 0.0.0.0)
    HBC_SERVER_PORT: Port for the web server (default: 8000). In production,
        this single port serves both the API and the static frontend.
    HBC_LOG_LEVEL: Logging level (default: INFO)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Demo server for testing - users should replace with their own instance
DEMO_API_URL = "https://demo.homebox.software/api/v1"


@dataclass
class Settings:
    """Application settings loaded from environment variables.

    All environment variables use the HBC_ prefix to ensure
    they don't conflict with other applications.

    Note: Settings are read from environment at instantiation time.
    The module-level `settings` instance acts as a singleton.
    """

    # Homebox API configuration
    api_url: str = field(
        default_factory=lambda: os.environ.get("HBC_API_URL", DEMO_API_URL)
    )

    # OpenAI configuration
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("HBC_OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.environ.get("HBC_OPENAI_MODEL", "gpt-4o-mini")
    )

    # Web server configuration
    server_host: str = field(
        default_factory=lambda: os.environ.get("HBC_SERVER_HOST", "0.0.0.0")
    )
    server_port: int = field(
        default_factory=lambda: int(os.environ.get("HBC_SERVER_PORT", "8000"))
    )

    # Logging configuration
    log_level: str = field(
        default_factory=lambda: os.environ.get("HBC_LOG_LEVEL", "INFO")
    )

    @property
    def is_demo_mode(self) -> bool:
        """Check if using the demo server."""
        return self.api_url == DEMO_API_URL

    def validate(self) -> list[str]:
        """Validate settings and return list of issues."""
        issues = []
        if not self.openai_api_key:
            issues.append(
                "HBC_OPENAI_API_KEY is not set. "
                "Vision detection will not work without an OpenAI API key."
            )
        return issues


# Module-level singleton instance for easy import
# Settings are read from environment variables when this module is first imported
settings = Settings()

