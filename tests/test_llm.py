"""Tests for vision detection and LLM functionality.

Integration tests require HBC_OPENAI_API_KEY to be set.
Run with: uv run pytest -m integration
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from homebox_companion import DetectedItem, detect_items_from_bytes, encode_image_to_data_uri

# ---------------------------------------------------------------------------
# Unit Tests (no API calls)
# ---------------------------------------------------------------------------


def test_encode_image_to_data_uri_returns_valid_data_uri(
    single_item_single_image_path: Path,
) -> None:
    """Test that encode_image_to_data_uri produces valid base64 data URI."""
    uri = encode_image_to_data_uri(single_item_single_image_path)

    # The function may use jpeg or jpg depending on optimization
    assert uri.startswith("data:image/jpeg;base64,") or uri.startswith("data:image/jpg;base64,")

    # Verify the base64 portion is valid
    prefix_len = len("data:image/jpeg;base64,")
    encoded = uri[prefix_len:]
    decoded = base64.b64decode(encoded)
    # The decoded bytes should be valid image data (starts with JPEG header)
    assert decoded[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_detected_item_from_raw_items_handles_invalid_entries() -> None:
    """Test that DetectedItem.from_raw_items filters and normalizes items correctly."""
    raw_items = [
        {
            "name": "   box  ",
            "quantity": "3",
            "description": "Cardboard",
            "labelIds": ["abc123", ""],
        },
        {"name": "", "quantity": 2},
        {"name": "Shelf", "quantity": "invalid", "label_ids": [123]},
    ]

    detected = DetectedItem.from_raw_items(raw_items)

    assert len(detected) == 2
    assert detected[0].name == "box"
    assert detected[0].quantity == 3
    assert detected[0].label_ids == ["abc123"]
    assert detected[1].name == "Shelf"
    assert detected[1].quantity == 1
    assert detected[1].label_ids == ["123"]


def test_detected_item_to_create_payload_basic() -> None:
    """Test to_create_payload returns correct format for Homebox API."""
    item = DetectedItem(
        name="Test Item",
        quantity=5,
        description="A test description",
        location_id="loc-123",
        label_ids=["label-1", "label-2"],
    )

    payload = item.to_create_payload()

    assert payload["name"] == "Test Item"
    assert payload["quantity"] == 5
    assert payload["description"] == "A test description"
    assert payload["locationId"] == "loc-123"
    assert payload["labelIds"] == ["label-1", "label-2"]


def test_detected_item_to_create_payload_truncates_long_values() -> None:
    """Test that name and description are truncated to API limits."""
    long_name = "x" * 300  # Over 255 limit
    long_desc = "y" * 1500  # Over 1000 limit

    item = DetectedItem(name=long_name, quantity=1, description=long_desc)
    payload = item.to_create_payload()

    assert len(payload["name"]) == 255
    assert len(payload["description"]) == 1000


def test_detected_item_to_create_payload_defaults() -> None:
    """Test default values when fields are missing or invalid."""
    item = DetectedItem(name="", quantity=0, description=None)
    payload = item.to_create_payload()

    assert payload["name"] == "Untitled item"
    assert payload["quantity"] == 1
    assert payload["description"] == "Created via Homebox Companion."
    assert "locationId" not in payload
    assert "labelIds" not in payload


def test_detected_item_get_extended_fields_payload() -> None:
    """Test get_extended_fields_payload returns correct fields."""
    item = DetectedItem(
        name="Tool",
        quantity=1,
        manufacturer="DeWalt",
        model_number="DCD771",
        serial_number="SN12345",
        purchase_price=99.99,
        purchase_from="Home Depot",
        notes="Good condition",
    )

    payload = item.get_extended_fields_payload()

    assert payload is not None
    assert payload["manufacturer"] == "DeWalt"
    assert payload["modelNumber"] == "DCD771"
    assert payload["serialNumber"] == "SN12345"
    assert payload["purchasePrice"] == 99.99
    assert payload["purchaseFrom"] == "Home Depot"
    assert payload["notes"] == "Good condition"


def test_detected_item_get_extended_fields_payload_returns_none_when_empty() -> None:
    """Test get_extended_fields_payload returns None when no extended fields."""
    item = DetectedItem(name="Basic Item", quantity=1)
    payload = item.get_extended_fields_payload()

    assert payload is None


def test_detected_item_has_extended_fields() -> None:
    """Test has_extended_fields returns correct boolean."""
    basic_item = DetectedItem(name="Basic", quantity=1)
    assert basic_item.has_extended_fields() is False

    item_with_manufacturer = DetectedItem(name="Tool", quantity=1, manufacturer="Bosch")
    assert item_with_manufacturer.has_extended_fields() is True

    item_with_price = DetectedItem(name="Tool", quantity=1, purchase_price=50.0)
    assert item_with_price.has_extended_fields() is True

    item_with_zero_price = DetectedItem(name="Tool", quantity=1, purchase_price=0)
    assert item_with_zero_price.has_extended_fields() is False


# ---------------------------------------------------------------------------
# Integration Tests (require HBC_OPENAI_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_item_single_image(
    api_key: str,
    model: str,
    single_item_single_image_path: Path,
) -> None:
    """Test detection of a single item from a single image.

    Uses single_item_single_image.jpg which should contain one distinct item.
    """
    image_bytes = single_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        single_item=True,
    )

    print("\n=== Single Item Single Image Detection ===")
    for idx, item in enumerate(detected_items, start=1):
        print(f"  {idx}. {item.name} (qty: {item.quantity}) - {item.description or 'no desc'}")
    print(f"Full payload: {json.dumps([asdict(item) for item in detected_items], indent=2)}")

    assert len(detected_items) == 1, "Expected exactly 1 item with single_item=True"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_item_multi_image(
    api_key: str,
    model: str,
    single_item_multi_image_1_path: Path,
    single_item_multi_image_2_path: Path,
) -> None:
    """Test multi-image analysis of a single item.

    Uses single_item_multi_image_1.jpg and single_item_multi_image_2.jpg which
    should show the same item from different angles.
    """
    primary_bytes = single_item_multi_image_1_path.read_bytes()
    additional_bytes = single_item_multi_image_2_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=primary_bytes,
        api_key=api_key,
        model=model,
        single_item=True,
        additional_images=[(additional_bytes, "image/jpeg")],
    )

    print("\n=== Single Item Multi-Image Detection ===")
    for idx, item in enumerate(detected_items, start=1):
        print(f"  {idx}. {item.name} (qty: {item.quantity}) - {item.description or 'no desc'}")
    print(f"Full payload: {json.dumps([asdict(item) for item in detected_items], indent=2)}")

    assert len(detected_items) == 1, "Expected exactly 1 item from multi-image analysis"
    assert detected_items[0].name, "Item must have a name"
    assert detected_items[0].quantity >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_item_single_image(
    api_key: str,
    model: str,
    multi_item_single_image_path: Path,
) -> None:
    """Test detection of multiple items from a single image.

    Uses multi_item_single_image.jpg which should contain multiple distinct items.
    """
    image_bytes = multi_item_single_image_path.read_bytes()

    detected_items = await detect_items_from_bytes(
        image_bytes=image_bytes,
        api_key=api_key,
        model=model,
        single_item=False,  # Allow multiple items
    )

    print("\n=== Multi-Item Single Image Detection ===")
    for idx, item in enumerate(detected_items, start=1):
        print(f"  {idx}. {item.name} (qty: {item.quantity}) - {item.description or 'no desc'}")
    print(f"Full payload: {json.dumps([asdict(item) for item in detected_items], indent=2)}")

    assert len(detected_items) > 1, "Expected multiple items from multi-item image"
    for item in detected_items:
        assert item.name, "Each item must have a name"
        assert item.quantity >= 1
