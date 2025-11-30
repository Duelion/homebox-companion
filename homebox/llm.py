"""LLM utilities for extracting Homebox items from images."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
from loguru import logger
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
    logger.debug(f"Starting item detection with model: {model}")

    if labels is None:
        labels = []

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else "IMPORTANT: You MUST assign appropriate labelIds from this list to each item. "
             "Select all labels that apply to each item. Available labels:\n" + "\n".join(
            f"- {label['name']} (id: {label['id']})"
            for label in labels
            if label.get("id")
        )
    )

    logger.debug(f"Labels provided: {len(labels)}")

    client = OpenAI(api_key=api_key)
    logger.debug("Calling OpenAI API...")

    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant for the Homebox API. "
                    "Return a single JSON object with an `items` array. Each item must "
                    "include: `name` (<=255 characters), integer `quantity` (>=1), "
                    "`description` (<=1000 characters) summarizing condition or "
                    "notable attributes, and `labelIds` (array of label IDs that match). "
                    "Combine identical objects into a single entry with the correct quantity. "
                    "Do not add extra commentary. Ignore background elements (floors, walls, "
                    "benches, shelves, packaging, shadows) and only count objects that are "
                    "the clear focus of the image.\n\n" + label_prompt
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List all distinct items that are the logical focus of this image "
                            "and ignore background objects or incidental surfaces. "
                            "For each item, include labelIds with matching label IDs. "
                            "Return only JSON. Example: "
                            '{"items":[{"name":"hammer","quantity":2,'
                            '"description":"Steel claw hammer","labelIds":["id1"]}]}.'
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    items = DetectedItem.from_raw_items(parsed_content.get("items", []))

    logger.info(f"Detected {len(items)} items")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, labels: {item.label_ids}")

    return items


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


def analyze_item_details_from_images(
    image_data_uris: list[str],
    item_name: str,
    item_description: str | None,
    api_key: str,
    model: str = "gpt-4o-mini",
    labels: list[dict[str, str]] | None = None,
) -> dict:
    """
    Analyze multiple images of an item to extract detailed information.

    Returns a dict with all possible Homebox item fields that can be determined
    from the images: serialNumber, modelNumber, manufacturer, purchasePrice,
    warrantyDetails, notes, etc.
    """
    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Item description: {item_description}")

    if labels is None:
        labels = []

    logger.debug(f"Available labels: {len(labels)}")

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else (
            "IMPORTANT: Assign appropriate labelIds from this list.\n"
            "Available labels:\n"
            + "\n".join(
                f"- {label['name']} (id: {label['id']})"
                for label in labels
                if label.get("id")
            )
        )
    )

    # Build image content for the message
    image_content = []
    for data_uri in image_data_uris:
        image_content.append({"type": "image_url", "image_url": {"url": data_uri}})

    logger.debug("Calling OpenAI API for advanced analysis...")
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant analyzing images of an item to extract "
                    "detailed information for the Homebox inventory system. The user has "
                    f"identified this item as: '{item_name}'"
                    + (f" with description: '{item_description}'" if item_description else "")
                    + ".\n\n"
                    "Analyze ALL provided images carefully. Look for:\n"
                    "- Serial numbers (on labels, stickers, engravings)\n"
                    "- Model numbers (on product labels, packaging)\n"
                    "- Manufacturer/brand name\n"
                    "- Any visible price tags or receipts\n"
                    "- Warranty information (stickers, cards)\n"
                    "- Condition notes (scratches, wear, damage)\n"
                    "- Any other relevant details\n\n"
                    "Return a single JSON object with these fields (omit fields you cannot "
                    "determine, use null for truly unknown values):\n"
                    "- name: string (improved name if you can determine a more specific one)\n"
                    "- description: string (detailed description based on all images)\n"
                    "- serialNumber: string or null\n"
                    "- modelNumber: string or null\n"
                    "- manufacturer: string or null\n"
                    "- purchasePrice: number or null (in local currency, just the number)\n"
                    "- notes: string (any additional observations)\n"
                    "- labelIds: array of label IDs that apply\n\n"
                    "Available labels:\n" + label_prompt
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze these images of the item and extract as much detail as "
                            "possible. Look carefully at all angles, labels, and markings. "
                            "Return only JSON with the fields described."
                        ),
                    },
                    *image_content,
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    logger.info(f"Advanced analysis complete. Fields found: {list(parsed_content.keys())}")
    logger.debug(f"Full result: {parsed_content}")

    return parsed_content
