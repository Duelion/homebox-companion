from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from pprint import pformat

import pytest

from homebox_vision import DetectedItem, HomeboxClient, detect_items_with_openai

IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "test_detection.jpg"


@pytest.mark.integration
@pytest.mark.skipif(
    "HOMEBOX_VISION_OPENAI_API_KEY" not in os.environ,
    reason="HOMEBOX_VISION_OPENAI_API_KEY must be set for integration tests.",
)
def test_detect_items_with_openai_returns_items() -> None:
    api_key = os.environ["HOMEBOX_VISION_OPENAI_API_KEY"]
    model = os.getenv("HOMEBOX_VISION_OPENAI_MODEL", "gpt-5-mini")

    detected_items = detect_items_with_openai(image_path=IMAGE_PATH, api_key=api_key, model=model)

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
def test_create_item_in_demo_environment() -> None:
    # Use demo server for testing
    client = HomeboxClient(base_url="https://demo.homebox.software/api/v1")

    token = client.login("demo@example.com", "demo")
    locations = client.list_locations(token)
    assert locations, "The demo API should return at least one location."

    location_id = locations[0]["id"]
    item = DetectedItem(
        name=f"Integration item {datetime.now(UTC).isoformat(timespec='seconds')}",
        quantity=1,
        description="Created via integration test for the Homebox Vision Companion.",
        location_id=location_id,
    )

    created_items = client.create_items(token, [item])
    assert len(created_items) == 1, "Exactly one item should be created."

    created = created_items[0]
    assert created.get("id"), "Created item response should include an ID."
    assert created.get("name", "").startswith("Integration item")


@pytest.mark.integration
@pytest.mark.skipif(
    "HOMEBOX_VISION_OPENAI_API_KEY" not in os.environ,
    reason="HOMEBOX_VISION_OPENAI_API_KEY must be set for integration tests.",
)
def test_detect_and_create_items_from_image() -> None:
    api_key = os.environ["HOMEBOX_VISION_OPENAI_API_KEY"]
    model = os.getenv("HOMEBOX_VISION_OPENAI_MODEL", "gpt-5-mini")

    detected_items = detect_items_with_openai(image_path=IMAGE_PATH, api_key=api_key, model=model)
    assert detected_items, "Expected at least one detected item to create."

    # Use demo server for testing
    client = HomeboxClient(base_url="https://demo.homebox.software/api/v1")
    token = client.login("demo@example.com", "demo")
    locations = client.list_locations(token)
    assert locations, "The demo API should return at least one location."

    location_id = locations[0]["id"]
    items_to_create = [
        DetectedItem(
            name=item.name,
            quantity=item.quantity,
            description=item.description,
            location_id=location_id,
            label_ids=item.label_ids,
        )
        for item in detected_items[:2]
    ]

    created_items = client.create_items(token, items_to_create)

    assert len(created_items) == len(items_to_create)
    for created in created_items:
        assert created.get("id"), "Created item response should include an ID."
        assert created.get("locationId") == location_id
