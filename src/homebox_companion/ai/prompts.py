"""Shared prompt templates and constants for AI interactions."""

from __future__ import annotations

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


def build_label_prompt(labels: list[dict[str, str]] | None) -> str:
    """Build the label assignment prompt section.

    Args:
        labels: List of label dicts with 'id' and 'name' keys, or None.

    Returns:
        Prompt text instructing the AI how to handle labels.
    """
    if not labels:
        return "No labels are available; omit labelIds."

    label_lines = [
        f"- {label['name']} (id: {label['id']})"
        for label in labels
        if label.get("id") and label.get("name")
    ]

    if not label_lines:
        return "No labels are available; omit labelIds."

    return (
        "IMPORTANT: You MUST assign appropriate labelIds from this list to each item. "
        "Select all labels that apply to each item. Available labels:\n"
        + "\n".join(label_lines)
    )

