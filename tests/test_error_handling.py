"""Unit tests for error handling and failure modes.

These tests use mocked dependencies to ensure deterministic behavior
when testing error conditions like network failures, malformed responses,
and invalid input data.
"""

from __future__ import annotations

import json

import httpx
import pytest

from homebox_companion.core.exceptions import AuthenticationError
from homebox_companion.homebox.client import HomeboxClient
from homebox_companion.tools.vision.models import DetectedItem


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

    def test_404_response_raises_runtime_error(self) -> None:
        """404 responses should raise RuntimeError with status code."""
        response = httpx.Response(
            404,
            json={"error": "Not found"},
        )

        with pytest.raises(RuntimeError, match="404"):
            HomeboxClient._ensure_success(response, "Fetch item")

    def test_500_response_raises_runtime_error(self) -> None:
        """500 responses should raise RuntimeError with status code."""
        response = httpx.Response(
            500,
            json={"error": "Internal server error"},
        )

        with pytest.raises(RuntimeError, match="500"):
            HomeboxClient._ensure_success(response, "Create item")

    def test_malformed_json_response_raises_with_text(self) -> None:
        """Non-JSON responses should raise error with text content."""
        response = httpx.Response(
            400,
            text="Bad request - invalid format",
        )

        with pytest.raises(RuntimeError, match="Bad request"):
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


class TestDetectedItemInvalidInput:
    """Test DetectedItem handling of invalid/malformed input data."""

    def test_non_dict_items_cause_attribute_error(self) -> None:
        """Non-dictionary items in raw list cause AttributeError (expected behavior)."""
        raw_items = [
            {"name": "Valid Item", "quantity": 1},
            "invalid string item",  # This will cause AttributeError
        ]

        # Current implementation doesn't filter non-dicts, it raises AttributeError
        # This tests that we're aware of this limitation
        with pytest.raises(AttributeError):
            DetectedItem.from_raw_items(raw_items)

    def test_nested_invalid_label_data_filtered(self) -> None:
        """Invalid nested data in labelIds should be filtered gracefully."""
        raw_items = [
            {
                "name": "Item 1",
                "quantity": 1,
                "labelIds": ["valid-1", {"nested": "dict"}, None, "valid-2"],
            },
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert len(items) == 1
        # Invalid entries should be converted to strings or filtered
        assert items[0].label_ids is not None
        assert "valid-1" in items[0].label_ids
        assert "valid-2" in items[0].label_ids

    def test_extremely_long_name_truncates(self) -> None:
        """Extremely long names should truncate without crashing."""
        long_name = "x" * 10000  # 10k characters
        item = DetectedItem(name=long_name, quantity=1)

        payload = item.to_create_payload()

        # Should truncate to 255
        assert len(payload["name"]) == 255

    def test_extremely_long_description_truncates(self) -> None:
        """Extremely long descriptions should truncate without crashing."""
        long_desc = "y" * 50000  # 50k characters
        item = DetectedItem(name="Item", quantity=1, description=long_desc)

        payload = item.to_create_payload()

        # Should truncate to 1000
        assert len(payload["description"]) == 1000

    def test_negative_quantity_normalizes_to_one(self) -> None:
        """Negative quantities should normalize to 1."""
        raw_items = [
            {"name": "Item 1", "quantity": -5},
            {"name": "Item 2", "quantity": -1},
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert items[0].quantity == 1
        assert items[1].quantity == 1

    def test_float_quantity_converts_to_int(self) -> None:
        """Float quantities should convert to integers."""
        raw_items = [
            {"name": "Item 1", "quantity": 3.7},
            {"name": "Item 2", "quantity": 5.2},
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert items[0].quantity == 3
        assert items[1].quantity == 5

    def test_missing_required_keys_handled_gracefully(self) -> None:
        """Items missing name should be filtered; missing quantity defaults."""
        raw_items = [
            {},  # Missing everything
            {"quantity": 5},  # Missing name
            {"name": "Valid"},  # Missing quantity (should default to 1)
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert len(items) == 1
        assert items[0].name == "Valid"
        assert items[0].quantity == 1


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


class TestVisionDetectionErrorHandling:
    """Test vision detection handling of malformed/invalid responses."""

    def test_empty_items_list_returns_empty_result(self) -> None:
        """Response with empty items list should return empty list."""
        raw_response = {"items": []}

        items = DetectedItem.from_raw_items(raw_response.get("items", []))

        assert items == []

    def test_missing_items_key_returns_empty_result(self) -> None:
        """Response missing 'items' key should return empty list."""
        raw_response = {"data": "something else"}

        items = DetectedItem.from_raw_items(raw_response.get("items", []))

        assert items == []

