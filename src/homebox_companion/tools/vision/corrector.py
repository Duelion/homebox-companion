"""Item correction using AI based on user feedback."""

from __future__ import annotations

from loguru import logger

from ...ai.llm import vision_completion
from ...ai.prompts import (
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_language_instruction,
    build_naming_examples,
)



async def correct_item(
    image_data_uri: str,
    current_item: dict,
    correction_instructions: str,
    labels: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> list[dict]:
    """Correct or split an item based on user feedback.

    This function takes an item, its image, and user correction instructions
    to produce either a corrected single item or multiple separate items
    if the user indicates the AI made a grouping mistake.

    Args:
        image_data_uri: Data URI of the original image.
        current_item: The current item dict with name, quantity, description.
        correction_instructions: User's correction text explaining what's wrong
            or how to fix the detection.
        labels: Optional list of Homebox labels to suggest for items.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        List of corrected item dictionaries.
    """

    logger.info(f"Correcting item '{current_item.get('name')}' with user instructions")
    logger.debug(f"User correction: {correction_instructions}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    # Ensure field_preferences is a dict (empty dict if None)
    field_preferences = field_preferences or {}

    # Build schemas with customizations
    language_instr = build_language_instruction(output_language)
    item_schema = build_item_schema(field_preferences)
    extended_schema = build_extended_fields_schema(field_preferences)
    naming_examples = build_naming_examples(field_preferences)
    label_prompt = build_label_prompt(labels)

    system_prompt = (
        # 1. Role
        "You are an inventory assistant correcting item detection errors. "
        "Return a JSON object with an `items` array.\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Critical correction rules
        "CORRECTION RULES:\n"
        "- 'separate items' → return multiple items in array\n"
        "- Name/description fix → return single corrected item\n"
        "- Extract price→purchasePrice, store→purchaseFrom, brand→manufacturer\n"
        "- Always verify against the image\n\n"
        # 4. Schema
        f"{item_schema}\n"
        f"{extended_schema}\n\n"
        # 5. Naming
        f"{naming_examples}\n\n"
        # 6. Labels
        f"{label_prompt}"
    )

    # Build current item summary
    current_summary = f"Current: {current_item.get('name', 'Unknown')} (qty: {current_item.get('quantity', 1)})"
    if current_item.get("manufacturer"):
        current_summary += f", mfr: {current_item.get('manufacturer')}"

    user_prompt = (
        f"{current_summary}\n\n"
        f'User correction: "{correction_instructions}"\n\n'
        "Apply the correction and return JSON with corrected item(s)."
    )

    parsed_content = await vision_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_data_uris=[image_data_uri],
        expected_keys=["items"],
    )

    items = parsed_content.get("items", [])

    # If the response is a single item dict (not in array), wrap it
    if not items and isinstance(parsed_content, dict) and "name" in parsed_content:
        items = [parsed_content]

    logger.info(f"Correction resulted in {len(items)} item(s)")
    for item in items:
        logger.debug(f"  Corrected item: {item.get('name')}, qty: {item.get('quantity', 1)}")

    return items
