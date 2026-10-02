"""Unit tests for error handling and failure modes.

These tests use mocked dependencies to ensure deterministic behavior
when testing error conditions like network failures, malformed responses,
and invalid input data.
"""

from __future__ import annotations

import json

import httpx
import pytest

from homebox_companion.core.exceptions import HomeboxAPIError, HomeboxAuthError
from homebox_companion.homebox.client import HomeboxClient

# All tests in this module are unit tests (mocked httpx, tmp_path for files)
pytestmark = pytest.mark.unit


class TestHomeboxClientErrorHandling:
    """Test HTTP error handling in HomeboxClient."""

    @pytest.mark.parametrize(
        "status,message,error,match",
        [
            pytest.param(401, "Token expired", HomeboxAuthError, "Token expired", id="authentication"),
            pytest.param(404, "Not found", HomeboxAPIError, "404", id="not-found"),
            pytest.param(500, "Internal server error", HomeboxAPIError, "500", id="server-error"),
        ],
    )
    def test_http_error_classification(self, status, message, error, match) -> None:
        response = httpx.Response(status, json={"error": message})
        with pytest.raises(error, match=match):
            HomeboxClient._ensure_success(response, "Test operation")

    def test_malformed_json_response_raises_with_text(self) -> None:
        """Non-JSON responses should raise HomeboxAPIError with text content."""
        response = httpx.Response(
            400,
            text="Bad request - invalid format",
        )

        with pytest.raises(HomeboxAPIError, match="Bad request"):
            HomeboxClient._ensure_success(response, "Update item")

    @pytest.mark.parametrize("status", [200, 204], ids=["success", "no-content"])
    def test_success_response_does_not_raise(self, status) -> None:
        HomeboxClient._ensure_success(httpx.Response(status), "Successful operation")


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
