"""Shared prompt templates and constants for AI interactions.

Note on customizations:
    The `customizations` parameter in prompt builder functions contains
    the effective values for all fields (user overrides merged with defaults).

    The source of truth for defaults is FieldPreferencesDefaults in
    field_preferences.py, which handles env var overrides via HBC_AI_* variables.

    All prompt builder functions require customizations to be passed explicitly
    via get_effective_customizations() - there are no fallback defaults here.
"""

from __future__ import annotations


def build_critical_constraints(single_item: bool = False) -> str:
    """Build critical constraints that MUST appear early in prompt.

    These are the most important rules that should be front-loaded
    to ensure the LLM prioritizes them.

    Args:
        single_item: If True, enforce single-item grouping mode.

    Returns:
        Critical constraints string.
    """
    if single_item:
        return (
            "CRITICAL: Treat EVERYTHING in this image as ONE item type. "
            "Do NOT separate into multiple entries. Count how many are visible.\n"
            "Do NOT guess or infer - only use what's visible or user-stated."
        )
    return (
        "RULES:\n"
        "- Combine identical objects into one entry with correct quantity\n"
        "- Separate distinctly different items into separate entries\n"
        "- Do NOT guess or infer - only use what's visible or user-stated\n"
        "- Ignore background elements (floors, walls, shelves, packaging)"
    )


def build_naming_examples(customizations: dict[str, str]) -> str:
    """Build naming examples with optional user override.

    Args:
        customizations: Dict with effective values for all fields (required).
            Must contain 'naming_examples' for examples. If 'name' contains
            a custom instruction, adds a user preference note.

    Returns:
        Naming examples string with optional user preference.
    """
    # Get examples from customizations
    examples = customizations.get("naming_examples", "").strip()
    if not examples:
        examples = (
            '"Ball Bearing 6900-2RS 10x22x6mm", '
            '"Acrylic Paint Vallejo Game Color Bone White", '
            '"LED Strip COB Green 5V 1M"'
        )

    # Build base with examples
    result = f"""Examples: {examples}"""

    # Add user naming preference if it's a custom instruction
    name_instruction = customizations.get("name", "").strip()
    if name_instruction and not name_instruction.startswith("[Type]"):
        # This is a custom instruction, not the default format
        result += f"""

USER NAMING PREFERENCE (takes priority):
{name_instruction}"""

    return result


def build_item_schema(customizations: dict[str, str]) -> str:
    """Build item schema with field instructions integrated inline.

    Args:
        customizations: Dict with effective values for fields (name, quantity,
            description). Required - must contain values for all fields.

    Returns:
        Item schema string with field instructions.
    """
    name_instr = customizations.get("name", "Title Case, max 255 characters")
    qty_instr = customizations.get("quantity", ">= 1, count of identical items")
    desc_instr = customizations.get("description", "max 1000 chars, condition/attributes only")
    return f"""OUTPUT SCHEMA - Each item must include:
- name: string ({name_instr})
- quantity: integer ({qty_instr})
- description: string ({desc_instr})
- labelIds: array of matching label IDs"""


def build_extended_fields_schema(customizations: dict[str, str]) -> str:
    """Build extended fields schema with field instructions integrated inline.

    Args:
        customizations: Dict with effective values for extended fields
            (manufacturer, model_number, serial_number, purchase_price,
            purchase_from, notes). Required - must contain values for all fields.

    Returns:
        Extended fields schema string with field instructions.
    """
    mfr_instr = customizations.get("manufacturer", "brand name when visible")
    model_instr = customizations.get("model_number", "product code when visible")
    serial_instr = customizations.get("serial_number", "S/N when visible")
    price_instr = customizations.get("purchase_price", "price from tag, just the number")
    from_instr = customizations.get("purchase_from", "store name when visible")
    notes_instr = customizations.get("notes", "ONLY for defects/damage")
    return f"""
OPTIONAL FIELDS (include only when visible or user-provided):
- manufacturer: string or null ({mfr_instr})
- modelNumber: string or null ({model_instr})
- serialNumber: string or null ({serial_instr})
- purchasePrice: number or null ({price_instr})
- purchaseFrom: string or null ({from_instr})
- notes: string or null ({notes_instr})"""


def build_label_prompt(labels: list[dict[str, str]] | None) -> str:
    """Build the label assignment prompt section.

    Args:
        labels: List of label dicts with 'id' and 'name' keys, or None.

    Returns:
        Prompt text instructing the AI how to handle labels.
    """
    if not labels:
        return "No labels available; omit labelIds."

    label_lines = [
        f"- {label['name']} (id: {label['id']})" for label in labels if label.get("id") and label.get("name")
    ]

    if not label_lines:
        return "No labels available; omit labelIds."

    return "LABELS - Assign matching IDs to each item:\n" + "\n".join(label_lines)


def build_language_instruction(output_language: str | None) -> str:
    """Build language output instruction.

    Args:
        output_language: Target language for output. If None or "English",
            returns empty string (English is default).

    Returns:
        Language instruction string, or empty string if English/default.
    """
    if not output_language or output_language.strip().lower() == "english":
        return ""

    return (
        f"\nOUTPUT LANGUAGE: Write all item names, descriptions, and notes "
        f"in {output_language.strip()}. Keep field names (name, description, etc.) "
        f"in English for JSON compatibility.\n"
    )
