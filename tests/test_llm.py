"""Tests for the vision/AI detection module."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

import homebox
from homebox import Item, VisionClient, detect, encode_image
from homebox.vision import detect_items_with_openai

IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "test_detection.jpg"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output.txt"


def test_encode_image_round_trip() -> None:
    """Test that encode_image produces valid base64 data URI."""
    uri = encode_image(IMAGE_PATH)

    prefix = "data:image/jpg;base64,"
    assert uri.startswith(prefix)

    encoded = uri[len(prefix):]
    assert base64.b64decode(encoded) == IMAGE_PATH.read_bytes()


def test_vision_client_encode_image_static() -> None:
    """Test that VisionClient.encode_image works as a static method."""
    uri = VisionClient.encode_image(IMAGE_PATH)

    assert uri.startswith("data:image/jpg;base64,")


def test_item_from_list_handles_invalid_entries() -> None:
    """Test that Item.from_list filters and normalizes invalid data."""
    raw_items = [
        {
            "name": "   box  ",
            "quantity": "3",
            "description": "Cardboard",
            "labelIds": ["abc123", ""],
        },
        {"name": "", "quantity": 2},  # Should be filtered out
        {"name": "Shelf", "quantity": "invalid", "label_ids": [123]},
    ]

    detected = Item.from_list(raw_items)

    assert len(detected) == 2
    assert detected[0].name == "box"
    assert detected[0].quantity == 3
    assert detected[0].label_ids == ["abc123"]
    assert detected[1].name == "Shelf"
    assert detected[1].quantity == 1
    assert detected[1].label_ids == ["123"]


def test_vision_client_requires_api_key() -> None:
    """Ensure VisionClient raises error when API key is missing."""
    original_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        client = VisionClient()
        with pytest.raises(ValueError, match="OpenAI API key required"):
            _ = client.api_key
    finally:
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key


def test_vision_client_accepts_api_key_from_env() -> None:
    """Ensure VisionClient reads API key from environment."""
    original_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key-from-env"
    try:
        client = VisionClient()
        assert client.api_key == "test-key-from-env"
    finally:
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)


def test_vision_client_prefers_explicit_api_key() -> None:
    """Ensure explicit API key takes precedence over env var."""
    original_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "env-key"
    try:
        client = VisionClient(api_key="explicit-key")
        assert client.api_key == "explicit-key"
    finally:
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)


def test_detect_requires_api_key() -> None:
    """Ensure detect() raises error when API key is missing."""
    original_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="OpenAI API key required"):
            detect(IMAGE_PATH)
    finally:
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key


def test_vision_client_build_label_prompt() -> None:
    """Test the label prompt builder."""
    from homebox import Label

    client = VisionClient(api_key="test")

    # Empty labels
    prompt = client._build_label_prompt([])
    assert "No labels are available" in prompt

    # With labels
    labels = [Label(id="1", name="Tools"), Label(id="2", name="Kitchen")]
    prompt = client._build_label_prompt(labels)
    assert "Tools (id: 1)" in prompt
    assert "Kitchen (id: 2)" in prompt


@pytest.mark.integration
def test_detect_live() -> None:
    """Test detect() with real OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY must be set for live tests.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Test using the new simple API
    items = detect(IMAGE_PATH, api_key=api_key, model=model)

    print("Live OpenAI detection response:")
    output_lines = ["Live OpenAI detection response:"]
    for idx, item in enumerate(items, start=1):
        summary = f"  {idx}. {item.name} (qty: {item.quantity})"
        details = item.description or "no description"
        line = f"{summary} - {details}"
        print(line)
        output_lines.append(line)

    payload = [asdict(item) for item in items]
    payload_str = json.dumps(payload, indent=2)
    print("Full payload:", payload)
    output_lines.append(f"Full payload: {payload_str}")
    OUTPUT_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    assert items, "Expected at least one detected item from OpenAI."
    for item in items:
        assert item.name, "Detected item names should not be empty."
        assert item.quantity >= 1, "Detected quantities should be at least 1."


@pytest.mark.integration
def test_vision_client_detect_live() -> None:
    """Test VisionClient.detect() with real OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY must be set for live tests.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Test using the class-based client
    vision = VisionClient(api_key=api_key, model=model)
    items = vision.detect(IMAGE_PATH)

    print("Live OpenAI detection response (VisionClient):")
    for idx, item in enumerate(items, start=1):
        summary = f"  {idx}. {item.name} (qty: {item.quantity})"
        details = item.description or "no description"
        print(f"{summary} - {details}")

    assert items, "Expected at least one detected item from OpenAI."
    for item in items:
        assert item.name, "Detected item names should not be empty."
        assert item.quantity >= 1, "Detected quantities should be at least 1."


@pytest.mark.integration
def test_vision_client_fetch_labels_live() -> None:
    """Test VisionClient.labels() with real Homebox API."""
    vision = VisionClient(api_key="unused-for-labels")
    labels = vision.labels()

    print(f"Fetched {len(labels)} labels from Homebox demo API")
    for label in labels[:5]:
        print(f"  - {label.name} (id: {label.id})")

    assert isinstance(labels, list)


@pytest.mark.integration
def test_vision_client_labels_caching() -> None:
    """Test that VisionClient caches labels."""
    vision = VisionClient(api_key="unused-for-labels")

    # First call fetches
    labels1 = vision.labels()
    # Second call returns cached
    labels2 = vision.labels()

    assert labels1 is labels2  # Same object (cached)

    # Force refresh
    labels3 = vision.labels(refresh=True)
    assert labels3 is not labels1  # New object


# Backwards compatibility tests

@pytest.mark.integration
def test_legacy_detect_items_with_openai() -> None:
    """Test backwards-compatible detect_items_with_openai()."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY must be set for live tests.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    items = detect_items_with_openai(IMAGE_PATH, api_key=api_key, model=model)

    assert items, "Expected at least one detected item."
    for item in items:
        assert item.name
        assert item.quantity >= 1


@pytest.mark.integration
def test_legacy_homebox_llm_client() -> None:
    """Test backwards-compatible HomeboxLLMClient."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY must be set for live tests.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Test using the legacy class
    client = homebox.HomeboxLLMClient(api_key=api_key, model=model)
    items = client.detect_items(IMAGE_PATH)

    assert items, "Expected at least one detected item."
    for item in items:
        assert item.name
        assert item.quantity >= 1
