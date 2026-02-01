"""AI tests for vision detection with OpenAI models.

These tests require TEST_OPENAI_API_KEY to be set and will be skipped
if no key is available. They hit the real OpenAI API.

Environment variables:
    - TEST_OPENAI_API_KEY (required)
    - TEST_OPENAI_MODEL (optional, defaults to gpt-5-mini)

Run with: TEST_OPENAI_API_KEY=your-key uv run pytest tests/test_openai_vision_ai.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homebox_companion import detect_items_from_bytes

# All tests in this module hit the real OpenAI API
pytestmark = pytest.mark.live


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


@pytest.mark.asyncio
async def test_single_item_detection_returns_one_item(
    single_item_single_image_path: Path,
) -> None:
    """Single item detection should return exactly 1 item with name and quantity."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        single_item=True,
    )

    assert len(detected_items) == 1, "Expected exactly 1 item with single_item=True"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1, "Quantity must be at least 1"


@pytest.mark.asyncio
async def test_multi_item_detection_returns_multiple_items(
    multi_item_single_image_path: Path,
) -> None:
    """Multi-item detection should return multiple items with distinct names."""
    image_bytes = multi_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
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
async def test_detection_with_tags_assigns_valid_ids(
    single_item_single_image_path: Path,
) -> None:
    """Detection with tags should only assign tag IDs from provided list."""
    image_bytes = single_item_single_image_path.read_bytes()

    tags = [
        {"id": "tag-1", "name": "Electronics"},
        {"id": "tag-2", "name": "Tools"},
        {"id": "tag-3", "name": "Hardware"},
    ]

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        tags=tags,
    )

    assert detected_items, "Should detect at least one item"

    # If tags are assigned, they must be from the provided list
    valid_tag_ids = {tag["id"] for tag in tags}
    for item in detected_items:
        if item.tag_ids:
            for tag_id in item.tag_ids:
                assert tag_id in valid_tag_ids, f"Tag {tag_id} not in provided tags"
