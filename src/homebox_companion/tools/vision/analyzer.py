"""Advanced item analysis from multiple images."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from ...ai.llm import vision_completion
from .models import DetectedItem, get_single_item_adapter
from .prompts import build_analysis_system_prompt

if TYPE_CHECKING:
    from ...core.persistent_settings import CustomFieldDefinition


async def analyze_item_details_from_images(
    image_data_uris: list[str],
    item_name: str,
    item_description: str | None,
    tags: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
    custom_fields: list[CustomFieldDefinition] | None = None,
) -> DetectedItem:
    """Analyze multiple images of an item to extract detailed information.

    Args:
        image_data_uris: List of data URI strings for each image.
        item_name: The name of the item being analyzed.
        item_description: Optional initial description of the item.
        tags: Optional list of Homebox tags to suggest.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).
        custom_fields: Optional list of custom field definitions.

    Returns:
        A validated DetectedItem with extracted fields.
    """

    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    # Build system prompt using the consolidated builder
    system_prompt = build_analysis_system_prompt(
        item_name=item_name,
        item_description=item_description,
        tags=tags,
        field_preferences=field_preferences,
        output_language=output_language,
        custom_fields=custom_fields,
    )

    user_prompt = "Analyze all images. Look at labels, stickers, engravings for details. Return only JSON."

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
    )

    # Validate through Pydantic (same dynamic model as detector)
    adapter = get_single_item_adapter(custom_fields)
    item = adapter.validate_python(parsed_content)

    logger.info(f"Analysis complete. Fields: {list(item.model_fields.keys())}")

    return item
