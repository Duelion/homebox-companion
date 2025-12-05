"""Pytest configuration and fixtures for Homebox Companion tests.

This module provides centralized test configuration using pydantic_settings
and shared fixtures for integration tests.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

# Demo server URL for testing
DEMO_HOMEBOX_URL = "https://demo.homebox.software"

# Test assets directory
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class TestSettings(BaseSettings):
    """Test configuration loaded from environment variables.

    Uses the same HBC_ prefix as the main application for consistency.
    Does NOT read from .env file to ensure tests are isolated from
    local development configuration.
    """

    model_config = SettingsConfigDict(
        env_prefix="HBC_",
        extra="ignore",
        # Explicitly disable .env loading for test isolation
        env_file=None,
    )

    # OpenAI configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    # Homebox configuration - always use demo server for tests
    homebox_url: str = DEMO_HOMEBOX_URL

    @property
    def api_url(self) -> str:
        """Full Homebox API URL with /api/v1 path appended."""
        base = self.homebox_url.rstrip("/")
        return f"{base}/api/v1"


@lru_cache
def get_test_settings() -> TestSettings:
    """Get cached test settings instance."""
    return TestSettings()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Provide test settings instance."""
    return get_test_settings()


@pytest.fixture(scope="session")
def api_key(test_settings: TestSettings) -> str:
    """Provide OpenAI API key, skipping test if not set."""
    if not test_settings.openai_api_key:
        pytest.skip("HBC_OPENAI_API_KEY must be set for integration tests.")
    return test_settings.openai_api_key


@pytest.fixture(scope="session")
def model(test_settings: TestSettings) -> str:
    """Provide OpenAI model name."""
    return test_settings.openai_model


@pytest.fixture(scope="session")
def homebox_api_url(test_settings: TestSettings) -> str:
    """Provide Homebox API URL."""
    return test_settings.api_url


# ---------------------------------------------------------------------------
# Image Path Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def single_item_single_image_path() -> Path:
    """Path to single item single image test asset."""
    return ASSETS_DIR / "single_item_single_image.jpg"


@pytest.fixture(scope="session")
def single_item_multi_image_1_path() -> Path:
    """Path to first multi-image test asset (single item)."""
    return ASSETS_DIR / "single_item_multi_image_1.jpg"


@pytest.fixture(scope="session")
def single_item_multi_image_2_path() -> Path:
    """Path to second multi-image test asset (single item)."""
    return ASSETS_DIR / "single_item_multi_image_2.jpg"


@pytest.fixture(scope="session")
def multi_item_single_image_path() -> Path:
    """Path to multi-item single image test asset."""
    return ASSETS_DIR / "multi_item_single_image.jpg"

