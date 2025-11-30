"""Homebox Vision Companion - AI-powered item detection for Homebox.

This package provides utilities for detecting household items from images
using OpenAI's vision models and creating them in your Homebox instance.
"""

from .client import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    AsyncHomeboxClient,
    HomeboxClient,
)
from .config import settings
from .llm import (
    analyze_item_details_from_images,
    detect_items_from_bytes,
    detect_items_with_openai,
    discriminatory_detect_items,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
    merge_items_with_openai,
)
from .models import DetectedItem

__version__ = "0.5.0"

__all__ = [
    # Configuration
    "settings",
    # Client classes
    "AsyncHomeboxClient",
    "HomeboxClient",
    # Models
    "DetectedItem",
    # LLM utilities
    "analyze_item_details_from_images",
    "detect_items_from_bytes",
    "detect_items_with_openai",
    "discriminatory_detect_items",
    "encode_image_bytes_to_data_uri",
    "encode_image_to_data_uri",
    "merge_items_with_openai",
    # Constants
    "DEFAULT_HEADERS",
    "DEFAULT_TIMEOUT",
]

