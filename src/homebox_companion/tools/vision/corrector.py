"""Item correction using AI based on user feedback."""

from __future__ import annotations

from loguru import logger

from ...ai.openai import vision_completion
from ...ai.prompts import ITEM_SCHEMA, NAMING_RULES, build_label_prompt
from ...core.config import settings


async def correct_item_with_openai(
    image_data_uri: str,
    current_item: dict,
    correction_instructions: str,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
) -> list[dict]:
    """Correct or split an item based on user feedback.

    This function takes an item, its image, and user correction instructions
    to produce either a corrected single item or multiple separate items
    if the user indicates the AI made a grouping mistake.

    Args:
        image_data_uri: Data URI of the original image.
        current_item: The current item dict with name, quantity, description.
        correction_instructions: User's correction text explaining what's wrong
            or how to fix the detection. Examples:
            - "Actually these are soldering tips, not screws"
            - "These are two separate items: wire solder and paste solder"
            - "This is a multimeter, not a generic electronic device"
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest for items.

    Returns:
        List of corrected item dictionaries. Usually a single item, but may
        be multiple if the user indicated items should be split.
        Each item has: name, quantity, description, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Correcting item '{current_item.get('name')}' with user instructions")
    logger.debug(f"User correction: {correction_instructions}")

    label_prompt = build_label_prompt(labels)

    system_prompt = (
        "You are an inventory assistant helping to correct item detection errors. "
        "The user has provided feedback about a previously detected item. Your task "
        "is to:\n"
        "1. Understand the user's correction (they might be correcting the name, "
        "   saying items should be split, or providing more specific details)\n"
        "2. Re-analyze the image with this new understanding\n"
        "3. Return the corrected item(s)\n\n"
        f"{NAMING_RULES}\n\n"
        "CORRECTION RULES:\n"
        "- If the user says 'these are two separate items' or similar, return "
        "  multiple items in the array\n"
        "- If the user is just correcting the name/description, return a single item\n"
        "- Always look at the image to verify the user's feedback makes sense\n\n"
        "Return a JSON object with an `items` array.\n"
        f"{ITEM_SCHEMA}\n\n"
        + label_prompt
    )

    user_prompt = (
        f"I previously detected an item in this image as:\n"
        f"- Name: {current_item.get('name', 'Unknown')}\n"
        f"- Quantity: {current_item.get('quantity', 1)}\n"
        f"- Description: {current_item.get('description', 'None')}\n\n"
        f"The user has provided this correction/feedback:\n"
        f'"{correction_instructions}"\n\n'
        "Based on this feedback, re-analyze the image and provide the corrected "
        "item(s). If the user indicates these should be multiple separate items, "
        "return multiple items. Otherwise, return a single corrected item.\n\n"
        "Return only JSON."
    )

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=[image_data_uri],
        api_key=api_key,
        model=model,
    )

    items = parsed_content.get("items", [])

    # If the response is a single item dict (not in array), wrap it
    if not items and isinstance(parsed_content, dict) and "name" in parsed_content:
        items = [parsed_content]

    logger.info(f"Correction resulted in {len(items)} item(s)")
    for item in items:
        logger.debug(f"  Corrected item: {item.get('name')}, qty: {item.get('quantity', 1)}")

    return items

