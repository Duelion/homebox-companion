"""AI-powered tools for Homebox Companion.

This module contains the various tools that can be used to enhance
the Homebox experience with AI capabilities.

Available tools:
- vision: Detect and analyze items from images
"""

from .base import BaseTool
from .vision import (
    DetectedItem,
    analyze_item_details_from_images,
    correct_item,
    detect_items_from_bytes,
)

__all__ = [
    # Base class
    "BaseTool",
    # Vision tool exports
    "DetectedItem",
    "detect_items_from_bytes",
    "analyze_item_details_from_images",
    "correct_item",
]
