"""Item correction using AI based on user feedback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from ...ai.llm import vision_completion
from ...ai.prompts import (
    build_custom_fields_schema,
    build_extended_fields_schema,
    build_item_schema,
    build_language_instruction,
    build_naming_examples,
    build_tag_prompt,
)
from .models import DetectedItem, get_items_adapter

if TYPE_CHECKING:
    from ...core.persistent_settings import CustomFieldDefinition


async def correct_item(
    image_data_uri: str,
    current_item: dict,
    correction_instructions: str,
    tags: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
    custom_fields: list[CustomFieldDefinition] | None = None,
) -> list[DetectedItem]:
    """Correct or split an item based on user feedback.

    This function takes an item, its image, and user correction instructions
    to produce either a corrected single item or multiple separate items
    if the user indicates the AI made a grouping mistake.

    Args:
        image_data_uri: Data URI of the original image.
        current_item: The current item dict with name, quantity, description.
        correction_instructions: User's correction text explaining what's wrong
            or how to fix the detection.
        tags: Optional list of Homebox tags to suggest for items.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).
        custom_fields: Optional custom field definitions for AI extraction.

    Returns:
        List of corrected DetectedItem instances (validated through Pydantic).
    """

    logger.info(f"Correcting item '{current_item.get('name')}' with user instructions")
    logger.debug(f"User correction: {correction_instructions}")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")
    logger.debug(f"Custom fields: {len(custom_fields) if custom_fields else 0}")

    # Ensure field_preferences is a dict (empty dict if None)
    field_preferences = field_preferences or {}

    # Build schemas with customizations
    language_instr = build_language_instruction(output_language)
    item_schema = build_item_schema(field_preferences)
    extended_schema = build_extended_fields_schema(field_preferences)
    custom_fields_schema = build_custom_fields_schema(custom_fields or [])
    naming_examples = build_naming_examples(field_preferences)
    tag_prompt = build_tag_prompt(tags)

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
        f"{extended_schema}\n"
        # 5. Custom fields (if any)
        f"{custom_fields_schema}\n\n"
        # 6. Naming
        f"{naming_examples}\n\n"
        # 7. Tags
        f"{tag_prompt}"
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

    raw_items = parsed_content.get("items", [])

    # If the response is a single item dict (not in array), wrap it
    if not raw_items and isinstance(parsed_content, dict) and "name" in parsed_content:
        raw_items = [parsed_content]

    # Validate through Pydantic (same dynamic model as detector)
    adapter = get_items_adapter(custom_fields)
    items = adapter.validate_python(raw_items)

    logger.info(f"Correction resulted in {len(items)} item(s)")
    for item in items:
        logger.debug(f"  Corrected item: {item.name}, qty: {item.quantity}")

    return items
