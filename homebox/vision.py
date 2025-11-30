"""AI-powered vision detection for Homebox items.

This module provides utilities for detecting items in images using
OpenAI's vision models.

Example:
    >>> import homebox
    >>> items = homebox.detect("photo.jpg")
    >>> for item in items:
    ...     print(f"{item.name} x{item.quantity}")
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from openai import OpenAI

from ._logging import logger
from .api import _DEFAULT_HEADERS, DEMO_URL
from .types import Item, Label

if TYPE_CHECKING:
    from collections.abc import Sequence

# Default model for vision tasks
DEFAULT_MODEL = "gpt-4o-mini"


def encode_image(image_path: str | Path) -> str:
    """Encode an image file as a base64 data URI.

    Args:
        image_path: Path to the image file.

    Returns:
        Data URI string suitable for OpenAI's vision API.

    Example:
        >>> uri = encode_image("photo.jpg")
        >>> uri.startswith("data:image/")
        True
    """
    path = Path(image_path)
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def detect(
    image: str | Path,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    labels: Sequence[Label | dict[str, str]] | None = None,
    fetch_labels: bool = True,
    homebox_url: str = DEMO_URL,
) -> list[Item]:
    """Detect items in an image using OpenAI's vision model.

    This is the primary function for AI-powered item detection. It
    analyzes an image and returns a list of detected items with names,
    quantities, and descriptions.

    Args:
        image: Path to the image file to analyze.
        api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model: OpenAI model to use (default: gpt-4o-mini).
        labels: Available labels to match items against. If None and
            fetch_labels is True, labels are fetched from the Homebox API.
        fetch_labels: Whether to fetch labels from the API (default True).
        homebox_url: Homebox API URL for fetching labels.

    Returns:
        List of detected Item objects.

    Raises:
        ValueError: If no API key is available.

    Example:
        >>> items = homebox.detect("tools.jpg")
        >>> for item in items:
        ...     print(f"{item.name}: {item.quantity}")
        Hammer: 2
        Screwdriver: 5
    """
    # Resolve API key
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "OpenAI API key required. Pass api_key or set OPENAI_API_KEY env var."
        )

    logger.debug("Detecting items in {} using model {}", image, model)

    # Encode image
    data_uri = encode_image(image)

    # Get labels for the prompt
    available_labels: list[Label] = []
    if labels is not None:
        available_labels = [
            Label.from_dict(lbl) if isinstance(lbl, dict) else lbl
            for lbl in labels
        ]
    elif fetch_labels:
        available_labels = _fetch_labels(homebox_url)

    # Build the prompt
    label_prompt = _build_label_prompt(available_labels)

    # Call OpenAI
    client = OpenAI(api_key=key)
    logger.debug("Calling OpenAI vision API...")

    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": _build_system_prompt(label_prompt),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )

    # Parse response
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    parsed = getattr(message, "parsed", None) or json.loads(raw_content)
    raw_items = parsed.get("items", [])

    items = Item.from_list(raw_items)
    logger.info("Detected {} items in image", len(items))

    for item in items:
        logger.debug("  - {} x{}", item.name, item.quantity)

    return items


def _fetch_labels(homebox_url: str) -> list[Label]:
    """Fetch available labels from the Homebox API."""
    import requests

    try:
        response = requests.get(
            f"{homebox_url.rstrip('/')}/labels",
            headers=_DEFAULT_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        return Label.from_list(response.json())
    except Exception as e:
        logger.warning("Could not fetch labels: {}", e)
        return []


def _build_label_prompt(labels: list[Label]) -> str:
    """Build the label section of the prompt."""
    if not labels:
        return "No labels are available; omit labelIds."
    return "\n".join(f"- {label.name} (id: {label.id})" for label in labels)


def _build_system_prompt(label_prompt: str) -> str:
    """Build the system prompt for item detection."""
    return (
        "You are an inventory assistant for the Homebox API. "
        "Return a single JSON object with an `items` array. Each item must "
        "include: `name` (<=255 characters), integer `quantity` (>=1), and "
        "optional `description` (<=1000 characters) summarizing condition or "
        "notable attributes. Combine identical objects into a single entry "
        "with the correct quantity. Do not add extra commentary. Ignore "
        "background elements (floors, walls, benches, shelves, packaging, "
        "labels, shadows) and only count objects that are the clear focus of "
        "the image. When possible, set `labelIds` using the exact IDs from "
        "the available labels list. If none match, omit `labelIds`. Available "
        f"labels:\n{label_prompt}"
    )


_USER_PROMPT = (
    "List all distinct items that are the logical focus of this image "
    "and ignore background objects or incidental surfaces. Return only "
    'JSON. Example format: {"items":[{"name":"hammer","quantity":2,'
    '"description":"Steel head with wooden handle"}]}.'
)


class VisionClient:
    """Client for AI-powered item detection.

    This class provides a reusable client for detecting items in images.
    It's useful when you want to configure settings once and reuse them.

    Args:
        api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model: OpenAI model to use.
        homebox_url: Homebox API URL for fetching labels.

    Example:
        >>> vision = homebox.VisionClient()
        >>> items1 = vision.detect("photo1.jpg")
        >>> items2 = vision.detect("photo2.jpg")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        homebox_url: str = DEMO_URL,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.homebox_url = homebox_url
        self._openai: OpenAI | None = None
        self._labels: list[Label] | None = None

    @property
    def api_key(self) -> str:
        """Get the OpenAI API key."""
        key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OpenAI API key required. Pass api_key or set OPENAI_API_KEY env var."
            )
        return key

    @property
    def openai(self) -> OpenAI:
        """Get the OpenAI client (lazily initialized)."""
        if self._openai is None:
            self._openai = OpenAI(api_key=self.api_key)
        return self._openai

    def labels(self, *, refresh: bool = False) -> list[Label]:
        """Get available labels (cached after first fetch).

        Args:
            refresh: Force refresh from the API.
        """
        if self._labels is None or refresh:
            self._labels = _fetch_labels(self.homebox_url)
        return self._labels

    def detect(
        self,
        image: str | Path,
        *,
        labels: Sequence[Label | dict[str, str]] | None = None,
    ) -> list[Item]:
        """Detect items in an image.

        Args:
            image: Path to the image file.
            labels: Override labels (uses cached labels if None).

        Returns:
            List of detected Items.
        """
        return detect(
            image,
            api_key=self.api_key,
            model=self.model,
            labels=labels if labels is not None else self.labels(),
            fetch_labels=False,
            homebox_url=self.homebox_url,
        )


