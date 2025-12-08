"""Advanced item analysis from multiple images."""

from __future__ import annotations

from loguru import logger

from ...ai.openai import vision_completion
from ...ai.prompts import (
    FIELD_DEFAULTS,
    build_label_prompt,
    build_language_instruction,
    build_naming_rules,
)
from ...core.config import settings


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
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        Dictionary with extracted fields.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    language_instr = build_language_instruction(output_language)
    label_prompt = build_label_prompt(labels)
    naming_rules = build_naming_rules(field_preferences)

    # Merge field preferences with defaults
    instr = {**FIELD_DEFAULTS, **(field_preferences or {})}

    item_context = f"Item: '{item_name}'"
    if item_description:
        item_context += f" - {item_description}"

    system_prompt = (
        # 1. Role + task
        f"You are an inventory assistant analyzing images. {item_context}\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Critical instruction
        "Extract ALL visible details: serial numbers, model numbers, brand, "
        "price tags, condition issues. Only use what's visible.\n\n"
        # 4. Output schema
        "Return JSON with:\n"
        f"- name: string ({instr['name']})\n"
        f"- description: string ({instr['description']})\n"
        f"- serialNumber: string or null ({instr['serial_number']})\n"
        f"- modelNumber: string or null ({instr['model_number']})\n"
        f"- manufacturer: string or null ({instr['manufacturer']})\n"
        f"- purchasePrice: number or null ({instr['purchase_price']})\n"
        f"- notes: string or null ({instr['notes']})\n"
        "- labelIds: array of applicable label IDs\n\n"
        # 5. Naming
        f"{naming_rules}\n\n"
        # 6. Labels
        f"{label_prompt}"
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
