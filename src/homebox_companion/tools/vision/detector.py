"""Item detection from images using LLM vision."""

from __future__ import annotations

from loguru import logger
from pydantic import TypeAdapter

from ...ai.images import encode_image_bytes_to_data_uri
from ...ai.llm import vision_completion
from ...core.config import settings
from .models import DetectedItem, DetectionResult
from .prompts import (
    build_detection_system_prompt,
    build_detection_user_prompt,
    build_discriminatory_system_prompt,
    build_discriminatory_user_prompt,
    build_grouped_detection_system_prompt,
    build_grouped_detection_user_prompt,
    build_multi_image_system_prompt,
)

# Module-level TypeAdapter for validating lists of DetectedItem from LLM output.
# Creating TypeAdapter is relatively expensive, so we do it once at import time.
_DETECTED_ITEMS_ADAPTER: TypeAdapter[list[DetectedItem]] = TypeAdapter(list[DetectedItem])


async def detect_items_from_bytes(
    image_bytes: bytes,
    api_key: str | None = None,
    mime_type: str = "image/jpeg",
    model: str | None = None,
    api_base: str | None = None,
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
    additional_images: list[tuple[bytes, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> DetectionResult:
    """Use LLM vision model to detect items from raw image bytes.

    Args:
        image_bytes: Raw image data for the primary image.
        api_key: LLM API key. Defaults to effective_llm_api_key.
        mime_type: MIME type of the primary image.
        model: Model name. Defaults to effective_llm_model.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
        labels: Optional list of Homebox labels to suggest for items.
        single_item: If True, treat everything in the image as a single item.
        extra_instructions: Optional user hint about what's in the image.
        extract_extended_fields: If True, also attempt to extract extended fields.
        additional_images: Optional list of (bytes, mime_type) tuples for
            additional images showing the same item(s) from different angles.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        DetectionResult containing detected items and token usage statistics.
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
        api_base=api_base,
        labels=labels,
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
    api_base: str | None = None,
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> DetectionResult:
    """Core detection logic supporting multiple images.

    Args:
        image_data_uris: List of base64-encoded image data URIs.
        api_key: LLM API key.
        model: LLM model name.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
        labels: Optional list of Homebox labels for item tagging.
        single_item: If True, treat everything as a single item.
        extra_instructions: User-provided hint about image contents.
        extract_extended_fields: If True, also extract manufacturer, etc.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        DetectionResult containing detected items and token usage statistics.
    """
    if not image_data_uris:
        return DetectionResult()

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
    result = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
        api_base=api_base,
        expected_keys=["items"],
    )

    # Validate LLM output with Pydantic
    items = _DETECTED_ITEMS_ADAPTER.validate_python(result.content.get("items", []))

    logger.info(f"Detected {len(items)} items from {len(image_data_uris)} image(s)")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, labels: {item.label_ids}")
        if extract_extended_fields and item.has_extended_fields():
            logger.debug(
                f"    Extended: manufacturer={item.manufacturer}, "
                f"model={item.model_number}, serial={item.serial_number}"
            )

    if result.usage:
        logger.debug(
            f"Token usage: {result.usage.prompt_tokens} prompt, "
            f"{result.usage.completion_tokens} completion, "
            f"{result.usage.total_tokens} total ({result.usage.provider})"
        )

    return DetectionResult(items=items, usage=result.usage)


async def discriminatory_detect_items(
    image_data_uris: list[str],
    api_key: str | None = None,
    model: str | None = None,
    api_base: str | None = None,
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> DetectionResult:
    """Re-detect items from images with more discriminatory instructions.

    This function re-analyzes images with specific instructions to be more
    discriminatory and separate items that might have been grouped together.

    Args:
        image_data_uris: List of data URI strings for each image.
        api_key: LLM API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
        labels: Optional list of Homebox labels to suggest for items.
        extract_extended_fields: If True, also extract extended fields.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        DetectionResult containing detected items and token usage statistics.
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
    user_prompt = build_discriminatory_user_prompt()

    result = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
        api_base=api_base,
        expected_keys=["items"],
    )

    items = DetectedItem.from_raw_items(result.content.get("items", []))

    logger.info(f"Discriminatory detection found {len(items)} items")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}")

    if result.usage:
        logger.debug(
            f"Token usage: {result.usage.prompt_tokens} prompt, "
            f"{result.usage.completion_tokens} completion, "
            f"{result.usage.total_tokens} total ({result.usage.provider})"
        )

    return DetectionResult(items=items, usage=result.usage)


async def grouped_detect_items(
    image_data_uris: list[str],
    api_key: str | None = None,
    model: str | None = None,
    api_base: str | None = None,
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
    extra_instructions: str | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> DetectionResult:
    """Detect items from multiple images with automatic grouping.

    This function analyzes all images together and automatically groups
    images that show the same physical item. It returns items with
    `image_indices` indicating which images show each item.

    Use this when:
    - Uploading multiple images that may show the same item from different angles
    - You want the AI to automatically determine which images go together
    - You don't know ahead of time how images should be grouped

    Args:
        image_data_uris: List of data URI strings for each image.
        api_key: LLM API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
        labels: Optional list of Homebox labels to suggest for items.
        extract_extended_fields: If True, also extract extended fields.
        extra_instructions: Optional user hint about image contents.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        DetectionResult containing detected items (each with `image_indices`
        indicating which images show that item) and token usage statistics.
    """
    api_key = api_key or settings.effective_llm_api_key
    model = model or settings.effective_llm_model

    image_count = len(image_data_uris)
    logger.info(f"Grouped detection with {image_count} images (auto-grouping)")
    logger.debug(f"Extract extended fields: {extract_extended_fields}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    system_prompt = build_grouped_detection_system_prompt(
        labels, extract_extended_fields, field_preferences, output_language
    )
    user_prompt = build_grouped_detection_user_prompt(
        image_count, extra_instructions, extract_extended_fields
    )

    result = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
        api_base=api_base,
        expected_keys=["items"],
    )

    items = DetectedItem.from_raw_items(result.content.get("items", []))

    logger.info(f"Grouped detection found {len(items)} unique items from {image_count} images")
    for item in items:
        indices_str = str(item.image_indices) if item.image_indices else "none"
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, images: {indices_str}")

    if result.usage:
        logger.debug(
            f"Token usage: {result.usage.prompt_tokens} prompt, "
            f"{result.usage.completion_tokens} completion, "
            f"{result.usage.total_tokens} total ({result.usage.provider})"
        )

    return DetectionResult(items=items, usage=result.usage)