# -------------------------------------------------------------------------
# Backwards compatibility
# -------------------------------------------------------------------------

# Alias for backwards compatibility
encode_image_to_data_uri = encode_image


class HomeboxLLMClient(VisionClient):
    """Legacy client for backwards compatibility.

    .. deprecated::
        Use :class:`VisionClient` or :func:`detect` instead.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        homebox_base_url: str = DEMO_URL,
    ) -> None:
        super().__init__(api_key=api_key, model=model, homebox_url=homebox_base_url)

    def fetch_labels(self) -> list[dict[str, str]]:
        """Fetch available labels (legacy format)."""
        labels = self.labels(refresh=True)
        return [{"id": lbl.id, "name": lbl.name} for lbl in labels]

    def detect_items(self, image_path: Path) -> list[Item]:
        """Detect items in an image (legacy method)."""
        return self.detect(image_path)


def detect_items_with_openai(
    image_path: Path,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> list[Item]:
    """Legacy function for detecting items.

    .. deprecated::
        Use :func:`detect` instead.
    """
    return detect(image_path, api_key=api_key, model=model)


__all__ = [
    "DEFAULT_MODEL",
    "detect",
    "encode_image",
    "encode_image_to_data_uri",
    "VisionClient",
    "HomeboxLLMClient",
    "detect_items_with_openai",
]
