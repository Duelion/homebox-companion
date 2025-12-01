"""Homebox Vision Companion - AI-powered item detection for Homebox.

This package provides utilities for detecting household items from images
using OpenAI's vision models and creating them in your Homebox instance.

Quick Start:
    >>> from homebox_vision import detect_items, HomeboxClient
    >>>
    >>> # Detect items in an image
    >>> items = detect_items("photo.jpg")
    >>> for item in items:
    ...     print(f"{item.name}: {item.quantity}")
    >>>
    >>> # Create items in Homebox
    >>> with HomeboxClient() as client:
    ...     token = client.login("user@example.com", "password")
    ...     for item in items:
    ...         item.location_id = "your-location-id"
    ...         client.create_item(token, item)

For async contexts (FastAPI, etc.), use the async functions directly:
    >>> from homebox_vision import detect_items_from_bytes, AsyncHomeboxClient
"""

from .client import AsyncHomeboxClient, AuthenticationError, HomeboxClient
from .config import settings
from .llm import (
    analyze_item_details_from_images,
    correct_item_with_openai,
    detect_items,
    detect_items_from_bytes,
    discriminatory_detect_items,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
    merge_items_with_openai,
)
from .models import DetectedItem

__version__ = "0.15.0"

__all__ = [
    # Configuration
    "settings",
    # Client classes (sync and async)
    "HomeboxClient",
    "AsyncHomeboxClient",
    # Exceptions
    "AuthenticationError",
    # Data models
    "DetectedItem",
    # Detection functions
    "detect_items",  # Sync - for scripts, simple use cases
    "detect_items_from_bytes",  # Async - for FastAPI, performance
    "discriminatory_detect_items",  # Async - for re-detection with specificity
    # Advanced AI functions (all async)
    "analyze_item_details_from_images",
    "correct_item_with_openai",
    "merge_items_with_openai",
    # Image encoding utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
]
