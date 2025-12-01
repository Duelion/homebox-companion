"""LLM utilities for extracting Homebox items from images.

This module provides functions to analyze images using OpenAI's vision
models and extract structured item data suitable for Homebox.

Primary functions:
    - detect_items: Simple sync function for detecting items in an image file
    - detect_items_from_bytes: Async function for raw image bytes
    - analyze_item_details_from_images: Multi-image detailed analysis
    - merge_items_with_openai: Combine similar items
    - correct_item_with_openai: Fix detection errors with user feedback

Note: Core detection functions have sync wrappers for convenience.
Use async versions in async contexts (FastAPI, etc.) for better performance.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from .config import settings
from .models import DetectedItem

# Shared naming rules for consistent LLM output across all functions
NAMING_RULES = """NAMING RULES (IMPORTANT - follow strictly):
- Use Title Case for all item names (e.g., "Claw Hammer", "Phillips Screwdriver")
- Do NOT include quantity in the name (wrong: "3 Screws", correct: "Screw")
- Do NOT include quantity in the description (wrong: "Pack of 10", correct: "Zinc-plated")
- Be specific: include brand, model, size, or distinguishing features when visible
- Keep names concise but descriptive (max 255 characters)"""

ITEM_SCHEMA = """Each item must include:
- name: string (Title Case, no quantity, max 255 characters)
- quantity: integer (>= 1, count of identical items)
- description: string (max 1000 chars, condition/attributes only, NEVER mention quantity)
- labelIds: array of matching label IDs from the available labels"""

# Extended fields that can be extracted when visible/applicable
EXTENDED_FIELDS_SCHEMA = """
OPTIONAL EXTENDED FIELDS - Only include when clearly visible/determinable from the image:

- manufacturer: string or null (brand name ONLY if clearly visible via logo, label, or packaging)
- modelNumber: string or null (ONLY if product code/model number is visible on label or item)
- serialNumber: string or null (ONLY if serial number is visible on sticker/label/engraving)
- purchasePrice: number or null (ONLY if price tag or receipt is visible in image)
- purchaseFrom: string or null (ONLY if store name/retailer is visible on packaging/receipt)
- notes: string or null (ONLY for significant observations: condition issues, damage,
  special features, or notable details not fitting in description)

CRITERIA FOR EXTENDED FIELDS (IMPORTANT):
- DO NOT guess or infer fields you cannot see clearly
- manufacturer: Include ONLY when brand/logo is VISIBLE (e.g., "DeWalt" visible on tool)
- modelNumber: Include ONLY when model/part number TEXT is VISIBLE (e.g., "DCD771C2" on label)
- serialNumber: Include ONLY when S/N text is VISIBLE (usually on sticker/label)
- purchasePrice: Include ONLY if price tag/receipt is IN THE IMAGE
- purchaseFrom: Include ONLY if retailer name is visible (e.g., "Home Depot" on packaging)
- notes: Include ONLY for genuinely useful observations (damage, wear, modifications, etc.)

If a field cannot be determined from what's visible, omit it or set to null."""


