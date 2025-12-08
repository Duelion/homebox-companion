"""Tests to verify field preferences are correctly injected INLINE into prompts.

The new approach integrates customizations directly into field definitions rather
than appending a separate "FIELD CUSTOMIZATIONS" section at the end. This ensures:
1. Custom instructions REPLACE defaults (no conflicts)
2. Instructions appear WHERE they belong (in field definitions)
3. Name customizations add an override note to NAMING_FORMAT
4. Critical constraints are front-loaded in prompts

These tests monkeypatch the OpenAI completion functions to capture the actual
prompts being constructed, allowing verification without real API calls.
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest

from homebox_companion.ai import prompts as prompts_module
from homebox_companion.ai.prompts import (
    FIELD_DEFAULTS,
    NAMING_FORMAT,
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_naming_rules,
)
from homebox_companion.core.field_preferences import FieldPreferences
from homebox_companion.tools.vision.analyzer import analyze_item_details_from_images
from homebox_companion.tools.vision.corrector import correct_item_with_openai
from homebox_companion.tools.vision.detector import (
    detect_items_from_bytes,
    discriminatory_detect_items,
)
from homebox_companion.tools.vision.merger import merge_items_with_openai

# Sample test data
SAMPLE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n"  # Minimal PNG header
SAMPLE_DATA_URI = "data:image/png;base64,iVBORw0KGgo="
SAMPLE_LABELS = [{"id": "label-1", "name": "Electronics"}, {"id": "label-2", "name": "Tools"}]


class PromptCapture:
    """Helper class to capture prompts sent to OpenAI."""

    def __init__(self):
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None
        self.call_count: int = 0

    async def mock_vision_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_uris: list[str],
        api_key: str,
        model: str,
    ) -> dict:
        """Mock vision_completion that captures prompts."""
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.call_count += 1
        # Return minimal valid response
        return {"items": [{"name": "Test Item", "quantity": 1, "description": "Test"}]}

    async def mock_chat_completion(
        self,
        messages: list[dict],
        api_key: str,
        model: str,
        response_format: dict | None = None,
    ) -> dict:
        """Mock chat_completion that captures prompts."""
        for msg in messages:
            if msg.get("role") == "system":
                self.system_prompt = msg.get("content")
            elif msg.get("role") == "user":
                self.user_prompt = msg.get("content")
        self.call_count += 1
        return {"name": "Merged Item", "quantity": 5, "description": "Merged"}


@pytest.fixture
def prompt_capture():
    """Fixture that provides a fresh PromptCapture instance."""
    return PromptCapture()


@pytest.fixture
def sample_field_preferences() -> dict[str, str]:
    """Sample field preferences for testing - uses snake_case keys to match FIELD_DEFAULTS."""
    return {
        "name": "Always include brand name first",
        "description": "Focus on condition and unique features",
        "notes": "Include storage recommendations",
        "manufacturer": "Extract from any visible branding",
        "model_number": "Look for part numbers on labels",
    }


class TestCriticalConstraintsBuilder:
    """Tests for build_critical_constraints helper."""

    def test_critical_constraints_normal_mode(self):
        """Test critical constraints for normal multi-item mode."""
        result = build_critical_constraints(single_item=False)
        print("\n" + "=" * 80)
        print("CRITICAL CONSTRAINTS - NORMAL MODE:")
        print("=" * 80)
        print(result)

        assert "RULES:" in result
        assert "Combine identical" in result
        assert "Do NOT guess" in result

    def test_critical_constraints_single_item_mode(self):
        """Test critical constraints for single-item mode."""
        result = build_critical_constraints(single_item=True)
        print("\n" + "=" * 80)
        print("CRITICAL CONSTRAINTS - SINGLE ITEM MODE:")
        print("=" * 80)
        print(result)

        assert "CRITICAL:" in result
        assert "ONE item" in result
        assert "Do NOT separate" in result


class TestDetectItemsPromptInjection:
    """Tests for detect_items_from_bytes prompt construction."""

    @pytest.mark.asyncio
    async def test_detect_without_preferences_uses_defaults(self, prompt_capture):
        """Test detection prompt uses default instructions when no preferences."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await detect_items_from_bytes(
                image_bytes=SAMPLE_IMAGE_BYTES,
                api_key="test-key",
                labels=SAMPLE_LABELS,
            )

        print("\n" + "=" * 80)
        print("DETECT WITHOUT PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify NO separate customization section exists
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt

        # Verify default instructions are inline
        assert "Title Case, no quantity, max 255 characters" in prompt_capture.system_prompt

        # Verify critical constraints are early in prompt (before schema)
        assert prompt_capture.system_prompt.find("RULES:") < prompt_capture.system_prompt.find(
            "OUTPUT SCHEMA"
        )

    @pytest.mark.asyncio
    async def test_detect_with_preferences_replaces_defaults_inline(
        self, prompt_capture, sample_field_preferences
    ):
        """Test that preferences REPLACE default instructions inline (not appended)."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await detect_items_from_bytes(
                image_bytes=SAMPLE_IMAGE_BYTES,
                api_key="test-key",
                labels=SAMPLE_LABELS,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("DETECT WITH PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # CRITICAL: Verify NO separate "FIELD CUSTOMIZATIONS" section
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt

        # Verify custom instructions appear INLINE in field definitions
        assert "Always include brand name first" in prompt_capture.system_prompt
        # The default should NOT be there since it was replaced
        assert "Title Case, no quantity, max 255 characters" not in prompt_capture.system_prompt

        # Verify name customization adds override note
        assert "USER NAMING PREFERENCE" in prompt_capture.system_prompt
        assert "takes priority" in prompt_capture.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_detect_with_extended_fields_and_preferences(
        self, prompt_capture, sample_field_preferences
    ):
        """Test extended fields schema uses custom instructions inline."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await detect_items_from_bytes(
                image_bytes=SAMPLE_IMAGE_BYTES,
                api_key="test-key",
                labels=SAMPLE_LABELS,
                extract_extended_fields=True,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("DETECT WITH EXTENDED FIELDS AND PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify NO separate customization section
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt

        # Verify custom instructions appear in extended fields section
        assert "Extract from any visible branding" in prompt_capture.system_prompt
        assert "Include storage recommendations" in prompt_capture.system_prompt
        assert "Look for part numbers on labels" in prompt_capture.system_prompt


class TestDiscriminatoryDetectPromptInjection:
    """Tests for discriminatory_detect_items prompt construction."""

    @pytest.mark.asyncio
    async def test_discriminatory_with_preferences_inline(
        self, prompt_capture, sample_field_preferences
    ):
        """Test discriminatory detection uses inline customizations."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await discriminatory_detect_items(
                image_data_uris=[SAMPLE_DATA_URI],
                api_key="test-key",
                labels=SAMPLE_LABELS,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("DISCRIMINATORY DETECT WITH PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify inline integration
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt
        assert "Always include brand name first" in prompt_capture.system_prompt
        assert "USER NAMING PREFERENCE" in prompt_capture.system_prompt
        assert "MAXIMUM SPECIFICITY" in prompt_capture.system_prompt


class TestCorrectItemPromptInjection:
    """Tests for correct_item_with_openai prompt construction."""

    @pytest.mark.asyncio
    async def test_correct_with_preferences_inline(
        self, prompt_capture, sample_field_preferences
    ):
        """Test correction prompt uses inline customizations."""
        current_item = {"name": "Unknown Item", "quantity": 1, "description": "Test"}

        with patch(
            "homebox_companion.tools.vision.corrector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await correct_item_with_openai(
                image_data_uri=SAMPLE_DATA_URI,
                current_item=current_item,
                correction_instructions="This is actually a screwdriver",
                api_key="test-key",
                labels=SAMPLE_LABELS,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("CORRECT WITH PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify inline integration, not appended section
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt
        # Custom instructions should be in the extended fields section
        assert "Extract from any visible branding" in prompt_capture.system_prompt
        # Name preference should add override note
        assert "USER NAMING PREFERENCE" in prompt_capture.system_prompt


class TestMergeItemsPromptInjection:
    """Tests for merge_items_with_openai prompt construction."""

    @pytest.mark.asyncio
    async def test_merge_with_preferences_inline(
        self, prompt_capture, sample_field_preferences
    ):
        """Test merge prompt uses inline customizations."""
        items = [
            {"name": "80 Grit Sandpaper", "quantity": 2, "description": "Coarse"},
            {"name": "120 Grit Sandpaper", "quantity": 3, "description": "Medium"},
        ]

        with patch(
            "homebox_companion.ai.openai.chat_completion",
            prompt_capture.mock_chat_completion,
        ):
            await merge_items_with_openai(
                items=items,
                api_key="test-key",
                labels=SAMPLE_LABELS,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("MERGE WITH PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify inline integration
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt
        # Merge uses name and description preferences in its schema
        assert "Always include brand name first" in prompt_capture.system_prompt
        assert "Focus on condition and unique features" in prompt_capture.system_prompt
        # Should have naming override note
        assert "USER NAMING PREFERENCE" in prompt_capture.system_prompt


class TestAnalyzeItemPromptInjection:
    """Tests for analyze_item_details_from_images prompt construction."""

    @pytest.mark.asyncio
    async def test_analyze_with_preferences_inline(
        self, prompt_capture, sample_field_preferences
    ):
        """Test analyze prompt uses inline customizations."""
        with patch(
            "homebox_companion.tools.vision.analyzer.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await analyze_item_details_from_images(
                image_data_uris=[SAMPLE_DATA_URI],
                item_name="Power Drill",
                item_description="Cordless drill",
                api_key="test-key",
                labels=SAMPLE_LABELS,
                field_preferences=sample_field_preferences,
            )

        print("\n" + "=" * 80)
        print("ANALYZE WITH PREFERENCES - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt_capture.system_prompt)

        # Verify inline integration
        assert "FIELD CUSTOMIZATIONS" not in prompt_capture.system_prompt
        # Custom instructions should be inline with field definitions
        assert "Always include brand name first" in prompt_capture.system_prompt
        assert "Include storage recommendations" in prompt_capture.system_prompt
        assert "USER NAMING PREFERENCE" in prompt_capture.system_prompt


class TestFieldPreferencesModel:
    """Tests for the FieldPreferences model itself."""

    def test_to_customizations_dict_empty(self):
        """Test that empty preferences return empty dict."""
        prefs = FieldPreferences()
        result = prefs.to_customizations_dict()
        print("\n" + "=" * 80)
        print("EMPTY PREFERENCES TO_CUSTOMIZATIONS_DICT:")
        print("=" * 80)
        print(f"Result: {result}")
        assert result == {}

    def test_to_customizations_dict_preserves_snake_case(self):
        """Test that keys remain snake_case to match FIELD_DEFAULTS."""
        prefs = FieldPreferences(
            name="Brand first, then type",
            description="Focus on condition",
            model_number="Look for part numbers",
            purchase_price="Extract from visible tags",
        )
        result = prefs.to_customizations_dict()
        print("\n" + "=" * 80)
        print("PREFERENCES TO_CUSTOMIZATIONS_DICT:")
        print("=" * 80)
        print(f"Result: {result}")

        # Keys should be snake_case to match FIELD_DEFAULTS
        assert "name" in result
        assert "model_number" in result  # NOT "model number"
        assert "purchase_price" in result  # NOT "purchase price"
        assert result["name"] == "Brand first, then type"

    def test_to_prompt_dict_is_alias(self):
        """Test that to_prompt_dict is an alias for to_customizations_dict."""
        prefs = FieldPreferences(name="Test instruction")
        assert prefs.to_prompt_dict() == prefs.to_customizations_dict()

    def test_filters_empty_and_none_values(self):
        """Test that empty/whitespace/None values are filtered out."""
        prefs = FieldPreferences(
            name="Brand first",
            description="",  # Empty
            notes="   ",  # Whitespace only
            manufacturer=None,  # None
        )
        result = prefs.to_customizations_dict()
        print("\n" + "=" * 80)
        print("FILTERS EMPTY VALUES:")
        print("=" * 80)
        print(f"Result: {result}")

        assert "name" in result
        assert "description" not in result
        assert "notes" not in result
        assert "manufacturer" not in result


class TestSchemaBuilders:
    """Tests for the schema builder functions."""

    def test_build_item_schema_with_defaults(self):
        """Test build_item_schema uses defaults when no customizations."""
        result = build_item_schema()
        print("\n" + "=" * 80)
        print("BUILD_ITEM_SCHEMA - DEFAULTS:")
        print("=" * 80)
        print(result)

        assert FIELD_DEFAULTS["name"] in result
        assert FIELD_DEFAULTS["quantity"] in result
        assert FIELD_DEFAULTS["description"] in result

    def test_build_item_schema_with_customizations(self):
        """Test build_item_schema replaces defaults with customizations."""
        customizations = {
            "name": "CUSTOM: Brand first, type second",
            "description": "CUSTOM: Focus on defects only",
        }
        result = build_item_schema(customizations)
        print("\n" + "=" * 80)
        print("BUILD_ITEM_SCHEMA - WITH CUSTOMIZATIONS:")
        print("=" * 80)
        print(result)

        # Custom instructions should be present
        assert "CUSTOM: Brand first, type second" in result
        assert "CUSTOM: Focus on defects only" in result
        # Default for name should NOT be present (replaced)
        assert FIELD_DEFAULTS["name"] not in result
        # But quantity default should still be there (not customized)
        assert FIELD_DEFAULTS["quantity"] in result

    def test_build_extended_fields_schema_with_customizations(self):
        """Test build_extended_fields_schema replaces defaults inline."""
        customizations = {
            "manufacturer": "CUSTOM: Extract from any logo",
            "notes": "CUSTOM: Always include storage tips",
        }
        result = build_extended_fields_schema(customizations)
        print("\n" + "=" * 80)
        print("BUILD_EXTENDED_FIELDS_SCHEMA - WITH CUSTOMIZATIONS:")
        print("=" * 80)
        print(result)

        # Custom instructions should replace defaults
        assert "CUSTOM: Extract from any logo" in result
        assert "CUSTOM: Always include storage tips" in result
        # Defaults for customized fields should NOT be present
        assert FIELD_DEFAULTS["manufacturer"] not in result
        assert FIELD_DEFAULTS["notes"] not in result

    def test_build_naming_rules_without_customization(self):
        """Test build_naming_rules returns base rules when no customization."""
        result = build_naming_rules()
        print("\n" + "=" * 80)
        print("BUILD_NAMING_RULES - NO CUSTOMIZATION:")
        print("=" * 80)
        print(result)

        assert NAMING_FORMAT in result
        assert "Examples:" in result
        assert "USER NAMING PREFERENCE" not in result

    def test_build_naming_rules_with_customization(self):
        """Test build_naming_rules adds override note with customization."""
        result = build_naming_rules({"name": "Always put brand name first"})
        print("\n" + "=" * 80)
        print("BUILD_NAMING_RULES - WITH CUSTOMIZATION:")
        print("=" * 80)
        print(result)

        # Should contain base rules PLUS override note
        assert "USER NAMING PREFERENCE" in result
        assert "takes priority" in result
        assert "Always put brand name first" in result

    def test_build_naming_rules_with_custom_examples(self):
        """Test build_naming_rules uses custom examples when provided."""
        custom_examples = '"My Custom Example 1", "My Custom Example 2"'
        result = build_naming_rules({"naming_examples": custom_examples})
        print("\n" + "=" * 80)
        print("BUILD_NAMING_RULES - WITH CUSTOM EXAMPLES:")
        print("=" * 80)
        print(result)

        assert "My Custom Example 1" in result
        assert "My Custom Example 2" in result


class TestPromptStructureOptimization:
    """Tests to verify prompts follow the optimized structure."""

    @pytest.mark.asyncio
    async def test_critical_constraints_before_schema(self, prompt_capture):
        """Verify critical constraints appear before schema in detection prompts."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await detect_items_from_bytes(
                image_bytes=SAMPLE_IMAGE_BYTES,
                api_key="test-key",
                labels=SAMPLE_LABELS,
            )

        prompt = prompt_capture.system_prompt

        # Find positions
        rules_pos = prompt.find("RULES:")
        schema_pos = prompt.find("OUTPUT SCHEMA")

        print("\n" + "=" * 80)
        print("PROMPT STRUCTURE CHECK:")
        print("=" * 80)
        print(f"RULES position: {rules_pos}")
        print(f"OUTPUT SCHEMA position: {schema_pos}")

        # Critical constraints (RULES:) should come BEFORE schema
        assert rules_pos < schema_pos, "Critical constraints should appear before schema"

    @pytest.mark.asyncio
    async def test_single_item_mode_critical_first(self, prompt_capture):
        """Verify single-item mode puts CRITICAL constraint first."""
        with patch(
            "homebox_companion.tools.vision.detector.vision_completion",
            prompt_capture.mock_vision_completion,
        ):
            await detect_items_from_bytes(
                image_bytes=SAMPLE_IMAGE_BYTES,
                api_key="test-key",
                labels=SAMPLE_LABELS,
                single_item=True,
            )

        prompt = prompt_capture.system_prompt
        print("\n" + "=" * 80)
        print("SINGLE ITEM MODE - SYSTEM PROMPT:")
        print("=" * 80)
        print(prompt)

        # CRITICAL should appear early
        critical_pos = prompt.find("CRITICAL:")
        schema_pos = prompt.find("OUTPUT SCHEMA")

        assert critical_pos != -1, "CRITICAL should be in prompt"
        assert critical_pos < schema_pos, "CRITICAL should appear before schema"


class TestNoAppendedCustomizationsSection:
    """Meta-tests to ensure the old append approach is completely removed."""

    def test_build_field_customizations_prompt_removed(self):
        """Verify the old append function is no longer used in prompts module."""
        source = inspect.getsource(prompts_module)

        # The function definition should be removed
        assert "def build_field_customizations_prompt" not in source

    def test_no_field_customizations_header_in_any_output(self, prompt_capture):
        """Comprehensive test that no prompt ever contains the old header."""
        # This is more of a documentation test - the actual verification
        # happens in each individual test above. This serves as a reminder
        # that "FIELD CUSTOMIZATIONS" should NEVER appear.
        pass  # Verified by assertions in other tests


if __name__ == "__main__":
    # Run with verbose output to see all prompts
    pytest.main([__file__, "-v", "-s"])
