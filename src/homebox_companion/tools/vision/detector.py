"""Item detection from images using LLM vision."""

from __future__ import annotations

from loguru import logger
from pydantic import TypeAdapter

from ...ai.images import encode_image_bytes_to_data_uri
from ...ai.llm import vision_completion

from .models import DetectedItem
from .prompts import (
    build_detection_system_prompt,
    build_detection_user_prompt,
    build_multi_image_system_prompt,
)

# Module-level TypeAdapter for validating lists of DetectedItem from LLM output.
# Creating TypeAdapter is relatively expensive, so we do it once at import time.
_DETECTED_ITEMS_ADAPTER: TypeAdapter[list[DetectedItem]] = TypeAdapter(list[DetectedItem])


async def detect_items_from_bytes(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
    additional_images: list[tuple[bytes, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> list[DetectedItem]:
    """Use LLM vision model to detect items from raw image bytes.

    Args:
        image_bytes: Raw image data for the primary image.
        mime_type: MIME type of the primary image.
        labels: Optional list of Homebox labels to suggest for items.
        single_item: If True, treat everything in the image as a single item.
        extra_instructions: Optional user hint about what's in the image.
        extract_extended_fields: If True, also attempt to extract extended fields.
        additional_images: Optional list of (bytes, mime_type) tuples for
            additional images showing the same item(s) from different angles.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        List of detected items with quantities, descriptions, and optionally
        extended fields when extract_extended_fields is True.
    """
    # Build list of all image data URIs
    image_data_uris = [encode_image_bytes_to_data_uri(image_bytes, mime_type)]

    if additional_images:
        for add_bytes, add_mime in additional_images:
            image_data_uris.append(encode_image_bytes_to_data_uri(add_bytes, add_mime))

    return await _detect_items_from_data_uris(
        image_data_uris,
        labels,
        single_item=single_item,
        extra_instructions=extra_instructions,
        extract_extended_fields=extract_extended_fields,
        field_preferences=field_preferences,
        output_language=output_language,
    )


async def _detect_items_from_data_uris(
    image_data_uris: list[str],
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> list[DetectedItem]:
    """Core detection logic supporting multiple images.

    Args:
        image_data_uris: List of base64-encoded image data URIs.
        labels: Optional list of Homebox labels for item tagging.
        single_item: If True, treat everything as a single item.
        extra_instructions: User-provided hint about image contents.
        extract_extended_fields: If True, also extract manufacturer, etc.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).
    """
    if not image_data_uris:
        return []

    multi_image = len(image_data_uris) > 1

    logger.debug(f"Starting {'multi-image' if multi_image else 'single-image'} detection")
    logger.debug(f"Single item: {single_item}")
    logger.debug(f"Extract extended fields: {extract_extended_fields}")
    logger.debug(f"Labels provided: {len(labels) if labels else 0}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    # Build prompts
    if multi_image:
        system_prompt = build_multi_image_system_prompt(
            labels, single_item, extract_extended_fields, field_preferences, output_language
        )
    else:
        system_prompt = build_detection_system_prompt(
            labels, single_item, extract_extended_fields, field_preferences, output_language
        )

    user_prompt = build_detection_user_prompt(extra_instructions, extract_extended_fields, multi_image, single_item)

    # Call LLM
    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        expected_keys=["items"],
    )

    # Validate LLM output with Pydantic
    items = _DETECTED_ITEMS_ADAPTER.validate_python(parsed_content.get("items", []))

    logger.info(f"Detected {len(items)} items from {len(image_data_uris)} image(s)")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, labels: {item.label_ids}")
        if extract_extended_fields and item.has_extended_fields():
            logger.debug(
                f"    Extended: manufacturer={item.manufacturer}, "
                f"model={item.model_number}, serial={item.serial_number}"
            )

    return items
