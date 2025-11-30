from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from homebox import DetectedItem, HomeboxDemoClient, detect_items_with_openai

IMAGE_PATH = Path(__file__).resolve().parent.parent / "image.jpg"


@pytest.mark.integration
@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY must be set to hit the OpenAI API for integration tests.",
)
def test_detect_items_with_openai_returns_items() -> None:
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    detected_items = detect_items_with_openai(image_path=IMAGE_PATH, api_key=api_key, model=model)

    assert detected_items, "Expected at least one item from OpenAI vision response."
    for item in detected_items:
        assert item.name, "Detected items must include a name."
        assert item.quantity >= 1, "Quantity should be at least 1."
        assert item.description is None or isinstance(item.description, str)


@pytest.mark.integration
def test_create_item_in_demo_environment() -> None:
    client = HomeboxDemoClient()

    token = client.login()
    locations = client.list_locations(token)
    assert locations, "The demo API should return at least one location."

    location_id = locations[0]["id"]
    item = DetectedItem(
        name=f"Integration item {datetime.now(UTC).isoformat(timespec='seconds')}",
        quantity=1,
        description="Created via integration test for the Homebox demo API.",
        location_id=location_id,
    )

    created_items = client.create_items(token, [item])
    assert len(created_items) == 1, "Exactly one item should be created."

    created = created_items[0]
    assert created.get("id"), "Created item response should include an ID."
    assert created.get("name", "").startswith("Integration item")
