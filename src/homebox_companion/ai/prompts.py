"""Shared prompt templates and constants for AI interactions."""

from __future__ import annotations

# Default instructions per field (single source of truth)
# User customizations will REPLACE these when provided
FIELD_DEFAULTS = {
    "name": "Title Case, no quantity, max 255 characters",
    "description": "max 1000 chars, condition/attributes only, NEVER mention quantity",
    "quantity": ">= 1, count of identical items",
    "manufacturer": "brand name from logo/label when clearly visible",
    "model_number": "product code from label when clearly visible",
    "serial_number": "S/N from sticker/label when clearly visible",
    "purchase_price": "price from visible tag/receipt, just the number",
    "purchase_from": "store name from visible packaging/receipt",
    "notes": "ONLY for defects/damage/warnings - leave null for normal items",
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
        customizations: Optional dict with 'name' for custom naming instructions
            and 'naming_examples' for custom example names.

    Returns:
        Naming rules string with examples and optional user preference.
    """
    # Get examples (use custom or default)
    examples = FIELD_DEFAULTS["naming_examples"]
    if customizations and customizations.get("naming_examples"):
        examples = customizations["naming_examples"].strip()

    # Build base rules with examples
    result = f"""{NAMING_FORMAT}

Examples: {examples}"""

    # Add user naming preference if provided
    if customizations and customizations.get("name") and customizations["name"].strip():
        result += f"""

USER NAMING PREFERENCE (takes priority):
{customizations["name"].strip()}"""

    return result


def build_item_schema(customizations: dict[str, str] | None = None) -> str:
    """Build item schema with customizations integrated inline.

    User customizations REPLACE the default instruction for each field,
    ensuring the LLM sees only one instruction per field.

    Args:
        customizations: Dict mapping field names to custom instructions.
            Keys should match FIELD_DEFAULTS keys.

    Returns:
        Item schema string with customizations integrated.
    """
    instr = {**FIELD_DEFAULTS, **(customizations or {})}
    return f"""OUTPUT SCHEMA - Each item must include:
- name: string ({instr['name']})
- quantity: integer ({instr['quantity']})
- description: string ({instr['description']})
- labelIds: array of matching label IDs"""


def build_extended_fields_schema(customizations: dict[str, str] | None = None) -> str:
    """Build extended fields schema with customizations integrated inline.

    User customizations REPLACE the default instruction for each field,
    ensuring the LLM sees only one instruction per field.

    Args:
        customizations: Dict mapping field names to custom instructions.
            Keys should match FIELD_DEFAULTS keys.

    Returns:
        Extended fields schema string with customizations integrated.
    """
    instr = {**FIELD_DEFAULTS, **(customizations or {})}

    # Build notes examples only if using default notes instruction
    notes_examples = ""
    if customizations is None or "notes" not in customizations:
        notes_examples = (
            '\n  GOOD: "Cracked lens", "Missing screws" | '
            'BAD: "Appears new", "Made in China"'
        )

    return f"""
OPTIONAL FIELDS (include only when visible or user-provided):
- manufacturer: string or null ({instr['manufacturer']})
- modelNumber: string or null ({instr['model_number']})
- serialNumber: string or null ({instr['serial_number']})
- purchasePrice: number or null ({instr['purchase_price']})
- purchaseFrom: string or null ({instr['purchase_from']})
- notes: string or null ({instr['notes']}){notes_examples}"""


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
