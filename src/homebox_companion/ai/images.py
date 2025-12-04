"""Image encoding and optimization utilities for AI/LLM APIs."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from loguru import logger
from PIL import Image

# Default settings for image optimization
DEFAULT_MAX_DIMENSION = 2048  # OpenAI recommends max 2048px for detail="high"
DEFAULT_JPEG_QUALITY = 85


def optimize_image_for_vision(
    image_bytes: bytes,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> tuple[bytes, str]:
    """Optimize an image for LLM vision processing.

    Resizes large images and compresses to JPEG for faster uploads and
    reduced token costs. OpenAI's vision API works best with images
    up to 2048px on the longest side.

    Args:
        image_bytes: Raw image data.
        max_dimension: Maximum width or height in pixels.
        quality: JPEG compression quality (1-100).

    Returns:
        Tuple of (optimized_bytes, mime_type).
    """
    original_size = len(image_bytes)

    try:
        img = Image.open(io.BytesIO(image_bytes))
        original_dimensions = img.size

        # Handle EXIF orientation
        try:
            from PIL import ExifTags

            for orientation in ExifTags.TAGS:
                if ExifTags.TAGS[orientation] == "Orientation":
                    break

            exif = img._getexif()
            if exif is not None:
                orientation_value = exif.get(orientation)
                if orientation_value == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_value == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_value == 8:
                    img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, TypeError):
            # No EXIF data or no orientation tag
            pass

        # Resize if larger than max dimension
        needs_resize = max(img.size) > max_dimension
        if needs_resize:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            logger.debug(
                f"Resized image from {original_dimensions} to {img.size}"
            )

        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if img.mode in ("RGBA", "P", "LA"):
            # Create white background for transparent images
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Compress to JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        optimized_bytes = output.getvalue()

        optimized_size = len(optimized_bytes)
        savings = ((original_size - optimized_size) / original_size) * 100

        if savings > 5:  # Only log if meaningful savings
            logger.debug(
                f"Image optimized: {original_size:,} -> {optimized_size:,} bytes "
                f"({savings:.1f}% reduction)"
            )

        return optimized_bytes, "image/jpeg"

    except Exception as e:
        logger.warning(f"Image optimization failed, using original: {e}")
        return image_bytes, "image/jpeg"


def encode_image_to_data_uri(image_path: Path | str, optimize: bool = True) -> str:
    """Read an image file and return a data URI for OpenAI's vision API.

    Args:
        image_path: Path to the image file.
        optimize: Whether to optimize the image for vision processing.

    Returns:
        A data URI string (e.g., "data:image/jpeg;base64,...").
    """
    path = Path(image_path)
    image_bytes = path.read_bytes()

    if optimize:
        image_bytes, mime_type = optimize_image_for_vision(image_bytes)
        suffix = "jpeg"
    else:
        suffix = path.suffix.lower().lstrip(".") or "jpeg"

    payload = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def encode_image_bytes_to_data_uri(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    optimize: bool = True,
) -> str:
    """Encode raw image bytes to a data URI for OpenAI's vision API.

    Args:
        image_bytes: Raw image data.
        mime_type: MIME type of the image.
        optimize: Whether to optimize the image for vision processing.

    Returns:
        A data URI string.
    """
    if optimize:
        image_bytes, mime_type = optimize_image_for_vision(image_bytes)
        suffix = "jpeg"
    else:
        suffix = mime_type.split("/")[-1] if "/" in mime_type else "jpeg"

    payload = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"




