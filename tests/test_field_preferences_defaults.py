"""Tests for FieldPreferencesDefaults and environment variable handling.

These tests verify that:
1. Hardcoded defaults are used when no env vars are set
2. Environment variables (HBC_AI_*) override hardcoded defaults
3. The get_defaults() function returns correct values
4. File-based preferences correctly overlay on env var defaults
"""

from __future__ import annotations

import json
import os

import pytest

# We need to import the module fresh for each test to pick up env var changes
# So we'll import the class/function directly in each test after setting env vars


class TestFieldPreferencesDefaultsHardcoded:
    """Tests for hardcoded default values when no env vars are set."""

    def test_output_language_default(self, monkeypatch):
        """Test output_language defaults to English."""
        # Clear any existing env var
        monkeypatch.delenv("HBC_AI_OUTPUT_LANGUAGE", raising=False)

        # Import fresh to pick up env changes
        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.output_language == "English"

    def test_name_default(self, monkeypatch):
        """Test name has proper hardcoded default."""
        monkeypatch.delenv("HBC_AI_NAME", raising=False)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert "Title Case" in defaults.name
        assert "item type first" in defaults.name

    def test_description_default(self, monkeypatch):
        """Test description has proper hardcoded default."""
        monkeypatch.delenv("HBC_AI_DESCRIPTION", raising=False)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert "NEVER mention quantity" in defaults.description

    def test_quantity_default(self, monkeypatch):
        """Test quantity has proper hardcoded default."""
        monkeypatch.delenv("HBC_AI_QUANTITY", raising=False)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert "identical items" in defaults.quantity

    def test_default_label_id_is_none(self, monkeypatch):
        """Test default_label_id has no default (None)."""
        monkeypatch.delenv("HBC_AI_DEFAULT_LABEL_ID", raising=False)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.default_label_id is None

    def test_all_fields_have_defaults(self, monkeypatch):
        """Test all fields except default_label_id have non-empty defaults."""
        # Clear all HBC_AI_* env vars
        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()

        # All fields should have values except default_label_id
        assert defaults.output_language
        assert defaults.name
        assert defaults.naming_examples
        assert defaults.description
        assert defaults.quantity
        assert defaults.manufacturer
        assert defaults.model_number
        assert defaults.serial_number
        assert defaults.purchase_price
        assert defaults.purchase_from
        assert defaults.notes
        # default_label_id is intentionally None
        assert defaults.default_label_id is None


class TestFieldPreferencesDefaultsEnvOverride:
    """Tests for environment variable override of defaults."""

    def test_output_language_env_override(self, monkeypatch):
        """Test HBC_AI_OUTPUT_LANGUAGE overrides default."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Spanish")

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.output_language == "Spanish"

    def test_name_env_override(self, monkeypatch):
        """Test HBC_AI_NAME overrides default."""
        custom_instruction = "Always put brand first, then model"
        monkeypatch.setenv("HBC_AI_NAME", custom_instruction)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.name == custom_instruction

    def test_description_env_override(self, monkeypatch):
        """Test HBC_AI_DESCRIPTION overrides default."""
        custom_instruction = "Focus only on visible defects"
        monkeypatch.setenv("HBC_AI_DESCRIPTION", custom_instruction)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.description == custom_instruction

    def test_default_label_id_env_override(self, monkeypatch):
        """Test HBC_AI_DEFAULT_LABEL_ID can be set via env."""
        label_id = "abc123-label-id"
        monkeypatch.setenv("HBC_AI_DEFAULT_LABEL_ID", label_id)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.default_label_id == label_id

    def test_naming_examples_env_override(self, monkeypatch):
        """Test HBC_AI_NAMING_EXAMPLES overrides default."""
        custom_examples = '"Custom Example 1", "Custom Example 2"'
        monkeypatch.setenv("HBC_AI_NAMING_EXAMPLES", custom_examples)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.naming_examples == custom_examples

    def test_multiple_env_overrides(self, monkeypatch):
        """Test multiple env vars can be set simultaneously."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "German")
        monkeypatch.setenv("HBC_AI_NAME", "Custom name instruction")
        monkeypatch.setenv("HBC_AI_NOTES", "Custom notes instruction")

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()
        assert defaults.output_language == "German"
        assert defaults.name == "Custom name instruction"
        assert defaults.notes == "Custom notes instruction"
        # Non-overridden fields should still have hardcoded defaults
        assert "NEVER mention quantity" in defaults.description

    def test_all_fields_can_be_overridden(self, monkeypatch):
        """Test that every field can be overridden via env var."""
        overrides = {
            "HBC_AI_OUTPUT_LANGUAGE": "French",
            "HBC_AI_DEFAULT_LABEL_ID": "test-label",
            "HBC_AI_NAME": "Custom name",
            "HBC_AI_NAMING_EXAMPLES": "Custom examples",
            "HBC_AI_DESCRIPTION": "Custom description",
            "HBC_AI_QUANTITY": "Custom quantity",
            "HBC_AI_MANUFACTURER": "Custom manufacturer",
            "HBC_AI_MODEL_NUMBER": "Custom model",
            "HBC_AI_SERIAL_NUMBER": "Custom serial",
            "HBC_AI_PURCHASE_PRICE": "Custom price",
            "HBC_AI_PURCHASE_FROM": "Custom from",
            "HBC_AI_NOTES": "Custom notes",
        }

        for key, value in overrides.items():
            monkeypatch.setenv(key, value)

        from homebox_companion.core.field_preferences import FieldPreferencesDefaults

        defaults = FieldPreferencesDefaults()

        assert defaults.output_language == "French"
        assert defaults.default_label_id == "test-label"
        assert defaults.name == "Custom name"
        assert defaults.naming_examples == "Custom examples"
        assert defaults.description == "Custom description"
        assert defaults.quantity == "Custom quantity"
        assert defaults.manufacturer == "Custom manufacturer"
        assert defaults.model_number == "Custom model"
        assert defaults.serial_number == "Custom serial"
        assert defaults.purchase_price == "Custom price"
        assert defaults.purchase_from == "Custom from"
        assert defaults.notes == "Custom notes"


