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
        "3. Return the corrected item(s) with ALL fields\n\n"
        f"{NAMING_RULES}\n\n"
        "CORRECTION RULES:\n"
        "- If the user says 'these are two separate items' or similar, return "
        "  multiple items in the array\n"
        "- If the user is just correcting the name/description, return a single item\n"
        "- If the user specifies a brand/manufacturer, use that information\n"
        "- If the user specifies a PRICE (e.g., '20 usd', '$15', 'costs 50 dollars'), "
        "  set purchasePrice to that numeric value\n"
        "- If the user specifies where they bought it (e.g., 'from Amazon', 'at Home Depot'), "
        "  set purchaseFrom to that store name\n"
        "- If the user provides ANY specific information about the item, incorporate it\n"
        "- Always look at the image to verify the user's feedback makes sense\n\n"
        "Return a JSON object with an `items` array.\n"
        f"{ITEM_SCHEMA}\n\n"
        "EXTENDED FIELDS (include when user provides info OR visible in image):\n"
        "- manufacturer: string or null (brand name from user input or visible in image)\n"
        "- modelNumber: string or null (model/part number from user or visible on item)\n"
        "- serialNumber: string or null (serial number from user or visible on item)\n"
        "- purchasePrice: number or null (price in USD from user input)\n"
        "- purchaseFrom: string or null (store/retailer name from user or visible on packaging)\n"
        "- notes: string or null (additional details from user or observations from image)\n\n"
        + label_prompt
    )

    # Build current item details including extended fields
    current_details = [
        f"- Name: {current_item.get('name', 'Unknown')}",
        f"- Quantity: {current_item.get('quantity', 1)}",
        f"- Description: {current_item.get('description', 'None')}",
    ]
    if current_item.get('manufacturer'):
        current_details.append(f"- Manufacturer: {current_item.get('manufacturer')}")
    model_num = current_item.get('modelNumber') or current_item.get('model_number')
    if model_num:
        current_details.append(f"- Model Number: {model_num}")
    serial_num = current_item.get('serialNumber') or current_item.get('serial_number')
    if serial_num:
        current_details.append(f"- Serial Number: {serial_num}")
    price = current_item.get('purchasePrice') or current_item.get('purchase_price')
    if price:
        current_details.append(f"- Purchase Price: {price}")
    purchase_from = current_item.get('purchaseFrom') or current_item.get('purchase_from')
    if purchase_from:
        current_details.append(f"- Purchase From: {purchase_from}")
    if current_item.get('notes'):
        current_details.append(f"- Notes: {current_item.get('notes')}")

    user_prompt = (
        "I previously detected an item in this image as:\n"
        + "\n".join(current_details) + "\n\n"
        f"The user has provided this correction/feedback:\n"
        f'"{correction_instructions}"\n\n'
        "IMPORTANT: Parse the user's feedback for:\n"
        "- Name corrections (e.g., 'this is actually a...')\n"
        "- Brand/manufacturer (e.g., 'it's a Bosch', 'made by DeWalt')\n"
        "- Price information (e.g., 'costs $20', 'I paid 50') -> set purchasePrice\n"
        "- Store/retailer (e.g., 'bought from Amazon', 'from Home Depot') -> set purchaseFrom\n"
        "- Model numbers (e.g., 'model XYZ-123') -> set modelNumber\n"
        "- Any other specific details\n\n"
        "Apply ALL information from the user's feedback to the appropriate fields.\n"
        "Return the corrected item(s) with ALL fields.\n\n"
        "Return only JSON with an 'items' array."
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
        if item.get('manufacturer'):
            logger.debug(f"    Manufacturer: {item.get('manufacturer')}")
        if item.get('modelNumber') or item.get('model_number'):
            logger.debug(f"    Model: {item.get('modelNumber') or item.get('model_number')}")
        if item.get('purchasePrice') or item.get('purchase_price'):
            logger.debug(f"    Price: {item.get('purchasePrice') or item.get('purchase_price')}")

    return items

