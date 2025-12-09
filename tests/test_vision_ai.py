"""AI tests for vision detection with real OpenAI API.

These tests require HBC_OPENAI_API_KEY to be set and will be skipped
if the API key is not available. They hit the real OpenAI API.

Run with: uv run pytest tests/test_vision_ai.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homebox_companion import detect_items_from_bytes


@pytest.mark.asyncio
async def test_single_item_detection_returns_one_item(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Single item detection should return exactly 1 item with name and quantity."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        single_item=True,
    )

    assert len(detected_items) == 1, "Expected exactly 1 item with single_item=True"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1, "Quantity must be at least 1"
    assert isinstance(detected_items[0].description, (str, type(None)))


@pytest.mark.asyncio
async def test_multi_item_detection_returns_multiple_items(
    api_key: str,
    model: str,
    multi_item_single_image_path: Path,
) -> None:
    """Multi-item detection should return multiple items with distinct names."""
    image_bytes = multi_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        single_item=False,
    )

    assert len(detected_items) > 1, "Expected multiple items from multi-item image"

    # Each item should have required fields
    for item in detected_items:
        assert item.name, "Each item must have a name"
        assert item.quantity >= 1, "Each item must have positive quantity"

    # Names should be distinct
    names = [item.name for item in detected_items]
    assert len(names) == len(set(names)), "Item names should be distinct"


@pytest.mark.asyncio
async def test_detection_with_labels_assigns_valid_ids(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with labels should assign valid label IDs from provided list."""
    image_bytes = single_item_single_image_path.read_bytes()

    labels = [
        {"id": "label-1", "name": "Electronics"},
        {"id": "label-2", "name": "Tools"},
        {"id": "label-3", "name": "Hardware"},
    ]

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        labels=labels,
    )

    assert detected_items, "Should detect at least one item"

    # If labels are assigned, they should be from the provided list
    for item in detected_items:
        if item.label_ids:
            valid_label_ids = {label["id"] for label in labels}
            for label_id in item.label_ids:
                assert (
                    label_id in valid_label_ids
                ), f"Label {label_id} not in provided labels"


@pytest.mark.asyncio
async def test_detection_with_extended_fields_includes_metadata(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with extended fields should include manufacturer/model when visible."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        extract_extended_fields=True,
    )

    assert detected_items, "Should detect at least one item"

    # At least verify extended fields are None or valid strings/numbers
    for item in detected_items:
        if item.manufacturer:
            assert isinstance(item.manufacturer, str)
            assert len(item.manufacturer) > 0
        if item.model_number:
            assert isinstance(item.model_number, str)
            assert len(item.model_number) > 0
        if item.purchase_price:
            assert isinstance(item.purchase_price, (int, float))
            assert item.purchase_price > 0


@pytest.mark.asyncio
async def test_multi_image_analysis_combines_information(
    api_key: str,
    model: str,
    single_item_multi_image_1_path: Path,
    single_item_multi_image_2_path: Path,
) -> None:
    """Multi-image analysis should combine information from multiple angles."""
    primary_bytes = single_item_multi_image_1_path.read_bytes()
    additional_bytes = single_item_multi_image_2_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=primary_bytes,
        api_key=api_key,
        model=model,
        single_item=True,
        additional_images=[(additional_bytes, "image/jpeg")],
    )

    assert len(detected_items) == 1, "Expected 1 item from multi-image analysis"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1


@pytest.mark.asyncio
async def test_detection_with_custom_field_preferences(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with custom field preferences should follow custom instructions."""
    image_bytes = single_item_single_image_path.read_bytes()

    field_preferences = {
        "name": "Always start with the item type, followed by brand if visible",
        "description": "Focus only on visible condition and defects",
    }

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        field_preferences=field_preferences,
    )

    assert detected_items, "Should detect at least one item"
    # We can't verify the AI followed instructions exactly, but we can verify
    # the call succeeded and returned valid items
    for item in detected_items:
        assert item.name
        assert item.quantity >= 1


@pytest.mark.asyncio
async def test_detection_handles_empty_labels_list(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with empty labels list should succeed without label IDs."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        labels=[],
    )

    assert detected_items, "Should detect items even without labels"
    # Items should not have label_ids or should have empty list
    for item in detected_items:
        assert item.label_ids is None or item.label_ids == []


@pytest.mark.asyncio
async def test_detection_with_output_language(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with non-English output language should return non-English text."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        output_language="Spanish",
    )

    assert detected_items, "Should detect items in Spanish"
    # We can't easily verify the language is Spanish without NLP,
    # but we can verify the call succeeded
    for item in detected_items:
        assert item.name
        assert item.quantity >= 1


@pytest.mark.asyncio
async def test_detection_returns_valid_detected_item_instances(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection should return DetectedItem instances with correct types."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
    )

    assert detected_items, "Should detect at least one item"

    for item in detected_items:
        # Verify types
        assert isinstance(item.name, str)
        assert isinstance(item.quantity, int)
        assert isinstance(item.description, (str, type(None)))
        assert isinstance(item.label_ids, (list, type(None)))

        # Verify values
        assert len(item.name) > 0
        assert item.quantity >= 1

        # If label_ids present, should be list of strings
        if item.label_ids:
            assert all(isinstance(label_id, str) for label_id in item.label_ids)


@pytest.mark.asyncio
async def test_detection_with_extra_instructions(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Detection with extra instructions should succeed."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        extra_instructions="Focus on identifying the brand and model",
    )

    assert detected_items, "Should detect at least one item"
    # Verify the call succeeded with extra instructions
    for item in detected_items:
        assert item.name
        assert item.quantity >= 1

