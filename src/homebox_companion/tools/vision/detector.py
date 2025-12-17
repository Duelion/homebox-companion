"""Item detection from images using LLM vision."""

from __future__ import annotations

from loguru import logger

from ...ai.images import encode_image_bytes_to_data_uri
from ...ai.llm import vision_completion
from ...core.config import settings
from .models import DetectedItem
from .prompts import (
    build_detection_system_prompt,
    build_detection_user_prompt,
    build_discriminatory_system_prompt,
    build_discriminatory_user_prompt,
    build_multi_image_system_prompt,
)


async def detect_items_from_bytes(
    image_bytes: bytes,
    api_key: str | None = None,
    mime_type: str = "image/jpeg",
    model: str | None = None,
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
        api_key: LLM API key. Defaults to effective_llm_api_key.
        mime_type: MIME type of the primary image.
        model: Model name. Defaults to effective_llm_model.
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
        api_key or settings.effective_llm_api_key,
        model or settings.effective_llm_model,
        labels,
        single_item=single_item,
        extra_instructions=extra_instructions,
        extract_extended_fields=extract_extended_fields,
        field_preferences=field_preferences,
        output_language=output_language,
    )


async def _detect_items_from_data_uris(
    image_data_uris: list[str],
    api_key: str,
    model: str,
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
        api_key: OpenAI API key.
        model: OpenAI model name.
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
    logger.debug(f"Model: {model}, Single item: {single_item}")
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

    user_prompt = build_detection_user_prompt(
        extra_instructions, extract_extended_fields, multi_image, single_item
    )

    # Call LLM
    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
        expected_keys=["items"],
    )

    items = DetectedItem.from_raw_items(parsed_content.get("items", []))

    logger.info(f"Detected {len(items)} items from {len(image_data_uris)} image(s)")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, labels: {item.label_ids}")
        if extract_extended_fields and item.has_extended_fields():
            logger.debug(
                f"    Extended: manufacturer={item.manufacturer}, "
                f"model={item.model_number}, serial={item.serial_number}"
            )

    return items


async def discriminatory_detect_items(
    image_data_uris: list[str],
    previous_merged_item: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> list[DetectedItem]:
    """Re-detect items from images with more discriminatory instructions.

    This function is used when a user "unmerges" items - it re-analyzes
    the images with specific instructions to be more discriminatory and
    separate items that might have been grouped together previously.

    Args:
        image_data_uris: List of data URI strings for each image.
        previous_merged_item: The previously merged item dict for context.
        api_key: LLM API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        labels: Optional list of Homebox labels to suggest for items.
        extract_extended_fields: If True, also extract extended fields.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        List of detected items, ideally more specific/separated than before.
    """
    api_key = api_key or settings.effective_llm_api_key
    model = model or settings.effective_llm_model

    logger.info(f"Discriminatory detection with {len(image_data_uris)} images")
    logger.debug(f"Extract extended fields: {extract_extended_fields}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    system_prompt = build_discriminatory_system_prompt(
        labels, extract_extended_fields, field_preferences, output_language
    )
    user_prompt = build_discriminatory_user_prompt(previous_merged_item)

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
        expected_keys=["items"],
    )

    items = DetectedItem.from_raw_items(parsed_content.get("items", []))

    logger.info(f"Discriminatory detection found {len(items)} items")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}")

    return items
