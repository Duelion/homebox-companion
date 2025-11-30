"""LLM utilities for extracting Homebox items from images."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
from openai import OpenAI

from .client import DEFAULT_HEADERS, DEFAULT_TIMEOUT, DEMO_BASE_URL
from .models import DetectedItem


def encode_image_to_data_uri(image_path: Path) -> str:
    """Read the image and return a data URI suitable for OpenAI's vision API."""
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def encode_image_bytes_to_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Encode raw image bytes to a data URI suitable for OpenAI's vision API."""
    suffix = mime_type.split("/")[-1] if "/" in mime_type else "jpeg"
    payload = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def detect_items_with_openai(
    image_path: Path,
    api_key: str,
    model: str = "gpt-4o-mini",
    labels: list[dict[str, str]] | None = None,
) -> list[DetectedItem]:
    """Use an OpenAI vision model to detect items and quantities in an image."""
    data_uri = encode_image_to_data_uri(image_path)
    return _detect_items_from_data_uri(data_uri, api_key, model, labels)


def detect_items_from_bytes(
    image_bytes: bytes,
    api_key: str,
    mime_type: str = "image/jpeg",
    model: str = "gpt-4o-mini",
    labels: list[dict[str, str]] | None = None,
) -> list[DetectedItem]:
    """Use an OpenAI vision model to detect items from raw image bytes."""
    data_uri = encode_image_bytes_to_data_uri(image_bytes, mime_type)
    return _detect_items_from_data_uri(data_uri, api_key, model, labels)


def _detect_items_from_data_uri(
    data_uri: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    labels: list[dict[str, str]] | None = None,
) -> list[DetectedItem]:
    """Core detection logic using a data URI."""
    if labels is None:
        labels = []

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else "\n".join(
            f"- {label['name']} (id: {label['id']})"
            for label in labels
            if label.get("id")
        )
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
                            'JSON. Example format: {"items":[{"name":"hammer","quantity":2,'
                            '"description":"Steel head with wooden handle"}]}.'
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
    """Fetch the available labels from the Homebox demo API (unauthenticated)."""
    with httpx.Client(headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(f"{base_url}/labels")
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


async def fetch_demo_labels_async(
    base_url: str = DEMO_BASE_URL,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, str]]:
    """Async version: Fetch the available labels from the Homebox demo API."""
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)

    try:
        response = await client.get(f"{base_url}/labels")
        response.raise_for_status()
        labels = response.json()
    finally:
        if owns_client:
            await client.aclose()

    if not isinstance(labels, list):
        return []

    cleaned: list[dict[str, str]] = []
    for label in labels:
        label_id = str(label.get("id", "")).strip()
        label_name = str(label.get("name", "")).strip()
        if label_id and label_name:
            cleaned.append({"id": label_id, "name": label_name})
    return cleaned
