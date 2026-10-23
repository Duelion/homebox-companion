"""Homebox v0.26.2/v0.27.0 repo.AssetID JSON contract.

https://github.com/sysadminsmedia/homebox/blob/v0.27.0/backend/internal/data/repo/asset_id_type.go
Hyphens are removed before int64 parsing. Blank leaves automatic assignment enabled.
"""

import re

ASSET_ID_ERROR = "Enter a numeric Homebox asset ID (for example, 032-303), or leave it blank."


def normalize_asset_id(value: object) -> str:
    """Validate user input and return Homebox's display format without float rounding."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(ASSET_ID_ERROR)
    value = value.strip()
    if not value:
        return ""
    digits = value.replace("-", "")
    if not re.fullmatch(r"\+?[0-9]+", digits):
        raise ValueError(ASSET_ID_ERROR)
    # Avoid Python's integer-string limit for malformed, arbitrarily long input.
    significant = digits.lstrip("+0") or "0"
    if len(significant) > 19 or int(significant) > 9223372036854775807:
        raise ValueError(ASSET_ID_ERROR)
    if significant == "0":
        return "0"
    padded = significant.zfill(6)
    return f"{padded[:3]}-{padded[3:]}"