def encode_image_to_data_uri(image_path: Path) -> str:
    """Read an image file and return a data URI for OpenAI's vision API.

    Args:
        image_path: Path to the image file.

    Returns:
        A data URI string (e.g., "data:image/jpeg;base64,...").
    """
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def encode_image_bytes_to_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Encode raw image bytes to a data URI for OpenAI's vision API.

    Args:
        image_bytes: Raw image data.
        mime_type: MIME type of the image.

    Returns:
        A data URI string.
    """
    suffix = mime_type.split("/")[-1] if "/" in mime_type else "jpeg"
    payload = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


async def detect_items_from_bytes(
    image_bytes: bytes,
    api_key: str | None = None,
    mime_type: str = "image/jpeg",
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
) -> list[DetectedItem]:
    """Use OpenAI vision model to detect items from raw image bytes.

    Args:
        image_bytes: Raw image data.
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        mime_type: MIME type of the image.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest for items.
        single_item: If True, treat everything in the image as a single item
            (do not separate into multiple items).
        extra_instructions: Optional user hint about what's in the image
            (e.g., "the items in the photo are static grass for train models").
        extract_extended_fields: If True, also attempt to extract extended item
            fields like manufacturer, modelNumber, serialNumber, purchasePrice,
            purchaseFrom, and notes when they are clearly visible in the image.
            These fields are extracted on a criteria basis - only when the AI
            can determine them with confidence from visible text/labels.

    Returns:
        List of detected items with quantities, descriptions, and optionally
        extended fields when extract_extended_fields is True.
    """
    data_uri = encode_image_bytes_to_data_uri(image_bytes, mime_type)
    return await _detect_items_from_data_uri(
        data_uri,
        api_key or settings.openai_api_key,
        model or settings.openai_model,
        labels,
        single_item=single_item,
        extra_instructions=extra_instructions,
        extract_extended_fields=extract_extended_fields,
    )


async def _detect_items_from_data_uri(
    data_uri: str,
    api_key: str,
    model: str,
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
) -> list[DetectedItem]:
    """Core detection logic using a data URI.

    Args:
        data_uri: Base64-encoded image data URI.
        api_key: OpenAI API key.
        model: OpenAI model name.
        labels: Optional list of Homebox labels for item tagging.
        single_item: If True, treat everything as a single item (don't separate).
        extra_instructions: User-provided hint about image contents.
        extract_extended_fields: If True, also extract manufacturer, modelNumber, etc.
            when visible in the image.
    """
    logger.debug(f"Starting item detection with model: {model}")
    logger.debug(f"Single item mode: {single_item}, Extra instructions: {extra_instructions}")
    logger.debug(f"Extract extended fields: {extract_extended_fields}")

    if labels is None:
        labels = []

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else "IMPORTANT: You MUST assign appropriate labelIds from this list to each item. "
        "Select all labels that apply to each item. Available labels:\n"
        + "\n".join(f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id"))
    )

    logger.debug(f"Labels provided: {len(labels)}")

    # Build system prompt based on single_item mode
    if single_item:
        grouping_instructions = (
            "IMPORTANT: Treat EVERYTHING visible in this image as a SINGLE item. "
            "Do NOT separate objects into multiple items. Even if you see multiple pieces "
            "or components, group them all as ONE item with an appropriate collective name "
            "and set quantity to 1. For example, if you see a bag of screws, return one item "
            "'Bag of Screws' with quantity 1, not individual screws."
        )
    else:
        grouping_instructions = (
            "Combine identical objects into a single entry with the correct quantity. "
            "Separate distinctly different items into separate entries."
        )

    # Build user context hint if provided
    user_hint = ""
    if extra_instructions and extra_instructions.strip():
        user_hint = (
            f"\n\nUSER CONTEXT: The user has provided this hint about the image contents: "
            f'"{extra_instructions.strip()}". Use this information to better understand '
            "and identify the items in the image."
        )

    # Include extended fields schema when requested
    extended_prompt = ""
    extended_example = ""
    if extract_extended_fields:
        extended_prompt = f"\n\n{EXTENDED_FIELDS_SCHEMA}"
        extended_example = (
            ',"manufacturer":"DeWalt","modelNumber":"DCD771C2","notes":"Minor wear on handle"'
        )

    client = AsyncOpenAI(api_key=api_key)
    logger.debug("Calling OpenAI API...")

    completion = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant for the Homebox API. "
                    "Return a single JSON object with an `items` array.\n\n"
                    f"{NAMING_RULES}\n\n"
                    f"{ITEM_SCHEMA}"
                    f"{extended_prompt}\n\n"
                    f"{grouping_instructions} "
                    "Do not add extra commentary. Ignore background elements (floors, walls, "
                    "benches, shelves, packaging, shadows) and only count objects that are "
                    "the clear focus of the image.\n\n" + label_prompt
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List all distinct items that are the logical focus of this image "
                            "and ignore background objects or incidental surfaces. "
                            "For each item, include labelIds with matching label IDs. "
                            "Return only JSON. Example: "
                            '{"items":[{"name":"Claw Hammer","quantity":2,"description":'
                            f'"Steel claw hammer","labelIds":["id1"]{extended_example}'
                            "}]}."
                            + user_hint
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    items = DetectedItem.from_raw_items(parsed_content.get("items", []))

    logger.info(f"Detected {len(items)} items")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}, labels: {item.label_ids}")
        if extract_extended_fields:
            logger.debug(
                f"    Extended: manufacturer={item.manufacturer}, "
                f"model={item.model_number}, serial={item.serial_number}"
            )

    return items


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
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.

    Returns:
        Dictionary with extracted fields: name, description, serialNumber,
        modelNumber, manufacturer, purchasePrice, notes, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Analyzing {len(image_data_uris)} images for item: {item_name}")
    logger.debug(f"Item description: {item_description}")

    if labels is None:
        labels = []

    logger.debug(f"Available labels: {len(labels)}")

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else (
            "IMPORTANT: Assign appropriate labelIds from this list.\n"
            "Available labels:\n"
            + "\n".join(
                f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id")
            )
        )
    )

    # Build image content for the message
    image_content = []
    for data_uri in image_data_uris:
        image_content.append({"type": "image_url", "image_url": {"url": data_uri}})

    logger.debug("Calling OpenAI API for advanced analysis...")
    client = AsyncOpenAI(api_key=api_key)
    completion = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
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
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze these images of the item and extract as much detail as "
                            "possible. Look carefully at all angles, labels, and markings. "
                            "Return only JSON with the fields described."
                        ),
                    },
                    *image_content,
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    logger.info(f"Advanced analysis complete. Fields found: {list(parsed_content.keys())}")
    logger.debug(f"Full result: {parsed_content}")

    return parsed_content


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
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest.

    Returns:
        Dictionary with merged item fields: name, quantity, description, labelIds.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Merging {len(items)} items with AI")

    if labels is None:
        labels = []

    # Format items for the prompt
    items_text = "\n".join(
        f"- {item.get('name', 'Unknown')} (qty: {item.get('quantity', 1)}): "
        f"{item.get('description', 'No description')}"
        for item in items
    )

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else (
            "Assign appropriate labelIds from this list:\n"
            + "\n".join(
                f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id")
            )
        )
    )

    # Build message content
    content = [
        {
            "type": "text",
            "text": (
                f"Merge these {len(items)} items into a single consolidated inventory item:\n\n"
                f"{items_text}\n\n"
                "Create a single item that represents all of these. Use Title Case for the name. "
                "For example, if merging '80 Grit Sandpaper', '120 Grit Sandpaper', '220 Grit "
                "Sandpaper', create 'Sandpaper Assortment' with combined quantity and a "
                "description listing the variants (e.g., 'Includes 80, 120, and 220 grit').\n\n"
                "Return only JSON with the merged item."
            ),
        }
    ]

    # Add images if provided
    if image_data_uris:
        for data_uri in image_data_uris:
            content.append({"type": "image_url", "image_url": {"url": data_uri}})

    logger.debug("Calling OpenAI API for item merge...")
    client = AsyncOpenAI(api_key=api_key)
    completion = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
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
                ),
            },
            {
                "role": "user",
                "content": content,
            },
        ],
    )

    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI merge response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    logger.info(f"Merge complete: {parsed_content.get('name', 'Unknown')}")

    return parsed_content


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
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
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

    if labels is None:
        labels = []

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else (
            "Assign appropriate labelIds from this list to each resulting item:\n"
            + "\n".join(
                f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id")
            )
        )
    )

    # Build the message with the image and correction context
    content: list[dict] = [
        {
            "type": "text",
            "text": (
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
            ),
        },
        {"type": "image_url", "image_url": {"url": image_data_uri}},
    ]

    logger.debug("Calling OpenAI API for item correction...")
    client = AsyncOpenAI(api_key=api_key)
    completion = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
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
                ),
            },
            {
                "role": "user",
                "content": content,
            },
        ],
    )

    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI correction response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    items = parsed_content.get("items", [])

    # If the response is a single item dict (not in array), wrap it
    if not items and isinstance(parsed_content, dict) and "name" in parsed_content:
        items = [parsed_content]

    logger.info(f"Correction resulted in {len(items)} item(s)")
    for item in items:
        logger.debug(f"  Corrected item: {item.get('name')}, qty: {item.get('quantity', 1)}")

    return items


async def discriminatory_detect_items(
    image_data_uris: list[str],
    previous_merged_item: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
) -> list[DetectedItem]:
    """Re-detect items from images with more discriminatory instructions.

    This function is used when a user "unmerges" items - it re-analyzes
    the images with specific instructions to be more discriminatory and
    separate items that might have been grouped together previously.

    Args:
        image_data_uris: List of data URI strings for each image.
        previous_merged_item: The previously merged item dict for context.
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest for items.
        extract_extended_fields: If True (default), also extract extended item
            fields like manufacturer, modelNumber, serialNumber when visible.

    Returns:
        List of detected items, ideally more specific/separated than before.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.info(f"Discriminatory detection with {len(image_data_uris)} images")
    logger.debug(f"Extract extended fields: {extract_extended_fields}")

    if labels is None:
        labels = []

    label_prompt = (
        "No labels are available; omit labelIds."
        if not labels
        else (
            "IMPORTANT: Assign appropriate labelIds from this list to each item:\n"
            + "\n".join(
                f"- {label['name']} (id: {label['id']})"
                for label in labels
                if label.get("id")
            )
        )
    )

    # Include extended fields schema when requested
    extended_prompt = ""
    if extract_extended_fields:
        extended_prompt = f"\n\n{EXTENDED_FIELDS_SCHEMA}"

    # Context about what was previously detected
    context = ""
    if previous_merged_item:
        context = (
            f"\n\nPreviously, these items were grouped as: "
            f"'{previous_merged_item.get('name', 'unknown')}' "
            f"(qty: {previous_merged_item.get('quantity', 1)}). "
            f"Description: {previous_merged_item.get('description', 'N/A')}.\n"
            "The user believes these should be SEPARATE items. "
            "Please look more carefully and identify distinct items."
        )

    # Build message content with images
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Please carefully examine these images and identify ALL DISTINCT items. "
                "Be MORE DISCRIMINATORY than usual - if items look similar but have "
                "differences (like different sizes, colors, brands, models, grits, etc.), "
                "list them as SEPARATE items.\n\n"
                "For example (using Title Case):\n"
                "- Different grit sandpapers → '80 Grit Sandpaper', '120 Grit Sandpaper'\n"
                "- Different sized screws → 'M3 Phillips Screw', 'M5 Phillips Screw'\n"
                "- Different colored items → 'Red Marker', 'Blue Marker'\n"
                "- Different brands → 'DeWalt Drill Bit', 'Bosch Drill Bit'\n\n"
                "Be specific in names and descriptions. Include distinguishing "
                "characteristics like size, color, brand, model number, etc."
                + context
                + "\n\nReturn only JSON."
            ),
        }
    ]

    # Add all images
    for data_uri in image_data_uris:
        content.append({"type": "image_url", "image_url": {"url": data_uri}})

    logger.debug("Calling OpenAI API for discriminatory detection...")
    client = AsyncOpenAI(api_key=api_key)
    completion = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant for the Homebox API. Your task is to "
                    "identify items with MAXIMUM SPECIFICITY. Do NOT group similar items "
                    "together - instead, list each distinct variant separately.\n\n"
                    f"{NAMING_RULES}\n\n"
                    "Return a JSON object with an `items` array.\n"
                    f"{ITEM_SCHEMA}"
                    f"{extended_prompt}\n\n"
                    "SPECIFICITY RULES:\n"
                    "- Be specific: include size, color, brand, model in the name when visible\n"
                    "- Each distinct variant gets its own entry (e.g., '80 Grit Sandpaper' and "
                    "'120 Grit Sandpaper' are separate items)\n"
                    "- If you see 3 sandpapers of different grits, that's 3 separate items\n"
                    "- If you see 5 screws of 2 sizes, that's 2 separate items with quantities\n\n"
                    + label_prompt
                ),
            },
            {
                "role": "user",
                "content": content,
            },
        ],
    )

    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI discriminatory response: {raw_content[:500]}...")

    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    items = DetectedItem.from_raw_items(parsed_content.get("items", []))

    logger.info(f"Discriminatory detection found {len(items)} items")
    for item in items:
        logger.debug(f"  Item: {item.name}, qty: {item.quantity}")
        if extract_extended_fields and item.has_extended_fields():
            logger.debug(
                f"    Extended: manufacturer={item.manufacturer}, "
                f"model={item.model_number}, serial={item.serial_number}"
            )

    return items


