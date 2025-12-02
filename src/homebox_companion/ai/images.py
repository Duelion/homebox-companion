"""Image encoding utilities for AI/LLM APIs."""

from __future__ import annotations

import base64
from pathlib import Path


def encode_image_to_data_uri(image_path: Path | str) -> str:
    """Read an image file and return a data URI for OpenAI's vision API.

    Args:
        image_path: Path to the image file.

    Returns:
        A data URI string (e.g., "data:image/jpeg;base64,...").
    """
    path = Path(image_path)
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def encode_image_bytes_to_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Encode raw image bytes to a data URI for OpenAI's vision API.

    Args:
        image_bytes: Raw image data.
        mime_type: MIME type of the image.

    Returns:
        A data URI string.
    """
    suffix = mime_type.split("/")[-1] if "/" in mime_type else "jpeg"
    payload = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"

