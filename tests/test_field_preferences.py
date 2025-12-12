"""Unit tests for field preferences configuration priority."""

from __future__ import annotations

import json

from homebox_companion.core import field_preferences


class TestConfigurationPriority:
    """Test the three-tier priority: file > env > hardcoded."""

    def test_load_with_no_file_no_env_returns_hardcoded(
        self, monkeypatch, tmp_path
    ) -> None:
        """With no file and no env vars, should return hardcoded defaults."""
        # Clear all HBC_AI_* env vars
        import os

        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        # Set up clean config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json"
        )

        # Get defaults
        defaults = field_preferences.get_defaults()

        assert defaults.output_language == "English"
        assert "Title Case" in defaults.name
        assert "NEVER mention quantity" in defaults.description

    def test_load_with_env_vars_set_overrides_hardcoded(self, monkeypatch, tmp_path) -> None:
        """Environment variables should override hardcoded defaults."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Spanish")
        monkeypatch.setenv("HBC_AI_NAME", "Custom naming from env")

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json"
        )

        defaults = field_preferences.get_defaults()

        assert defaults.output_language == "Spanish"
        assert defaults.name == "Custom naming from env"
        # Non-overridden field still has hardcoded default
        assert "NEVER mention quantity" in defaults.description

    def test_load_with_file_present_overrides_env(self, monkeypatch, tmp_path) -> None:
        """File-based preferences should override environment variables."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "French")
        monkeypatch.setenv("HBC_AI_NAME", "Env naming")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Create file with different values
        file_prefs = {
            "output_language": "German",
            "name": "File-based naming",
            "description": "File description",
        }
        prefs_file.write_text(json.dumps(file_prefs))

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        prefs = field_preferences.load_field_preferences()

        # File values should win
        assert prefs.output_language == "German"
        assert prefs.name == "File-based naming"
        assert prefs.description == "File description"


class TestGetEffectiveCustomizations:
    """Test merging user values with effective defaults."""

    def test_merges_user_values_with_defaults(self, monkeypatch) -> None:
        """Effective customizations should merge user overrides with env defaults."""
        monkeypatch.setenv("HBC_AI_NAME", "Env name instruction")
        monkeypatch.setenv("HBC_AI_DESCRIPTION", "Env description instruction")

        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            name="User custom name",  # Override env
            description=None,  # Use env default
            quantity=None,  # Use env/hardcoded default
        )

        result = prefs.get_effective_customizations()

        assert result["name"] == "User custom name"  # User wins
        assert result["description"] == "Env description instruction"  # Env default
        assert "quantity" in result  # Has value from hardcoded default

    def test_all_fields_have_values(self) -> None:
        """Effective customizations should always return values for all fields."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences()  # All None

        result = prefs.get_effective_customizations()

        expected_fields = [
            "name",
            "description",
            "quantity",
            "manufacturer",
            "model_number",
            "serial_number",
            "purchase_price",
            "purchase_from",
            "notes",
            "naming_examples",
        ]

        for field in expected_fields:
            assert field in result
            assert result[field]  # Has non-empty value


class TestToCustomizationsDict:
    """Test conversion to dict for prompt integration."""

    def test_filters_empty_values(self) -> None:
        """Empty and None values should be filtered out."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            name="Custom name",
            description="",  # Empty
            notes="   ",  # Whitespace
            manufacturer=None,  # None
        )

        result = prefs.to_customizations_dict()

        assert "name" in result
        assert result["name"] == "Custom name"
        assert "description" not in result
        assert "notes" not in result
        assert "manufacturer" not in result

    def test_uses_snake_case_keys(self) -> None:
        """Keys should be snake_case to match FIELD_DEFAULTS."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            model_number="Model123",
            purchase_price="Price instruction",
            purchase_from="Store instruction",
        )

        result = prefs.to_customizations_dict()

        assert "model_number" in result
        assert "purchase_price" in result
        assert "purchase_from" in result
        # Not camelCase
        assert "modelNumber" not in result

    def test_excludes_metadata_fields(self) -> None:
        """output_language and default_label_id should be excluded."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            output_language="Spanish",
            default_label_id="label-123",
            name="Custom name",
        )

        result = prefs.to_customizations_dict()

        assert "name" in result
        assert "output_language" not in result
        assert "default_label_id" not in result


class TestResetPreferences:
    """Test resetting preferences to defaults."""

    def test_deletes_file_and_returns_none_values(self, monkeypatch, tmp_path) -> None:
        """Reset should delete file and return prefs with None values.

        The actual defaults (from env vars or hardcoded) are resolved via
        get_output_language() or get_effective_customizations(), not stored
        in the FieldPreferences object directly.
        """
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Italian")
        monkeypatch.setenv("HBC_AI_NAME", "Env name")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Create file that will be deleted
        file_prefs = {"output_language": "Japanese", "name": "File name"}
        prefs_file.write_text(json.dumps(file_prefs))
        assert prefs_file.exists()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        prefs = field_preferences.reset_field_preferences()

        # File should be deleted
        assert not prefs_file.exists()

        # Raw field values should be None (meaning "use defaults")
        assert prefs.output_language is None
        assert prefs.name is None

        # Effective value should come from env var via get_output_language()
        assert prefs.get_output_language() == "Italian"

    def test_reset_without_file_succeeds(self, monkeypatch, tmp_path) -> None:
        """Reset should succeed even if no file exists."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        assert not prefs_file.exists()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        # Should not raise error
        prefs = field_preferences.reset_field_preferences()

        # Raw value is None, effective value comes from defaults
        assert prefs.output_language is None
        assert prefs.get_output_language() == "English"  # Hardcoded default


class TestSaveAndLoad:
    """Test save/load round-trip."""

    def test_save_and_load_preserves_values(self, monkeypatch, tmp_path) -> None:
        """Saved preferences should load correctly."""
        from homebox_companion.core.field_preferences import FieldPreferences

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        # Save preferences
        prefs = FieldPreferences(
            output_language="Portuguese",
            name="Custom name instruction",
            description="Custom description",
        )
        field_preferences.save_field_preferences(prefs)

        assert prefs_file.exists()

        # Load them back
        loaded = field_preferences.load_field_preferences()

        assert loaded.output_language == "Portuguese"
        assert loaded.name == "Custom name instruction"
        assert loaded.description == "Custom description"

    def test_save_creates_config_dir(self, monkeypatch, tmp_path) -> None:
        """Save should create config directory if it doesn't exist."""
        from homebox_companion.core.field_preferences import FieldPreferences

        config_dir = tmp_path / "nonexistent" / "config"
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        assert not config_dir.exists()

        prefs = FieldPreferences(name="Test")
        field_preferences.save_field_preferences(prefs)

        assert config_dir.exists()
        assert prefs_file.exists()