# =============================================================================
# Synchronous Wrapper Functions
# =============================================================================
# These provide a convenient sync interface for scripts and simple use cases.
# For async contexts (FastAPI, etc.), use the async versions directly.


def _run_sync(coro):
    """Run an async coroutine synchronously.

    Handles the case where we're already in an event loop (e.g., Jupyter)
    by creating a new loop in a thread.
    """
    try:
        asyncio.get_running_loop()
        # Already in an async context - run in a new thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # No running loop - we can use asyncio.run()
        return asyncio.run(coro)


def detect_items(
    image_path: Path | str,
    api_key: str | None = None,
    model: str | None = None,
    labels: list[dict[str, str]] | None = None,
) -> list[DetectedItem]:
    """Detect items in an image file using OpenAI vision.

    This is a convenience wrapper that reads an image file and runs detection.
    For raw bytes or async contexts, use detect_items_from_bytes instead.

    Args:
        image_path: Path to the image file (JPEG, PNG, etc.).
        api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
        model: Model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        labels: Optional list of Homebox labels to suggest for items.

    Returns:
        List of detected items with names, quantities, and descriptions.

    Example:
        >>> from homebox_vision import detect_items
        >>> items = detect_items("photo.jpg")
        >>> for item in items:
        ...     print(f"{item.name}: {item.quantity}")
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    image_bytes = path.read_bytes()
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    mime_type = f"image/{suffix}"

    return _run_sync(
        detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=api_key,
            mime_type=mime_type,
            model=model,
            labels=labels,
        )
    )
