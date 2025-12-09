"""Shared prompt templates and constants for AI interactions.

Note on customizations:
    The `customizations` parameter in prompt builder functions should contain
    the effective values for all fields (user overrides merged with defaults).

    The main source of truth for defaults is FieldPreferencesDefaults in
    field_preferences.py, which handles env var overrides.

    FIELD_DEFAULTS below is a legacy fallback only used when customizations
    is None. In normal operation, get_vision_context() and prompt preview
    always pass effective customizations, so FIELD_DEFAULTS is not used.
"""

from __future__ import annotations

# Legacy fallback defaults - only used when customizations is None
# The real defaults come from FieldPreferencesDefaults in field_preferences.py
# which supports env var overrides via HBC_AI_* variables
FIELD_DEFAULTS = {
    "name": "Title Case, no quantity, max 255 characters",
    "description": "max 1000 chars, condition/attributes only, NEVER mention quantity",
    "quantity": ">= 1, count of identical items",
    "manufacturer": "brand name from logo/label when clearly visible",
    "model_number": "product code from label when clearly visible",
    "serial_number": "S/N from sticker/label when clearly visible",
    "purchase_price": "price from visible tag/receipt, just the number",
    "purchase_from": "store name from visible packaging/receipt",
    "notes": (
        'ONLY for defects/damage/warnings - leave null for normal items. '
        'GOOD: "Cracked lens", "Missing screws" | BAD: "Appears new", "Made in China"'
    ),
    "naming_examples": (
        '"Ball Bearing 6900-2RS 10x22x6mm", '
        '"Acrylic Paint Vallejo Game Color Bone White", '
        '"LED Strip COB Green 5V 1M"'
    ),
}

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


def build_naming_rules(customizations: dict[str, str] | None = None) -> str:
    """Build naming rules with configurable examples and optional user override.

    Args:
        customizations: Dict with effective values for all fields. Should contain
            'naming_examples' for examples. If 'name' is present and differs from
            the default naming format, adds a user preference note.
            Pass None only for legacy compatibility (will use FIELD_DEFAULTS).

    Returns:
        Naming rules string with examples and optional user preference.
    """
    # Get examples - use passed value or legacy fallback
    examples = FIELD_DEFAULTS["naming_examples"]
    if customizations and customizations.get("naming_examples"):
        examples = customizations["naming_examples"].strip()

    # Build base rules with examples
    result = f"""{NAMING_FORMAT}

Examples: {examples}"""

    # Add user naming preference if it differs from the base format
    # (indicates a custom instruction was set)
    if customizations and customizations.get("name"):
        name_instruction = customizations["name"].strip()
        # Check if this looks like a custom user instruction (not the default format)
        if not name_instruction.startswith("[Type]"):
            result += f"""

USER NAMING PREFERENCE (takes priority):
{name_instruction}"""

    return result


def build_item_schema(customizations: dict[str, str] | None = None) -> str:
    """Build item schema with field instructions integrated inline.

    Args:
        customizations: Dict with effective values for fields (name, quantity,
            description). Should contain values for all fields - user overrides
            merged with defaults. Pass None only for legacy compatibility.

    Returns:
        Item schema string with field instructions.
    """
    instr = {**FIELD_DEFAULTS, **(customizations or {})}
    return f"""OUTPUT SCHEMA - Each item must include:
- name: string ({instr['name']})
- quantity: integer ({instr['quantity']})
- description: string ({instr['description']})
- labelIds: array of matching label IDs"""


def build_extended_fields_schema(customizations: dict[str, str] | None = None) -> str:
    """Build extended fields schema with field instructions integrated inline.

    Args:
        customizations: Dict with effective values for extended fields
            (manufacturer, model_number, serial_number, purchase_price,
            purchase_from, notes). Should contain values for all fields.
            Pass None only for legacy compatibility.

    Returns:
        Extended fields schema string with field instructions.
    """
    instr = {**FIELD_DEFAULTS, **(customizations or {})}

    return f"""
OPTIONAL FIELDS (include only when visible or user-provided):
- manufacturer: string or null ({instr['manufacturer']})
- modelNumber: string or null ({instr['model_number']})
- serialNumber: string or null ({instr['serial_number']})
- purchasePrice: number or null ({instr['purchase_price']})
- purchaseFrom: string or null ({instr['purchase_from']})
- notes: string or null ({instr['notes']})"""


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