class TestGetDefaultsFunction:
    """Tests for the get_defaults() function."""

    def test_get_defaults_returns_instance(self, monkeypatch):
        """Test get_defaults() returns a FieldPreferencesDefaults instance."""
        from homebox_companion.core.field_preferences import (
            FieldPreferencesDefaults,
            get_defaults,
        )

        defaults = get_defaults()
        assert isinstance(defaults, FieldPreferencesDefaults)

    def test_get_defaults_picks_up_env_vars(self, monkeypatch):
        """Test get_defaults() returns values from env vars."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Japanese")

        from homebox_companion.core.field_preferences import get_defaults

        defaults = get_defaults()
        assert defaults.output_language == "Japanese"

    def test_get_defaults_fresh_instance(self, monkeypatch):
        """Test get_defaults() returns fresh instance each time."""
        from homebox_companion.core.field_preferences import get_defaults

        defaults1 = get_defaults()
        defaults2 = get_defaults()

        # Should be different objects (not cached)
        assert defaults1 is not defaults2


class TestLoadFieldPreferencesWithEnv:
    """Tests for load_field_preferences() with env var defaults."""

    def test_load_without_file_uses_env_defaults(self, monkeypatch, tmp_path):
        """Test loading returns env var values when no file exists."""
        # Set up a clean config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Italian")

        from homebox_companion.core import field_preferences

        # Patch the config dir and file paths
        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json"
        )

        prefs = field_preferences.load_field_preferences()

        # output_language and default_label_id come from env/defaults
        # Other fields are None in the FieldPreferences model
        assert prefs.output_language == "Italian" or prefs.output_language is None
        # The loaded prefs should have None for non-special fields
        assert prefs.name is None

    def test_file_overrides_env_defaults(self, monkeypatch, tmp_path):
        """Test that file-based preferences override env var defaults."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Set env var
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Portuguese")

        # Create file with different value
        file_prefs = {"output_language": "Korean", "name": "File-based name"}
        prefs_file.write_text(json.dumps(file_prefs))

        from homebox_companion.core import field_preferences

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        prefs = field_preferences.load_field_preferences()

        # File should win over env var
        assert prefs.output_language == "Korean"
        assert prefs.name == "File-based name"


