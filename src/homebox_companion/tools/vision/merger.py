"""Item merging using AI."""

from __future__ import annotations

from loguru import logger

from ...ai.openai import vision_completion
from ...ai.prompts import NAMING_RULES, build_label_prompt
from ...core.config import settings


async def merge_items_with_openai(
    items: list[dict],
    image_data_uris: list[str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
) -> dict:
    """Merge multiple similar items into a single consolidated item using AI.

    This function takes multiple items (e.g., different grit sandpapers) and
    uses AI to create a single merged item with an appropriate name, combined
    quantity, and merged description.

    Args:
        items: List of item dictionaries with name, quantity, description fields.
        image_data_uris: Optional list of image data URIs for context.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.

    Returns:
        Dictionary with merged item fields: name, quantity, description, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Merging {len(items)} items with AI")

    # Format items for the prompt
    items_text = "\n".join(
        f"- {item.get('name', 'Unknown')} (qty: {item.get('quantity', 1)}): "
        f"{item.get('description', 'No description')}"
        for item in items
    )

    label_prompt = build_label_prompt(labels)

    system_prompt = (
        "You are an inventory assistant helping to merge multiple similar items "
        "into a single consolidated inventory entry. Create a sensible merged item "
        "that represents all the input items.\n\n"
        f"{NAMING_RULES}\n\n"
        "Return a single JSON object with:\n"
        "- name: string (Title Case, consolidated name, max 255 chars, e.g., "
        "'Sandpaper Assortment' or 'Mixed Screwdriver Set')\n"
        "- quantity: integer (total combined quantity)\n"
        "- description: string (list the variants/types included, but do NOT include "
        "counts or quantities, max 1000 chars, e.g., 'Includes 80, 120, 220 grit')\n"
        "- labelIds: array of label IDs that apply to the merged item\n\n"
        + label_prompt
    )

    user_prompt = (
        f"Merge these {len(items)} items into a single consolidated inventory item:\n\n"
        f"{items_text}\n\n"
        "Create a single item that represents all of these. Use Title Case for the name. "
        "For example, if merging '80 Grit Sandpaper', '120 Grit Sandpaper', '220 Grit "
        "Sandpaper', create 'Sandpaper Assortment' with combined quantity and a "
        "description listing the variants (e.g., 'Includes 80, 120, and 220 grit').\n\n"
        "Return only JSON with the merged item."
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






