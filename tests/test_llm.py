from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from homebox_vision import DetectedItem, detect_items_with_openai, encode_image_to_data_uri

IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "test_detection.jpg"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output.txt"


def test_encode_image_to_data_uri_round_trip() -> None:
    uri = encode_image_to_data_uri(IMAGE_PATH)

    prefix = "data:image/jpg;base64,"
    assert uri.startswith(prefix)

    encoded = uri[len(prefix):]
    assert base64.b64decode(encoded) == IMAGE_PATH.read_bytes()


def test_detected_item_from_raw_items_handles_invalid_entries() -> None:
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


@pytest.mark.integration
def test_detect_items_with_openai_live() -> None:
    api_key = os.environ.get("HOMEBOX_VISION_OPENAI_API_KEY")
    if not api_key:
        pytest.skip(
            "HOMEBOX_VISION_OPENAI_API_KEY must be set to hit the OpenAI API for live tests."
        )

    model = os.getenv("HOMEBOX_VISION_OPENAI_MODEL", "gpt-4.1-mini")

    detected_items = detect_items_with_openai(image_path=IMAGE_PATH, api_key=api_key, model=model)

    print("Live OpenAI detection response:")
    output_lines = ["Live OpenAI detection response:"]
    for idx, item in enumerate(detected_items, start=1):
        summary = f"  {idx}. {item.name} (qty: {item.quantity})"
        details = item.description or "no description"
        line = f"{summary} - {details}"
        print(line)
        output_lines.append(line)

    payload = [asdict(item) for item in detected_items]
    payload_str = json.dumps(payload, indent=2)
    print("Full payload:", payload)
    output_lines.append(f"Full payload: {payload_str}")
    OUTPUT_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    assert detected_items, "Expected at least one detected item from OpenAI."
    for item in detected_items:
        assert item.name, "Detected item names should not be empty."
        assert item.quantity >= 1, "Detected quantities should be at least 1."
