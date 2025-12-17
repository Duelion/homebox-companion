"""Advanced item analysis from multiple images."""

from __future__ import annotations

from loguru import logger

from ...ai.llm import vision_completion
from ...core.config import settings
from .prompts import build_analysis_system_prompt


async def analyze_item_details_from_images(
    image_data_uris: list[str],
    item_name: str,
    item_description: str | None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> dict:
    """Analyze multiple images of an item to extract detailed information.

    Args:
        image_data_uris: List of data URI strings for each image.
        item_name: The name of the item being analyzed.
        item_description: Optional initial description of the item.
        api_key: LLM API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        labels: Optional list of Homebox labels to suggest.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        Dictionary with extracted fields.
    """
    api_key = api_key or settings.effective_llm_api_key
    model = model or settings.effective_llm_model

    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    # Build system prompt using the consolidated builder
    system_prompt = build_analysis_system_prompt(
        item_name=item_name,
        item_description=item_description,
        labels=labels,
        field_preferences=field_preferences,
        output_language=output_language,
    )

    user_prompt = (
        "Analyze all images. Look at labels, stickers, engravings for details. "
        "Return only JSON."
    )

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
    )

    logger.info(f"Analysis complete. Fields: {list(parsed_content.keys())}")

    return parsed_content
