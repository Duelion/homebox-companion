"""LLM utilities for extracting Homebox items from images."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import requests
from openai import OpenAI

from .client import DEFAULT_HEADERS, DEMO_BASE_URL
from .models import DetectedItem


def encode_image_to_data_uri(image_path: Path) -> str:
    """Read the image and return a data URI suitable for OpenAI's vision API."""

    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def detect_items_with_openai(
    image_path: Path,
    api_key: str,
    model: str = "gpt-5-mini",
) -> list[DetectedItem]:
    """Use an OpenAI vision model to detect items and quantities in an image."""

    data_uri = encode_image_to_data_uri(image_path)
    labels = fetch_demo_labels()
    label_prompt = "No labels are available; omit labelIds." if not labels else "\n".join(
        f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id")
    )

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant for the Homebox API. "
                    "Return a single JSON object with an `items` array. Each item must "
                    "include: `name` (<=255 characters), integer `quantity` (>=1), and "
                    "optional `description` (<=1000 characters) summarizing condition or "
                    "notable attributes. Combine identical objects into a single entry "
                    "with the correct quantity. Do not add extra commentary. Ignore "
                    "background elements (floors, walls, benches, shelves, packaging, "
                    "labels, shadows) and only count objects that are the clear focus of "
                    "the image. When possible, set `labelIds` using the exact IDs from "
                    "the available labels list. If none match, omit `labelIds`. Available "
                    "labels:\n" + label_prompt
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List all distinct items that are the logical focus of this image "
                            "and ignore background objects or incidental surfaces. Return only "
                            "JSON. Example format: {\"items\":[{\"name\":\"hammer\",\"quantity\":2,"
                            "\"description\":\"Steel head with wooden handle\"}]}."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    return DetectedItem.from_raw_items(parsed_content.get("items", []))


def fetch_demo_labels(base_url: str = DEMO_BASE_URL) -> list[dict[str, str]]:
    """Fetch the available labels from the Homebox demo API."""

    response = requests.get(
        f"{base_url}/labels",
        headers=DEFAULT_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    labels = response.json()
    if not isinstance(labels, list):
        return []

    cleaned: list[dict[str, str]] = []
    for label in labels:
        label_id = str(label.get("id", "")).strip()
        label_name = str(label.get("name", "")).strip()
        if label_id and label_name:
            cleaned.append({"id": label_id, "name": label_name})
    return cleaned
