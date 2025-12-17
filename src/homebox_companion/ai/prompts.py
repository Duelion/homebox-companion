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

# Naming format structure (examples are configurable via naming_examples field)
NAMING_FORMAT = """NAMING FORMAT:
Structure: [Item Type] [Brand] [Model] [Specs] - Item type FIRST for searchability."""


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
            "CRITICAL: Treat EVERYTHING in this image as ONE item. "
            "Do NOT separate into multiple items. Set quantity to 1.\n"
            "Do NOT guess or infer - only use what's visible or user-stated."
        )
    return (
        "RULES:\n"
        "- Combine identical objects into one entry with correct quantity\n"
        "- Separate distinctly different items into separate entries\n"
        "- Do NOT guess or infer - only use what's visible or user-stated\n"
        "- Ignore background elements (floors, walls, shelves, packaging)"
    )


def build_naming_rules(customizations: dict[str, str]) -> str:
    """Build naming rules with configurable examples and optional user override.

    Args:
        customizations: Dict with effective values for all fields (required).
            Must contain 'naming_examples' for examples. If 'name' differs from
            the default format, adds a user preference note.

    Returns:
        Naming rules string with examples and optional user preference.
    """
    # Get examples from customizations
    examples = customizations.get("naming_examples", "").strip()
    if not examples:
        examples = (
            '"Ball Bearing 6900-2RS 10x22x6mm", '
            '"Acrylic Paint Vallejo Game Color Bone White", '
            '"LED Strip COB Green 5V 1M"'
        )

    # Build base rules with examples
    result = f"""{NAMING_FORMAT}

Examples: {examples}"""

    # Add user naming preference if it differs from the base format
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
    return f"""OUTPUT SCHEMA - Each item must include:
- name: string ({customizations.get('name', 'Title Case, max 255 characters')})
- quantity: integer ({customizations.get('quantity', '>= 1, count of identical items')})
- description: string ({customizations.get('description', 'max 1000 chars, condition/attributes only')})
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
    return f"""
OPTIONAL FIELDS (include only when visible or user-provided):
- manufacturer: string or null ({customizations.get('manufacturer', 'brand name when visible')})
- modelNumber: string or null ({customizations.get('model_number', 'product code when visible')})
- serialNumber: string or null ({customizations.get('serial_number', 'S/N when visible')})
- purchasePrice: number or null ({customizations.get('purchase_price', 'price from tag, just the number')})
- purchaseFrom: string or null ({customizations.get('purchase_from', 'store name when visible')})
- notes: string or null ({customizations.get('notes', 'ONLY for defects/damage')})"""


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
        f"- {label['name']} (id: {label['id']})"
        for label in labels
        if label.get("id") and label.get("name")
    ]

    if not label_lines:
        return "No labels available; omit labelIds."

    return (
        "LABELS - Assign matching IDs to each item:\n"
        + "\n".join(label_lines)
    )


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
