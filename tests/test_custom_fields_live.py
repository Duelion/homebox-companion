"""Live integration test for custom fields in AI detection.

These tests hit the real LLM API to verify that custom field definitions
are included in the AI prompt and populated in the detection response.

Environment variables:
    - TEST_OPENAI_API_KEY (required)
    - TEST_OPENAI_MODEL (optional, defaults to gpt-5-mini)

Run with: TEST_OPENAI_API_KEY=your-key uv run pytest tests/test_custom_fields_live.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homebox_companion import detect_items_from_bytes
from homebox_companion.core.persistent_settings import CustomFieldDefinition
from homebox_companion.tools.vision.models import get_custom_fields_dict

# All tests in this module hit the real LLM API
pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# Custom field definitions used across tests
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = [
    CustomFieldDefinition(
        name="Storage Location",
        ai_instruction=(
            "Where this item should be stored or is typically found"
            " (e.g. garage shelf, kitchen drawer, office desk)"
        ),
    ),
    CustomFieldDefinition(
        name="Condition",
        ai_instruction="The apparent condition of the item based on the image (e.g. New, Like New, Good, Fair, Poor)",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def configure_llm(openai_api_key: str, openai_model: str, monkeypatch):
    """Configure LLM via environment variables for tests."""
    from homebox_companion.core import config
    from homebox_companion.core.llm_router import invalidate_router

    monkeypatch.setenv("HBC_LLM_API_KEY", openai_api_key)
    monkeypatch.setenv("HBC_LLM_MODEL", openai_model)
    config.settings = config.Settings()
    invalidate_router()

    yield

    invalidate_router()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCustomFieldsDetection:
    """Verify that custom fields are included in AI detection and populated."""

    @pytest.mark.asyncio
    async def test_detection_with_custom_fields_returns_populated_values(
        self,
        single_item_single_image_path: Path,
    ) -> None:
        """Custom fields should appear in detection results with non-empty values.

        This test verifies the full pipeline:
        1. Custom field definitions are passed to detect_items_from_bytes
        2. The AI prompt includes custom field schema
        3. The dynamic Pydantic model validates custom field values
        4. get_custom_fields_dict extracts them as a display-name → value dict
        """
        image_bytes = single_item_single_image_path.read_bytes()

        detected_items = await detect_items_from_bytes(
            image_bytes=image_bytes,
            single_item=True,
            custom_fields=CUSTOM_FIELDS,
        )

        assert len(detected_items) == 1, "Expected exactly 1 item with single_item=True"
        item = detected_items[0]

        # Item should have basic fields
        assert item.name, "Item must have a name"
        assert item.quantity >= 1, "Quantity must be at least 1"

        # Extract custom fields using the helper (same path used by the API)
        custom_dict = get_custom_fields_dict(item, CUSTOM_FIELDS)

        # Custom fields dict should exist and have our field names
        assert custom_dict is not None, (
            "Custom fields dict should not be None — the AI should populate at least one custom field. "
            f"Item model fields: {list(item.model_fields.keys())}"
        )

        # Verify both custom fields are present as keys
        assert "Storage Location" in custom_dict, (
            f"'Storage Location' missing from custom fields. Got: {custom_dict}"
        )
        assert "Condition" in custom_dict, (
            f"'Condition' missing from custom fields. Got: {custom_dict}"
        )

        # Values should be non-empty strings
        assert custom_dict["Storage Location"].strip(), (
            "Storage Location value should not be empty"
        )
        assert custom_dict["Condition"].strip(), (
            "Condition value should not be empty"
        )

        # Condition should be a reasonable assessment
        valid_conditions = {"new", "like new", "good", "fair", "poor", "excellent", "used", "unknown"}
        condition_lower = custom_dict["Condition"].strip().lower()
        assert any(c in condition_lower for c in valid_conditions), (
            f"Condition '{custom_dict['Condition']}' doesn't match expected values"
        )

    @pytest.mark.asyncio
    async def test_detection_without_custom_fields_returns_none(
        self,
        single_item_single_image_path: Path,
    ) -> None:
        """Detection without custom fields should return None for custom_fields_dict."""
        image_bytes = single_item_single_image_path.read_bytes()

        detected_items = await detect_items_from_bytes(
            image_bytes=image_bytes,
            single_item=True,
            # No custom_fields parameter
        )

        assert len(detected_items) >= 1, "Should detect at least one item"
        item = detected_items[0]

        # With no custom field definitions, get_custom_fields_dict should return None
        custom_dict = get_custom_fields_dict(item, [])
        assert custom_dict is None, "Custom fields dict should be None when no definitions provided"

    @pytest.mark.asyncio
    async def test_dynamic_model_has_custom_field_attributes(
        self,
        single_item_single_image_path: Path,
    ) -> None:
        """The dynamic DetectedItem subclass should have custom fields as proper attributes."""
        image_bytes = single_item_single_image_path.read_bytes()

        detected_items = await detect_items_from_bytes(
            image_bytes=image_bytes,
            single_item=True,
            custom_fields=CUSTOM_FIELDS,
        )

        assert detected_items, "Should detect at least one item"
        item = detected_items[0]

        # Dynamic model should have the snake_case field attributes
        assert hasattr(item, "storage_location"), (
            f"Item should have 'storage_location' attribute. "
            f"Model type: {type(item).__name__}, fields: {list(item.model_fields.keys())}"
        )
        assert hasattr(item, "condition"), (
            f"Item should have 'condition' attribute. "
            f"Model type: {type(item).__name__}, fields: {list(item.model_fields.keys())}"
        )

        # The model class name should be the dynamic subclass
        assert type(item).__name__ == "DynamicDetectedItem", (
            f"Expected DynamicDetectedItem, got {type(item).__name__}"
        )
