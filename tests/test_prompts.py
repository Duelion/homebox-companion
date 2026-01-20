"""Snapshot tests for prompt builder functions."""

from __future__ import annotations

import pytest

from homebox_companion.ai.prompts import (
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_language_instruction,
    build_naming_examples,
)
from homebox_companion.core.field_preferences import get_defaults

# All tests in this module are pure unit tests
pytestmark = pytest.mark.unit

# Get default values for tests
DEFAULTS = get_defaults()


class TestBuildItemSchema:
    """Test item schema generation."""

    def test_default_contains_required_fields(self) -> None:
        """Schema should contain name, quantity, description, labelIds."""
        result = build_item_schema({})

        assert "name: string" in result
        assert "quantity: integer" in result
        assert "description: string" in result
        assert "labelIds: array" in result

    def test_default_uses_field_defaults(self) -> None:
        """With empty customizations, should use fallback defaults."""
        result = build_item_schema({})

        # Should contain some reasonable default text
        assert "Title Case" in result or "max 255" in result
        assert ">= 1" in result or "count" in result.lower()
        assert "max 1000" in result or "condition" in result.lower()

    def test_with_customizations_replaces_defaults_inline(self) -> None:
        """Custom instructions should replace defaults inline, not append."""
        customizations = {
            "name": "CUSTOM: Brand first",
            "description": "CUSTOM: Only defects",
            "quantity": "CUSTOM: Count carefully",
        }

        result = build_item_schema(customizations)

        # Custom instructions should be present
        assert "CUSTOM: Brand first" in result
        assert "CUSTOM: Only defects" in result
        assert "CUSTOM: Count carefully" in result

        # Should use custom instructions, not default fallbacks
        assert "Title Case" not in result
        assert "condition/attributes" not in result

    def test_partial_customizations_keeps_other_defaults(self) -> None:
        """Only customized fields should be replaced."""
        customizations = {
            "name": "CUSTOM: Name instruction",
        }

        result = build_item_schema(customizations)

        # Custom name
        assert "CUSTOM: Name instruction" in result
        # Default quantity and description fallbacks
        assert ">= 1" in result or "count" in result.lower()
        assert "max 1000" in result or "condition" in result.lower()


class TestBuildNamingExamples:
    """Test naming examples generation."""

    def test_default_contains_examples(self) -> None:
        """Should contain naming examples."""
        result = build_naming_examples({})

        assert "Examples:" in result
        assert "Ball Bearing" in result or "LED Strip" in result

    def test_with_user_preference_adds_override_section(self) -> None:
        """User naming preference should add USER NAMING PREFERENCE section."""
        customizations = {
            "name": "Always put brand name first",
        }

        result = build_naming_examples(customizations)

        assert "USER NAMING PREFERENCE" in result
        assert "takes priority" in result
        assert "Always put brand name first" in result

    def test_with_custom_examples_uses_them(self) -> None:
        """Custom examples should replace default examples."""
        custom_examples = '"Example One", "Example Two", "Example Three"'
        customizations = {
            "naming_examples": custom_examples,
        }

        result = build_naming_examples(customizations)

        assert "Example One" in result
        assert "Example Two" in result
        assert "Example Three" in result

    def test_default_format_no_override_section(self) -> None:
        """Without user customization, should not have override section."""
        result = build_naming_examples({})

        assert "USER NAMING PREFERENCE" not in result


class TestBuildExtendedFieldsSchema:
    """Test extended fields schema generation."""

    def test_contains_all_optional_fields(self) -> None:
        """Schema should list all extended fields."""
        result = build_extended_fields_schema({})

        assert "manufacturer:" in result
        assert "modelNumber:" in result
        assert "serialNumber:" in result
        assert "purchasePrice:" in result
        assert "purchaseFrom:" in result
        assert "notes:" in result

    def test_default_uses_field_defaults(self) -> None:
        """With empty customizations, should use fallback defaults."""
        result = build_extended_fields_schema({})

        assert "brand" in result.lower() or "manufacturer" in result.lower()
        assert "code" in result.lower() or "model" in result.lower()

    def test_with_customizations_replaces_inline(self) -> None:
        """Custom instructions should replace defaults inline."""
        customizations = {
            "manufacturer": "CUSTOM: Extract brand from logos",
            "notes": "CUSTOM: Storage recommendations",
        }

        result = build_extended_fields_schema(customizations)

        # Custom instructions present
        assert "CUSTOM: Extract brand from logos" in result
        assert "CUSTOM: Storage recommendations" in result

        # Should use custom instructions, not default fallbacks
        assert "brand name when visible" not in result
        assert "ONLY for defects" not in result

    def test_notes_with_custom_instruction(self) -> None:
        """Custom notes instruction should override default."""
        # With custom instruction
        customizations = {"notes": "Always include warranty info"}
        result_custom = build_extended_fields_schema(customizations)

        # Custom instruction should be present
        assert "Always include warranty info" in result_custom

        # Should not contain fallback default text
        assert "ONLY for defects" not in result_custom


