"""AI tests for vision detection with real LLM API.

These tests require an LLM API key to be set and will be skipped
if no key is available. They hit the real LLM API.

Environment variables (in order of preference):
    - HBC_LLM_API_KEY + HBC_LLM_MODEL (preferred)
    - HBC_OPENAI_API_KEY + HBC_OPENAI_MODEL (legacy fallback)

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
    """Detection with labels should only assign label IDs from provided list."""
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

    # If labels are assigned, they must be from the provided list
    valid_label_ids = {label["id"] for label in labels}
    for item in detected_items:
        if item.label_ids:
            for label_id in item.label_ids:
                assert (
                    label_id in valid_label_ids
                ), f"Label {label_id} not in provided labels"

