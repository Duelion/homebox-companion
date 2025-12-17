"""Minimal pytest configuration for Homebox Companion tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict

# Demo server URL for integration tests
DEMO_HOMEBOX_URL = "https://demo.homebox.software"
DEMO_USERNAME = "demo@example.com"
DEMO_PASSWORD = "demo"

# Test assets directory
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class TestSettings(BaseSettings):
    """Test configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="HBC_",
        extra="ignore",
        env_file=".env",  # Load from .env file
        env_file_encoding="utf-8",
    )

    # Legacy OpenAI config (kept for backwards compatibility in tests)
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    # New generic LLM config (preferred)
    llm_api_key: str = ""
    llm_model: str = ""
    llm_api_base: str | None = None
    llm_allow_unsafe_models: bool = False
    homebox_url: str = DEMO_HOMEBOX_URL

    @property
    def api_url(self) -> str:
        """Full Homebox API URL with /api/v1 path appended."""
        base = self.homebox_url.rstrip("/")
        return f"{base}/api/v1"


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Provide test settings instance."""
    return TestSettings()


@pytest.fixture(scope="session")
def api_key(test_settings: TestSettings) -> str:
    """Provide LLM API key, skipping test if not set."""
    key = (test_settings.llm_api_key or test_settings.openai_api_key or "").strip()
    if not key:
        pytest.skip("HBC_LLM_API_KEY (or legacy HBC_OPENAI_API_KEY) must be set for AI tests.")
    return key


@pytest.fixture(scope="session")
def model(test_settings: TestSettings) -> str:
    """Provide LLM model name."""
    return (test_settings.llm_model or test_settings.openai_model or "gpt-5-mini").strip()


@pytest.fixture(scope="session")
def homebox_api_url(test_settings: TestSettings) -> str:
    """Provide Homebox API URL."""
    return test_settings.api_url


@pytest.fixture(scope="session")
def homebox_credentials() -> tuple[str, str]:
    """Provide Homebox demo credentials."""
    return DEMO_USERNAME, DEMO_PASSWORD


# ---------------------------------------------------------------------------
# Settings Override Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def allow_unsafe_models() -> Generator[None, None, None]:
    """Enable HBC_LLM_ALLOW_UNSAFE_MODELS for the test module.
    
    This fixture reloads the app settings after modifying the environment
    variable. All modules access settings via config.settings, so updating
    the config module is sufficient.
    """
    from homebox_companion.core import config
    from homebox_companion.core.config import get_settings
    
    # Store original value
    original = os.environ.get("HBC_LLM_ALLOW_UNSAFE_MODELS")
    
    # Set new value and reload settings
    os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"] = "true"
    get_settings.cache_clear()
    config.settings = get_settings()
    
    yield
    
    # Restore original state
    if original is None:
        os.environ.pop("HBC_LLM_ALLOW_UNSAFE_MODELS", None)
    else:
        os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"] = original
    get_settings.cache_clear()
    config.settings = get_settings()


# ---------------------------------------------------------------------------
# Image Path Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def single_item_single_image_path() -> Path:
    """Path to single item single image test asset."""
    path = ASSETS_DIR / "single_item_single_image.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def single_item_multi_image_1_path() -> Path:
    """Path to first multi-image test asset (single item)."""
    path = ASSETS_DIR / "single_item_multi_image_1.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def single_item_multi_image_2_path() -> Path:
    """Path to second multi-image test asset (single item)."""
    path = ASSETS_DIR / "single_item_multi_image_2.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def multi_item_single_image_path() -> Path:
    """Path to multi-item single image test asset."""
    path = ASSETS_DIR / "multi_item_single_image.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Resource Cleanup Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cleanup_items(homebox_api_url: str, homebox_credentials: tuple[str, str]):
    """Track and cleanup items created during tests.

    Usage in tests:
        async def test_something(cleanup_items):
            item_id = await create_item(...)
            cleanup_items.append(item_id)  # Will be deleted after test
    """
    from homebox_companion import HomeboxClient

    created_ids: list[str] = []
    yield created_ids

    # Teardown: delete all created items (best effort)
    if created_ids:
        username, password = homebox_credentials
        try:
            async with HomeboxClient(base_url=homebox_api_url) as client:
                token = await client.login(username, password)
                for item_id in created_ids:
                    try:
                        await client.delete_item(token, item_id)
                    except Exception:
                        # Best effort cleanup - don't fail test if cleanup fails
                        pass
        except Exception:
            # If we can't login or cleanup, just continue
            pass


@pytest_asyncio.fixture
async def cleanup_locations(homebox_api_url: str, homebox_credentials: tuple[str, str]):
    """Track and cleanup locations created during tests.

    Usage in tests:
        async def test_something(cleanup_locations):
            location_id = await create_location(...)
            cleanup_locations.append(location_id)  # Will be deleted after test
    """
    from homebox_companion import HomeboxClient

    created_ids: list[str] = []
    yield created_ids

    # Teardown: delete all created locations (best effort)
    if created_ids:
        username, password = homebox_credentials
        try:
            async with HomeboxClient(base_url=homebox_api_url) as client:
                token = await client.login(username, password)
                for location_id in created_ids:
                    try:
                        # Homebox API typically uses DELETE /locations/{id}
                        await client.client.delete(
                            f"{client.base_url}/locations/{location_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                    except Exception:
                        # Best effort cleanup
                        pass
        except Exception:
            pass
