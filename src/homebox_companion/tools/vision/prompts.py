"""Vision-specific prompt templates."""

from __future__ import annotations

from ...ai.prompts import EXTENDED_FIELDS_SCHEMA, ITEM_SCHEMA, NAMING_RULES, build_label_prompt


def build_detection_system_prompt(
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extract_extended_fields: bool = False,
) -> str:
    """Build the system prompt for item detection.

    Args:
        labels: Optional list of label dicts for assignment.
        single_item: If True, treat all items as one grouped item.
        extract_extended_fields: If True, include extended fields schema.

    Returns:
        Complete system prompt string.
    """
    if single_item:
        grouping_instructions = (
            "IMPORTANT: Treat EVERYTHING visible in this image as a SINGLE item. "
            "Do NOT separate objects into multiple items. Even if you see multiple pieces "
            "or components, group them all as ONE item with an appropriate collective name "
            "and set quantity to 1."
        )
    else:
        grouping_instructions = (
            "Combine identical objects into a single entry with the correct quantity. "
            "Separate distinctly different items into separate entries."
        )

    extended_prompt = f"\n\n{EXTENDED_FIELDS_SCHEMA}" if extract_extended_fields else ""
    label_prompt = build_label_prompt(labels)

    return (
        "You are an inventory assistant for the Homebox API. "
        "Return a single JSON object with an `items` array.\n\n"
        f"{NAMING_RULES}\n\n"
        f"{ITEM_SCHEMA}"
        f"{extended_prompt}\n\n"
        f"{grouping_instructions} "
        "Do not add extra commentary. Ignore background elements (floors, walls, "
        "benches, shelves, packaging, shadows) and only count objects that are "
        "the clear focus of the image.\n\n" + label_prompt
    )


def build_detection_user_prompt(
    extra_instructions: str | None = None,
    extract_extended_fields: bool = False,
    multi_image: bool = False,
    single_item: bool = False,
) -> str:
    """Build the user prompt for item detection.

    Args:
        extra_instructions: Optional user hint about image contents.
        extract_extended_fields: If True, include extended field example.
        multi_image: If True, use multi-image phrasing.
        single_item: If True, use single-item phrasing for multi-image.

    Returns:
        Complete user prompt string.
    """
    extended_example = ""
    if extract_extended_fields:
        extended_example = (
            ',"manufacturer":"DeWalt","modelNumber":"DCD771C2","notes":"Minor wear on handle"'
        )

    user_hint = ""
    if extra_instructions and extra_instructions.strip():
        user_hint = (
            f"\n\nUSER CONTEXT: The user has provided this hint about the image contents: "
            f'"{extra_instructions.strip()}". Use this information to better understand '
            "and identify the items in the image."
        )

    if multi_image:
        if single_item:
            multi_image_hint = (
                "You are being shown multiple images of the SAME item from different angles "
                "or with different details visible. Use all images together to identify and "
                "describe this single item. "
            )
        else:
            multi_image_hint = (
                "You are being shown multiple images that may contain the same or related items. "
                "Analyze all images together to identify all distinct items, avoiding duplicates. "
            )
    else:
        multi_image_hint = ""

    return (
        f"{multi_image_hint}"
        "List all distinct items that are the logical focus of this image "
        "and ignore background objects or incidental surfaces. "
        "For each item, include labelIds with matching label IDs. "
        "Return only JSON. Example: "
        '{"items":[{"name":"Claw Hammer","quantity":2,"description":'
        f'"Steel claw hammer","labelIds":["id1"]{extended_example}'
        "}]}."
        + user_hint
    )


def build_multi_image_system_prompt(
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extract_extended_fields: bool = False,
) -> str:
    """Build system prompt for multi-image detection.

    Args:
        labels: Optional list of label dicts for assignment.
        single_item: If True, treat all images as showing one item.
        extract_extended_fields: If True, include extended fields schema.

    Returns:
        Complete system prompt string.
    """
    if single_item:
        grouping_instructions = (
            "IMPORTANT: Treat EVERYTHING visible across ALL images as a SINGLE item. "
            "Do NOT separate objects into multiple items. These images show the same item "
            "from different angles or with additional details. Group everything as ONE item "
            "with an appropriate name and set quantity to 1."
        )
    else:
        grouping_instructions = (
            "Combine identical objects into a single entry with the correct quantity. "
            "Separate distinctly different items into separate entries."
        )

    extended_prompt = f"\n\n{EXTENDED_FIELDS_SCHEMA}" if extract_extended_fields else ""
    label_prompt = build_label_prompt(labels)

    return (
        "You are an inventory assistant for the Homebox API. "
        "Return a single JSON object with an `items` array.\n\n"
        f"{NAMING_RULES}\n\n"
        f"{ITEM_SCHEMA}"
        f"{extended_prompt}\n\n"
        f"{grouping_instructions} "
        "Do not add extra commentary. Ignore background elements (floors, walls, "
        "benches, shelves, packaging, shadows) and only count objects that are "
        "the clear focus of the images.\n\n" + label_prompt
    )


def build_discriminatory_system_prompt(
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
) -> str:
    """Build system prompt for discriminatory (detailed) detection.

    This is used when "unmerging" items to get more specific results.

    Args:
        labels: Optional list of label dicts for assignment.
        extract_extended_fields: If True, include extended fields schema.

    Returns:
        Complete system prompt string.
    """
    extended_prompt = f"\n\n{EXTENDED_FIELDS_SCHEMA}" if extract_extended_fields else ""
    label_prompt = build_label_prompt(labels)

    return (
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
    )


def build_discriminatory_user_prompt(previous_merged_item: dict | None = None) -> str:
    """Build user prompt for discriminatory detection.

    Args:
        previous_merged_item: Optional dict of the previously merged item for context.

    Returns:
        User prompt string.
    """
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

    return (
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
    )





