"""Test all curated models via OpenRouter.

These tests require TEST_LLM_API_KEY to be set with an OpenRouter API key.
Each test validates single-item detection works correctly for each model.

Run with: TEST_LLM_API_KEY=your-key uv run pytest tests/test_openrouter_models.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from homebox_companion import detect_items_from_bytes

# OpenRouter model paths (full paths required for OpenRouter API)
# Note: Only models verified to work on OpenRouter are included
OPENROUTER_MODELS = [
    "openrouter/openai/gpt-5-mini",
    "openrouter/openai/gpt-5-nano",
    "openrouter/google/gemini-2.5-flash",
    "openrouter/anthropic/claude-3-5-sonnet-20241022",
    "openrouter/openai/gpt-4o-mini",
    "openrouter/openai/gpt-4o",
    "openrouter/anthropic/claude-3-opus-20240229",
]


@pytest.fixture(scope="module")
def openrouter_api_key() -> str:
    """Provide OpenRouter API key, skipping test if not set."""
    key = os.environ.get("TEST_LLM_API_KEY", "").strip()
    if not key:
        pytest.skip("TEST_LLM_API_KEY must be set for OpenRouter tests.")
    return key


@pytest.mark.parametrize("openrouter_model", OPENROUTER_MODELS)
@pytest.mark.asyncio
async def test_single_item_detection(
    openrouter_model: str,
    openrouter_api_key: str,
    single_item_single_image_path: Path,
) -> None:
    """Single item detection should return exactly 1 item with name and quantity."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=openrouter_api_key,
        model=openrouter_model,
        single_item=True,
    )

    assert len(detected_items) == 1, "Expected exactly 1 item with single_item=True"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1, "Quantity must be at least 1"

