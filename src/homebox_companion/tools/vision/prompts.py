"""Vision-specific prompt templates."""

from __future__ import annotations

from ...ai.prompts import (
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_language_instruction,
    build_naming_rules,
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
    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    critical = build_critical_constraints(single_item)
    item_schema = build_item_schema(field_preferences)
    extended_schema = (
        build_extended_fields_schema(field_preferences)
        if extract_extended_fields
        else ""
    )
    naming_rules = build_naming_rules(field_preferences)
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
        # 5. Naming guidelines
        f"{naming_rules}\n\n"
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
            multi_image_hint = (
                "Multiple images of the SAME item. Combine all details into one entry. "
            )
        else:
            multi_image_hint = (
                "Multiple images - identify all distinct items, avoiding duplicates. "
            )
    else:
        multi_image_hint = ""

    return (
        f"{multi_image_hint}"
        "List items that are the focus of this image. Return only JSON. "
        "Example: "
        '{"items":[{"name":"Claw Hammer","quantity":2,'
        f'"description":"Steel claw hammer","labelIds":["id1"]{extended_example}'
        "}]}."
        + user_hint
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
    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    critical = build_critical_constraints(single_item)
    item_schema = build_item_schema(field_preferences)
    extended_schema = (
        build_extended_fields_schema(field_preferences)
        if extract_extended_fields
        else ""
    )
    naming_rules = build_naming_rules(field_preferences)
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
        # 5. Naming guidelines
        f"{naming_rules}\n\n"
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
    # Build components with customizations
    language_instr = build_language_instruction(output_language)
    item_schema = build_item_schema(field_preferences)
    extended_schema = (
        build_extended_fields_schema(field_preferences)
        if extract_extended_fields
        else ""
    )
    naming_rules = build_naming_rules(field_preferences)
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
        # 5. Naming guidelines
        f"{naming_rules}\n\n"
        # 6. Labels
        f"{label_prompt}"
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
            f"\n\nPreviously grouped as: '{previous_merged_item.get('name', 'unknown')}' "
            f"(qty: {previous_merged_item.get('quantity', 1)}). "
            "User wants these as SEPARATE items."
        )

    return (
        "Identify ALL DISTINCT items. Be MORE DISCRIMINATORY - "
        "different sizes/colors/brands/grits = separate items.\n"
        "Examples: '80 Grit Sandpaper' + '120 Grit Sandpaper', "
        "'M3 Phillips Screw' + 'M5 Phillips Screw'."
        + context
        + "\nReturn only JSON."
    )
