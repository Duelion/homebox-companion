"""Backward-compatible imports for the Homebox demo helpers.

.. deprecated::
    Import from the `homebox` package directly.
"""
from __future__ import annotations

from homebox import (
    DEFAULT_HEADERS,
    DEMO_BASE_URL,
    DetectedItem,
    HomeboxDemoClient,
    detect_items_with_openai,
    encode_image_to_data_uri,
)

__all__ = [
    "DEMO_BASE_URL",
    "DEFAULT_HEADERS",
    "DetectedItem",
    "HomeboxDemoClient",
    "detect_items_with_openai",
    "encode_image_to_data_uri",
]
