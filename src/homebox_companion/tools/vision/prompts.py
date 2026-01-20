"""Vision-specific prompt templates."""

from __future__ import annotations

from ...ai.prompts import (
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_language_instruction,
    build_naming_examples,
)


def build_detection_system_prompt(
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extract_extended_fields: bool = False,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> str:
    """Build the system prompt for item detection.

    Prompt order optimized for LLM attention:
    1. Role + output format
    2. Language instruction (if not English)
    3. Critical constraints (front-loaded)
    4. Schema (what to output)
    5. Naming guidelines (how to format)
    6. Labels (reference data)

    Args:
        labels: Optional list of label dicts for assignment.
        single_item: If True, treat all items as one grouped item.
        extract_extended_fields: If True, include extended fields schema.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for output (default: English).

    Returns:
        Complete system prompt string.
    """
    # Ensure field_preferences is a dict (empty dict if None)
    field_preferences = field_preferences or {}

    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    critical = build_critical_constraints(single_item)
    item_schema = build_item_schema(field_preferences)
    extended_schema = build_extended_fields_schema(field_preferences) if extract_extended_fields else ""
    naming_examples = build_naming_examples(field_preferences)
    label_prompt = build_label_prompt(labels)

    return (
        # 1. Role + output format
        "You are an inventory assistant for the Homebox API. "
        "Return a JSON object with an `items` array.\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Critical constraints FIRST
        f"{critical}\n\n"
        # 4. Schema
        f"{item_schema}"
        f"{extended_schema}\n\n"
        # 5. Naming examples
        f"{naming_examples}\n\n"
        # 6. Labels
        f"{label_prompt}"
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
        extended_example = ',"manufacturer":"DeWalt","modelNumber":"DCD771C2"'

    user_hint = ""
    if extra_instructions and extra_instructions.strip():
        user_hint = (
            f'\n\nUSER CONTEXT: "{extra_instructions.strip()}"\n'
            "Extract any price→purchasePrice, serial→serialNumber, "
            "model→modelNumber, store→purchaseFrom, brand→manufacturer from this text."
        )

    if multi_image:
        if single_item:
            multi_image_hint = "Multiple images of the SAME item. Combine all details into one entry. "
        else:
            multi_image_hint = "Multiple images - identify all distinct items, avoiding duplicates. "
    else:
        multi_image_hint = ""

    return (
        f"{multi_image_hint}"
        "List items that are the focus of this image. Return only JSON. "
        "Example: "
        '{"items":[{"name":"Claw Hammer","quantity":2,'
        f'"description":"Steel claw hammer","labelIds":["id1"]{extended_example}'
        "}]}." + user_hint
    )


def build_multi_image_system_prompt(
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extract_extended_fields: bool = False,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> str:
    """Build system prompt for multi-image detection.

    Args:
        labels: Optional list of label dicts for assignment.
        single_item: If True, treat all images as showing one item.
        extract_extended_fields: If True, include extended fields schema.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for output (default: English).

    Returns:
        Complete system prompt string.
    """
    # Ensure field_preferences is a dict (empty dict if None)
    field_preferences = field_preferences or {}

    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    critical = build_critical_constraints(single_item)
    item_schema = build_item_schema(field_preferences)
    extended_schema = build_extended_fields_schema(field_preferences) if extract_extended_fields else ""
    naming_examples = build_naming_examples(field_preferences)
    label_prompt = build_label_prompt(labels)

    multi_note = (
        "Analyzing multiple images of the same item."
        if single_item
        else "Analyzing multiple images - combine duplicates."
    )

    return (
        # 1. Role + output format
        f"You are an inventory assistant for the Homebox API. {multi_note} "
        "Return a JSON object with an `items` array.\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Critical constraints FIRST
        f"{critical}\n\n"
        # 4. Schema
        f"{item_schema}"
        f"{extended_schema}\n\n"
        # 5. Naming examples
        f"{naming_examples}\n\n"
        # 6. Labels
        f"{label_prompt}"
    )


def build_discriminatory_system_prompt(
    labels: list[dict[str, str]] | None = None,
    extract_extended_fields: bool = True,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> str:
    """Build system prompt for discriminatory (detailed) detection.

    This is used when "unmerging" items to get more specific results.

    Args:
        labels: Optional list of label dicts for assignment.
        extract_extended_fields: If True, include extended fields schema.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for output (default: English).

    Returns:
        Complete system prompt string.
    """
    # Ensure field_preferences is a dict (empty dict if None)
    field_preferences = field_preferences or {}

    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    item_schema = build_item_schema(field_preferences)
    extended_schema = build_extended_fields_schema(field_preferences) if extract_extended_fields else ""
    naming_examples = build_naming_examples(field_preferences)
    label_prompt = build_label_prompt(labels)

    return (
        # 1. Role + critical constraint
        "You are an inventory assistant. Identify items with MAXIMUM SPECIFICITY. "
        "Do NOT group similar items - list each distinct variant separately.\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Specificity rules (critical for this mode)
        "SPECIFICITY RULES:\n"
        "- Each distinct variant = separate entry (80 Grit vs 120 Grit = 2 items)\n"
        "- Include size, color, brand, model in names when visible\n"
        "- Only use what's visible - do NOT guess\n\n"
        # 4. Schema
        f"{item_schema}"
        f"{extended_schema}\n\n"
        # 5. Naming examples
        f"{naming_examples}\n\n"
        # 6. Labels
        f"{label_prompt}"
    )


def build_discriminatory_user_prompt() -> str:
    """Build user prompt for discriminatory detection.

    Returns:
        User prompt string for detailed item separation.
    """
    return (
        "Identify ALL DISTINCT items. Be MORE DISCRIMINATORY - "
        "different sizes/colors/brands/grits = separate items.\n"
        "Examples: '80 Grit Sandpaper' + '120 Grit Sandpaper', "
        "'M3 Phillips Screw' + 'M5 Phillips Screw'."
        "\nReturn only JSON."
    )


def build_analysis_system_prompt(
    item_name: str,
    item_description: str | None,
    labels: list[dict[str, str]] | None = None,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> str:
    """Build system prompt for detailed item analysis from multiple images.

    This is used by analyzer.py to extract detailed information from
    multiple images of the same item.

    Args:
        item_name: The name of the item being analyzed.
        item_description: Optional initial description of the item.
        labels: Optional list of label dicts for assignment.
        field_preferences: Optional dict of field customization instructions.
        output_language: Target language for output (default: English).

    Returns:
        Complete system prompt string.
    """
    # Build components with customizations (with safe defaults if None)
    field_preferences = field_preferences or {}
    language_instr = build_language_instruction(output_language)
    naming_examples = build_naming_examples(field_preferences)
    label_prompt = build_label_prompt(labels)

    # Build item context
    item_context = f"Item: '{item_name}'"
    if item_description:
        item_context += f" - {item_description}"

    # Build extended field schema for analysis (always include extended fields)
    name_instr = field_preferences.get("name", "Title Case, max 255 characters")
    desc_instr = field_preferences.get("description", "max 1000 chars, condition/attributes only")
    serial_instr = field_preferences.get("serial_number", "S/N when visible")
    model_instr = field_preferences.get("model_number", "product code when visible")
    mfr_instr = field_preferences.get("manufacturer", "brand name when visible")
    price_instr = field_preferences.get("purchase_price", "price from tag, just the number")
    notes_instr = field_preferences.get("notes", "ONLY for defects/damage")

    return (
        # 1. Role + task
        f"You are an inventory assistant analyzing images. {item_context}\n"
        # 2. Language instruction (if not English)
        f"{language_instr}\n"
        # 3. Critical instruction
        "Extract ALL visible details: serial numbers, model numbers, brand, "
        "price tags, condition issues. Only use what's visible.\n\n"
        # 4. Output schema
        "Return JSON with:\n"
        f"- name: string ({name_instr})\n"
        f"- description: string ({desc_instr})\n"
        f"- serialNumber: string or null ({serial_instr})\n"
        f"- modelNumber: string or null ({model_instr})\n"
        f"- manufacturer: string or null ({mfr_instr})\n"
        f"- purchasePrice: number or null ({price_instr})\n"
        f"- notes: string or null ({notes_instr})\n"
        "- labelIds: array of applicable label IDs\n\n"
        # 5. Naming
        f"{naming_examples}\n\n"
        # 6. Labels
        f"{label_prompt}"
    )
