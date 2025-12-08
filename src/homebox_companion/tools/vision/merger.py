"""Item merging using AI."""

from __future__ import annotations

from loguru import logger

from ...ai.openai import vision_completion
from ...ai.prompts import build_label_prompt, build_language_instruction, build_naming_rules
from ...core.config import settings


async def merge_items_with_openai(
    items: list[dict],
    image_data_uris: list[str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> dict:
    """Merge multiple similar items into a single consolidated item using AI.

    Args:
        items: List of item dictionaries with name, quantity, description fields.
        image_data_uris: Optional list of image data URIs for context.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for AI output (default: English).

    Returns:
        Dictionary with merged item fields: name, quantity, description, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Merging {len(items)} items with AI")
    logger.debug(f"Field preferences: {len(field_preferences) if field_preferences else 0}")
    logger.debug(f"Output language: {output_language or 'English (default)'}")

    # Format items compactly
    items_text = ", ".join(
        f"{item.get('name', '?')} (x{item.get('quantity', 1)})"
        for item in items
    )

    language_instr = build_language_instruction(output_language)
    label_prompt = build_label_prompt(labels)
    naming_rules = build_naming_rules(field_preferences)

    # Get field customizations or defaults
    name_instr = (
        field_preferences.get("name")
        if field_preferences and field_preferences.get("name")
        else "Title Case, consolidated name"
    )
    desc_instr = (
        field_preferences.get("description")
        if field_preferences and field_preferences.get("description")
        else "list variants included, no quantities"
    )

    system_prompt = (
        # 1. Role + task
        "You are an inventory assistant. Merge similar items into ONE consolidated entry.\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Output schema
        "Return a JSON object with:\n"
        f"- name: string ({name_instr})\n"
        "- quantity: integer (total combined)\n"
        f"- description: string ({desc_instr})\n"
        "- labelIds: array of applicable label IDs\n\n"
        # 4. Naming
        f"{naming_rules}\n\n"
        # 5. Labels
        f"{label_prompt}"
    )

    user_prompt = (
        f"Merge into one item: {items_text}\n"
        "Example: '80 Grit' + '120 Grit' → 'Sandpaper Assortment', "
        "description: 'Includes 80, 120 grit'.\nReturn only JSON."
    )

    if image_data_uris:
        parsed_content = await vision_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_data_uris=image_data_uris,
            api_key=api_key,
            model=model,
        )
    else:
        # No images - use text-only completion
        from ...ai.openai import chat_completion

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        parsed_content = await chat_completion(
            messages,
            api_key=api_key,
            model=model,
            response_format={"type": "json_object"},
        )

    logger.info(f"Merge complete: {parsed_content.get('name', 'Unknown')}")

    return parsed_content
