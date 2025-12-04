"""Shared prompt templates and constants for AI interactions."""

from __future__ import annotations

# Shared naming rules for consistent LLM output across all functions
NAMING_RULES = """NAMING GUIDELINES (follow for consistency):

STRUCTURE (preferred order):
[Item Type] [Brand/Series] [Model] [Variant/Specs]

Examples:
- "Ball Bearing 6900-2RS 10x22x6mm" (type + model + specs)
- "Acrylic Paint Vallejo Game Color Bone White 72.034" (type + brand + series + color + code)
- "E-Paper Module WeAct 2.9 Inch Black/White" (type + brand + size + variant)
- "Safety Pin Silver 55mm" (type + material/color + size)
- "LED Strip COB Green 5V 1M" (type + subtype + color + specs)

RULES:
- Use Title Case (e.g., "Claw Hammer", not "claw hammer")
- Do NOT include quantity in name or description
- Include brand ONLY when recognizable/valuable (Vallejo, DeWalt, Raspberry Pi)
- Omit generic manufacturer names (e.g., "Shenzhen XYZ Technology Co.")
- Use metric units, format dimensions as NxNxNmm (e.g., "10x22x6mm", not "10 x 22 x 6 mm")
- Place color/variant at end when distinguishing similar items
- Keep names concise (max 255 chars) - prioritize searchability
- Omit container words (Bottle, Bag, Box) unless part of product identity

ITEM TYPE FIRST - The most important word for search/sort should come first:
- Good: "Ball Bearing 6900-2RS" (searchable by "Ball Bearing")
- Avoid: "6900-2RS Ball Bearing" (harder to find in alphabetical lists)"""

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
- notes: string or null (ONLY for defects, damage, or warnings - leave null for normal items)
  GOOD notes: "Cracked lens", "Missing 2 screws", "Battery corroded", "Requires 12V adapter"
  BAD notes: "Sealed in packaging", "Made in China", "Appears new", "Barcode visible"

CRITERIA FOR EXTENDED FIELDS (IMPORTANT):
- DO NOT guess or infer fields you cannot see clearly
- manufacturer: Include ONLY when brand/logo is VISIBLE (e.g., "DeWalt" visible on tool)
- modelNumber: Include ONLY when model/part number TEXT is VISIBLE (e.g., "DCD771C2" on label)
- serialNumber: Include ONLY when S/N text is VISIBLE (usually on sticker/label)
- purchasePrice: Include ONLY if price tag/receipt is IN THE IMAGE
- purchaseFrom: Include ONLY if retailer name is visible (e.g., "Home Depot" on packaging)
- notes: Include ONLY for defects/damage/warnings - most items should have null notes

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





