"""Integration tests for Homebox Companion.

These tests hit real APIs (Homebox demo server and OpenAI) and require:
- HBC_OPENAI_API_KEY environment variable for vision detection tests
- Network access to demo.homebox.software and api.openai.com

Run with: uv run pytest -m integration
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from pprint import pformat

import pytest

from homebox_companion import (
    HomeboxClient,
    ItemCreate,
    detect_items_from_bytes,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detect_items_returns_items(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Test that detect_items_from_bytes returns valid items from an image."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
    )

    print("Raw detected items from OpenAI:")
    for idx, item in enumerate(detected_items, start=1):
        summary = f"  {idx}. {item.name} (qty: {item.quantity})"
        details = item.description or "no description"
        print(f"{summary} - {details}")
    print("Full payload:\n" + pformat([asdict(item) for item in detected_items]))

    assert detected_items, "Expected at least one item from OpenAI vision response."
    for item in detected_items:
        assert item.name, "Detected items must include a name."
        assert item.quantity >= 1, "Quantity should be at least 1."
        assert item.description is None or isinstance(item.description, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_item_in_demo_environment(
    homebox_api_url: str,
) -> None:
    """Test creating an item in the Homebox demo environment."""
    async with HomeboxClient(base_url=homebox_api_url) as client:
        token = await client.login("demo@example.com", "demo")
        locations = await client.list_locations(token)
        assert locations, "The demo API should return at least one location."

        location_id = locations[0]["id"]
        item = ItemCreate(
            name=f"Integration item {datetime.now(UTC).isoformat(timespec='seconds')}",
            quantity=1,
            description="Created via integration test for Homebox Companion.",
            location_id=location_id,
        )

        created = await client.create_item(token, item)
        assert created.get("id"), "Created item response should include an ID."
        assert created.get("name", "").startswith("Integration item")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detect_and_create_items_from_image(
    api_key: str,
    model: str,
    homebox_api_url: str,
    single_item_single_image_path: Path,
) -> None:
    """Test the full flow: detect items from image and create them in Homebox."""
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
    )
    assert detected_items, "Expected at least one detected item to create."

    async with HomeboxClient(base_url=homebox_api_url) as client:
        token = await client.login("demo@example.com", "demo")
        locations = await client.list_locations(token)
        assert locations, "The demo API should return at least one location."

        location_id = locations[0]["id"]
        created_items = []

        # Create up to 2 items
        for item in detected_items[:2]:
            item_create = ItemCreate(
                name=item.name,
                quantity=item.quantity,
                description=item.description,
                location_id=location_id,
                label_ids=item.label_ids,
            )
            created = await client.create_item(token, item_create)
            created_items.append(created)

        assert len(created_items) == min(len(detected_items), 2)
        for created in created_items:
            assert created.get("id"), "Created item response should include an ID."
            # Location is returned as nested object, not locationId
            assert created.get("location", {}).get("id") == location_id