class TestBuildCriticalConstraints:
    """Test critical constraints generation."""

    def test_normal_mode_contains_combination_rules(self) -> None:
        """Normal mode should have rules about combining identical items."""
        result = build_critical_constraints(single_item=False)

        assert "RULES:" in result
        assert "Combine identical" in result or "identical objects" in result
        assert "Separate" in result or "different items" in result
        assert "Do NOT guess" in result

    def test_single_item_mode_enforces_one_item(self) -> None:
        """Single item mode should enforce treating everything as one item."""
        result = build_critical_constraints(single_item=True)

        assert "CRITICAL:" in result
        assert "ONE item" in result
        assert "Do NOT separate" in result or "NOT separate" in result

    def test_both_modes_include_no_guessing(self) -> None:
        """Both modes should include the no-guessing rule."""
        result_normal = build_critical_constraints(single_item=False)
        result_single = build_critical_constraints(single_item=True)

        assert "Do NOT guess" in result_normal or "not guess" in result_normal.lower()
        assert "Do NOT guess" in result_single or "not guess" in result_single.lower()


class TestBuildLabelPrompt:
    """Test label assignment prompt generation."""

    def test_with_labels_lists_all_with_ids(self) -> None:
        """Should list all labels with their IDs."""
        labels = [
            {"id": "label-1", "name": "Electronics"},
            {"id": "label-2", "name": "Tools"},
            {"id": "label-3", "name": "Hardware"},
        ]

        result = build_label_prompt(labels)

        assert "Electronics" in result
        assert "label-1" in result
        assert "Tools" in result
        assert "label-2" in result
        assert "Hardware" in result
        assert "label-3" in result

    def test_with_no_labels_says_none_available(self) -> None:
        """With no labels, should indicate none available."""
        result_none = build_label_prompt(None)
        result_empty = build_label_prompt([])

        assert "No labels" in result_none
        assert "omit labelIds" in result_none
        assert "No labels" in result_empty

    def test_filters_invalid_labels(self) -> None:
        """Should filter out labels missing id or name."""
        labels = [
            {"id": "label-1", "name": "Valid"},
            {"id": "", "name": "No ID"},
            {"id": "label-3", "name": ""},
            {},
        ]

        result = build_label_prompt(labels)

        assert "Valid" in result
        assert "label-1" in result
        # Invalid labels should not appear
        assert "No ID" not in result


class TestBuildLanguageInstruction:
    """Test language output instruction generation."""

    @pytest.mark.parametrize(
        "language,expected_empty",
        [
            (None, True),  # None returns empty
            ("English", True),  # English returns empty
            ("english", True),  # Case-insensitive English
            ("ENGLISH", True),  # Uppercase English
        ],
    )
    def test_english_variants_return_empty_string(self, language: str | None, expected_empty: bool) -> None:
        """English language variants should return empty string."""
        result = build_language_instruction(language)

        if expected_empty:
            assert result == ""
        else:
            assert result != ""

    @pytest.mark.parametrize(
        "language",
        ["Spanish", "German", "French", "Japanese", "Portuguese"],
    )
    def test_non_english_contains_language_directive(self, language: str) -> None:
        """Non-English languages should include output directive."""
        result = build_language_instruction(language)

        assert language in result
        assert "OUTPUT LANGUAGE" in result or "language" in result.lower()

    def test_preserves_field_names_in_english(self) -> None:
        """Should mention keeping field names in English for JSON."""
        result = build_language_instruction("German")

        assert "field names" in result.lower() or "English" in result


class TestPromptStructureProperties:
    """Test structural properties across prompts for regression detection."""

    def test_critical_constraints_front_loaded(self) -> None:
        """Critical constraints should be concise for front-loading."""
        result_normal = build_critical_constraints(single_item=False)
        result_single = build_critical_constraints(single_item=True)

        # Both should be relatively short (under 500 chars for front-loading)
        assert len(result_normal) < 500
        assert len(result_single) < 300

    def test_schema_builders_return_non_empty(self) -> None:
        """All schema builders should return non-empty strings."""
        assert build_item_schema({})
        assert build_extended_fields_schema({})
        assert build_naming_examples({})

    def test_customizations_empty_dict_safe(self) -> None:
        """All builders should handle empty dict gracefully."""
        empty_customizations = {}

        # Should not raise errors with empty dict
        build_item_schema(empty_customizations)
        build_extended_fields_schema(empty_customizations)
        build_naming_examples(empty_customizations)
