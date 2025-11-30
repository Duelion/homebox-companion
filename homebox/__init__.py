"""Homebox: A Pythonic library for inventory management.

A human-friendly library for interacting with the Homebox API and
detecting items in images using AI.

Quick Start:
    >>> import homebox
    >>>
    >>> # Connect to Homebox (uses demo credentials by default)
    >>> with homebox.Session() as hb:
    ...     # Get locations
    ...     locations = hb.locations()
    ...     print(f"Found {len(locations)} locations")
    ...
    ...     # Create an item
    ...     item = hb.create_item("Hammer", quantity=2, location=locations[0])
    ...     print(f"Created: {item.name} (id: {item.id})")

    >>> # Detect items in an image with AI
    >>> items = homebox.detect("tools.jpg")
    >>> for item in items:
    ...     print(f"{item.name} x{item.quantity}")

Configuration:
    >>> # Set log level
    >>> homebox.configure(level="DEBUG")
    >>>
    >>> # Use custom Homebox instance
    >>> hb = homebox.Session(url="https://my-homebox.example.com/api/v1")
"""
from __future__ import annotations

# Logging
from ._logging import configure, get_logger, logger

# Core API
from .api import (
    DEFAULT_HEADERS,
    DEMO_BASE_URL,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    DEMO_URL,
    AuthenticationError,
    HomeboxDemoClient,
    HomeboxError,
    Session,
)

# Types
from .types import (
    DetectedItem,
    Item,
    Label,
    Location,
)

# Vision/AI
from .vision import (
    DEFAULT_MODEL,
    HomeboxLLMClient,
    VisionClient,
    detect,
    detect_items_with_openai,
    encode_image,
    encode_image_to_data_uri,
)

__version__ = "0.3.0"

__all__ = [
    # Version
    "__version__",
    # Session & API
    "Session",
    "HomeboxError",
    "AuthenticationError",
    # Types
    "Item",
    "Location",
    "Label",
    # Vision/AI
    "detect",
    "encode_image",
    "VisionClient",
    "DEFAULT_MODEL",
    # Logging
    "configure",
    "get_logger",
    "logger",
    # Constants
    "DEMO_URL",
    "DEMO_EMAIL",
    "DEMO_PASSWORD",
    # Backwards compatibility
    "DEMO_BASE_URL",
    "DEFAULT_HEADERS",
    "DetectedItem",
    "HomeboxDemoClient",
    "HomeboxLLMClient",
    "detect_items_with_openai",
    "encode_image_to_data_uri",
]
