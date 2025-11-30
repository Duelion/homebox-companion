"""Integration tests that hit real APIs."""
from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from pprint import pformat

import pytest

from homebox import Item, Session, detect

IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "test_detection.jpg"


@pytest.mark.integration
@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY must be set for integration tests.",
)
def test_detect_returns_items() -> None:
    """Test that detect() returns valid items from an image."""
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    items = detect(IMAGE_PATH, api_key=api_key, model=model)

    print("Raw detected items from OpenAI:")
    for idx, item in enumerate(items, start=1):
        summary = f"  {idx}. {item.name} (qty: {item.quantity})"
        details = item.description or "no description"
        print(f"{summary} - {details}")
    print("Full payload:\n" + pformat([asdict(item) for item in items]))

    assert items, "Expected at least one item from OpenAI vision response."
    for item in items:
        assert item.name, "Detected items must include a name."
        assert item.quantity >= 1, "Quantity should be at least 1."
        assert item.description is None or isinstance(item.description, str)


@pytest.mark.integration
def test_session_create_item() -> None:
    """Test creating an item using the Session class."""
    with Session() as hb:
        locations = hb.locations()
        assert locations, "The demo API should return at least one location."

        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item = hb.create_item(
            f"Integration item {timestamp}",
            quantity=1,
            description="Created via integration test for the Homebox demo API.",
            location=locations[0],
        )

        assert item.id, "Created item should have an ID."
        assert item.name.startswith("Integration item")
        print(f"Created item: {item.name} (id: {item.id})")


@pytest.mark.integration
def test_session_list_locations() -> None:
    """Test listing locations using Session."""
    with Session() as hb:
        locations = hb.locations()

        assert locations, "Demo API should have at least one location."
        print(f"Found {len(locations)} locations:")
        for loc in locations[:5]:
            print(f"  - {loc.name} (id: {loc.id})")


@pytest.mark.integration
def test_session_list_labels() -> None:
    """Test listing labels using Session."""
    with Session() as hb:
        labels = hb.labels()

        print(f"Found {len(labels)} labels:")
        for label in labels[:5]:
            print(f"  - {label.name} (id: {label.id})")


@pytest.mark.integration
@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY must be set for integration tests.",
)
def test_detect_and_create_items() -> None:
    """Test end-to-end: detect items in image and create them in Homebox."""
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Detect items in image
    detected_items = detect(IMAGE_PATH, api_key=api_key, model=model)
    assert detected_items, "Expected at least one detected item to create."

    # Create items in Homebox
    with Session() as hb:
        locations = hb.locations()
        assert locations, "The demo API should return at least one location."

        location = locations[0]

        # Create first 2 detected items
        created_items = []
        for detected in detected_items[:2]:
            item = hb.create_item(
                detected.name,
                quantity=detected.quantity,
                description=detected.description,
                location=location,
                labels=None,
            )
            created_items.append(item)
            print(f"Created: {item.name} (id: {item.id})")

        assert len(created_items) == min(2, len(detected_items))
        for item in created_items:
            assert item.id, "Created item should have an ID."


# Backwards compatibility tests

@pytest.mark.integration
def test_legacy_client_create_item() -> None:
    """Test backwards-compatible HomeboxDemoClient."""
    from homebox import DetectedItem, HomeboxDemoClient

    client = HomeboxDemoClient()

    token = client.login()
    locations = client.list_locations(token)
    assert locations, "The demo API should return at least one location."

    location_id = locations[0]["id"]
    item = DetectedItem(
        name=f"Legacy item {datetime.now(UTC).isoformat(timespec='seconds')}",
        quantity=1,
        description="Created via legacy integration test.",
        location_id=location_id,
    )

    created_items = client.create_items(token, [item])
    assert len(created_items) == 1, "Exactly one item should be created."

    created = created_items[0]
    assert created.get("id"), "Created item response should include an ID."
    assert created.get("name", "").startswith("Legacy item")


@pytest.mark.integration
@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY must be set for integration tests.",
)
def test_legacy_detect_and_create() -> None:
    """Test backwards-compatible workflow."""
    from homebox import HomeboxDemoClient, detect_items_with_openai

    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    detected_items = detect_items_with_openai(IMAGE_PATH, api_key=api_key, model=model)
    assert detected_items, "Expected at least one detected item."

    client = HomeboxDemoClient()
    token = client.login()
    locations = client.list_locations(token)
    assert locations, "Demo API should return at least one location."

    location_id = locations[0]["id"]

    # Add location_id to items
    items_to_create = [
        Item(
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
        assert created.get("id"), "Created item should include an ID."
        assert created.get("locationId") == location_id