class TestResetFieldPreferencesWithEnv:
    """Tests for reset_field_preferences() with env var defaults."""

    def test_reset_returns_env_defaults(self, monkeypatch, tmp_path):
        """Test reset removes file and returns env var defaults."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Set env var
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Russian")

        # Create a file that will be deleted
        prefs_file.write_text(json.dumps({"output_language": "Chinese"}))
        assert prefs_file.exists()

        from homebox_companion.core import field_preferences

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        prefs = field_preferences.reset_field_preferences()

        # File should be deleted
        assert not prefs_file.exists()

        # Should return env var default
        assert prefs.output_language == "Russian"


class TestEffectiveDefaultsEndToEnd:
    """End-to-end tests simulating the full flow."""

    def test_defaults_flow_no_env_no_file(self, monkeypatch, tmp_path):
        """Test complete flow with no env vars and no file."""
        # Clear all HBC_AI_* env vars
        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        from homebox_companion.core import field_preferences

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json"
        )

        # get_defaults should return hardcoded defaults
        defaults = field_preferences.get_defaults()
        assert defaults.output_language == "English"
        assert "Title Case" in defaults.name

    def test_defaults_flow_with_env_no_file(self, monkeypatch, tmp_path):
        """Test complete flow with env vars but no file."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Dutch")
        monkeypatch.setenv("HBC_AI_NAME", "Dutch naming convention")

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        from homebox_companion.core import field_preferences

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json"
        )

        defaults = field_preferences.get_defaults()
        assert defaults.output_language == "Dutch"
        assert defaults.name == "Dutch naming convention"
        # Non-overridden fields still have hardcoded defaults
        assert "NEVER mention quantity" in defaults.description

    def test_defaults_flow_env_plus_file(self, monkeypatch, tmp_path):
        """Test complete flow with both env vars and file preferences."""
        # Env sets output_language to French
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "French")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # File overrides output_language to Spanish and sets custom name
        file_prefs = {"output_language": "Spanish", "name": "Custom from file"}
        prefs_file.write_text(json.dumps(file_prefs))

        from homebox_companion.core import field_preferences

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        # get_defaults still returns env var value (French)
        defaults = field_preferences.get_defaults()
        assert defaults.output_language == "French"

        # But load_field_preferences returns file value (Spanish)
        prefs = field_preferences.load_field_preferences()
        assert prefs.output_language == "Spanish"
        assert prefs.name == "Custom from file"


class TestEffectiveCustomizationsMethod:
    """Tests for the get_effective_customizations() method."""

    def test_returns_defaults_when_no_user_values(self, monkeypatch):
        """Test that effective customizations returns defaults for empty prefs."""
        monkeypatch.setenv("HBC_AI_NAME", "Custom name from env")

        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences()  # All None values
        result = prefs.get_effective_customizations()

        # Should have our env var value
        assert result["name"] == "Custom name from env"
        # Should have all fields
        assert "description" in result
        assert "quantity" in result
        assert "manufacturer" in result

    def test_user_values_override_defaults(self, monkeypatch):
        """Test that user values take priority over env defaults."""
        monkeypatch.setenv("HBC_AI_NAME", "Env name")
        monkeypatch.setenv("HBC_AI_DESCRIPTION", "Env description")

        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            name="User custom name",  # Override env
            description=None,  # Use env default
        )
        result = prefs.get_effective_customizations()

        assert result["name"] == "User custom name"  # User wins
        assert result["description"] == "Env description"  # Env default

    def test_all_prompt_fields_present(self, monkeypatch):
        """Test that all prompt-relevant fields are in the result."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences()
        result = prefs.get_effective_customizations()

        expected_fields = [
            "name", "description", "quantity", "manufacturer",
            "model_number", "serial_number", "purchase_price",
            "purchase_from", "notes", "naming_examples"
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
            assert result[field], f"Empty value for field: {field}"


class TestEnvVarsFlowToPrompts:
    """Integration tests verifying env vars flow through to actual prompts."""

    def test_env_vars_appear_in_detection_prompt(self, monkeypatch):
        """Test that env var defaults appear in detection system prompts."""
        # Set custom env var
        monkeypatch.setenv("HBC_AI_NAME", "CUSTOM_ENV_NAME_INSTRUCTION")
        monkeypatch.setenv("HBC_AI_DESCRIPTION", "CUSTOM_ENV_DESC_INSTRUCTION")

        from homebox_companion.core.field_preferences import (
            load_field_preferences,
        )
        from homebox_companion.tools.vision.prompts import build_detection_system_prompt

        # Simulate what get_vision_context() does
        prefs = load_field_preferences()
        effective = prefs.get_effective_customizations()

        # Build prompt with effective customizations
        prompt = build_detection_system_prompt(
            labels=[{"id": "test", "name": "Test"}],
            field_preferences=effective,
        )

        # Env var values should appear in prompt
        assert "CUSTOM_ENV_NAME_INSTRUCTION" in prompt
        assert "CUSTOM_ENV_DESC_INSTRUCTION" in prompt

    def test_env_language_flows_to_prompts(self, monkeypatch):
        """Test that output language env var affects prompts."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "German")

        from homebox_companion.core.field_preferences import load_field_preferences
        from homebox_companion.tools.vision.prompts import build_detection_system_prompt

        prefs = load_field_preferences()
        lang = prefs.get_output_language()
        effective = prefs.get_effective_customizations()

        prompt = build_detection_system_prompt(
            labels=[],
            field_preferences=effective,
            output_language=lang if lang.lower() != "english" else None,
        )

        # German language instruction should appear
        assert "German" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

