"""Unit tests for error handling and failure modes.

These tests use mocked dependencies to ensure deterministic behavior
when testing error conditions like network failures, malformed responses,
and invalid input data.
"""

from __future__ import annotations

import json

import httpx
import pytest

from homebox_companion.core.exceptions import AuthenticationError, HomeboxAPIError
from homebox_companion.homebox.client import HomeboxClient

# All tests in this module are unit tests (mocked httpx, tmp_path for files)
pytestmark = pytest.mark.unit


class TestHomeboxClientErrorHandling:
    """Test HTTP error handling in HomeboxClient."""

    def test_401_response_raises_authentication_error(self) -> None:
        """401 responses should raise AuthenticationError."""
        response = httpx.Response(
            401,
            json={"error": "Token expired"},
        )

        with pytest.raises(AuthenticationError, match="Token expired"):
            HomeboxClient._ensure_success(response, "Test operation")

    def test_404_response_raises_homebox_api_error(self) -> None:
        """404 responses should raise HomeboxAPIError with status code."""
        response = httpx.Response(
            404,
            json={"error": "Not found"},
        )

        with pytest.raises(HomeboxAPIError, match="404"):
            HomeboxClient._ensure_success(response, "Fetch item")

    def test_500_response_raises_homebox_api_error(self) -> None:
        """500 responses should raise HomeboxAPIError with status code."""
        response = httpx.Response(
            500,
            json={"error": "Internal server error"},
        )

        with pytest.raises(HomeboxAPIError, match="500"):
            HomeboxClient._ensure_success(response, "Create item")

    def test_malformed_json_response_raises_with_text(self) -> None:
        """Non-JSON responses should raise HomeboxAPIError with text content."""
        response = httpx.Response(
            400,
            text="Bad request - invalid format",
        )

        with pytest.raises(HomeboxAPIError, match="Bad request"):
            HomeboxClient._ensure_success(response, "Update item")

    def test_success_response_does_not_raise(self) -> None:
        """2xx responses should not raise any errors."""
        response = httpx.Response(
            200,
            json={"id": "123", "name": "Test"},
        )

        # Should not raise
        HomeboxClient._ensure_success(response, "Successful operation")

    def test_204_no_content_does_not_raise(self) -> None:
        """204 No Content responses should not raise errors."""
        response = httpx.Response(204)

        # Should not raise
        HomeboxClient._ensure_success(response, "Delete operation")


class TestFieldPreferencesFileCorruption:
    """Test field preferences handling of corrupted/invalid files."""

    def test_corrupted_json_falls_back_to_defaults(self, monkeypatch, tmp_path) -> None:
        """Corrupted JSON file should fall back to defaults with warning."""
        from homebox_companion.core import field_preferences

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Write invalid JSON
        prefs_file.write_text("{ invalid json }")

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Should not crash - corrupted file triggers warning + defaults
        prefs = field_preferences.load_field_preferences()

        # Returns defaults (no env vars set in this test)
        assert isinstance(prefs, field_preferences.FieldPreferences)
        assert prefs.output_language == "English"

    def test_invalid_data_types_falls_back_to_defaults(self, monkeypatch, tmp_path) -> None:
        """Invalid data types in JSON should trigger warning and fallback."""
        from homebox_companion.core import field_preferences

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Write JSON with wrong data types
        invalid_prefs = {
            "output_language": 123,  # Should be string
            "name": ["list", "instead", "of", "string"],
            "description": None,
        }
        prefs_file.write_text(json.dumps(invalid_prefs))

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Should not crash - returns defaults with warning
        prefs = field_preferences.load_field_preferences()
        assert isinstance(prefs, field_preferences.FieldPreferences)
        assert prefs.output_language == "English"
