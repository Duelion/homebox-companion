"""Advanced item analysis from multiple images."""

from __future__ import annotations

from loguru import logger

from ...ai.openai import vision_completion
from ...ai.prompts import NAMING_RULES, build_label_prompt
from ...core.config import settings


async def analyze_item_details_from_images(
    image_data_uris: list[str],
    item_name: str,
    item_description: str | None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
) -> dict:
    """Analyze multiple images of an item to extract detailed information.

    This function takes multiple images of the same item and uses AI to
    extract as much detail as possible, including serial numbers, model
    numbers, manufacturer, etc.

    Args:
        image_data_uris: List of data URI strings for each image.
        item_name: The name of the item being analyzed.
        item_description: Optional initial description of the item.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.

    Returns:
        Dictionary with extracted fields: name, description, serialNumber,
        modelNumber, manufacturer, purchasePrice, notes, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Item description: {item_description}")

    label_prompt = build_label_prompt(labels)

    system_prompt = (
        "You are an inventory assistant analyzing images of an item to extract "
        "detailed information for the Homebox inventory system. The user has "
        f"identified this item as: '{item_name}'"
        + (f" with description: '{item_description}'" if item_description else "")
        + ".\n\n"
        f"{NAMING_RULES}\n\n"
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
        "- name: string (Title Case, improved name if you can determine a more "
        "specific one, max 255 characters)\n"
        "- description: string (detailed description, no quantity, max 1000 chars)\n"
        "- serialNumber: string or null\n"
        "- modelNumber: string or null\n"
        "- manufacturer: string or null\n"
        "- purchasePrice: number or null (in local currency, just the number)\n"
        "- notes: string (any additional observations)\n"
        "- labelIds: array of label IDs that apply\n\n"
        + label_prompt
    )

    user_prompt = (
        "Analyze these images of the item and extract as much detail as "
        "possible. Look carefully at all angles, labels, and markings. "
        "Return only JSON with the fields described."
    )

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=image_data_uris,
        api_key=api_key,
        model=model,
    )

    logger.info(f"Advanced analysis complete. Fields found: {list(parsed_content.keys())}")
    logger.debug(f"Full result: {parsed_content}")

    return parsed_content









