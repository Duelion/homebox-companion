"""Homebox Companion - AI-powered tools for Homebox inventory management.

This package provides utilities for enhancing your Homebox experience
with AI capabilities, including item detection from images.

Quick Start:
    >>> from homebox_companion import detect_items_from_bytes, HomeboxClient
    >>>
    >>> # Detect items in an image (async)
    >>> items = await detect_items_from_bytes(image_bytes)
    >>> for item in items:
    ...     print(f"{item.name}: {item.quantity}")
    >>>
    >>> # Create items in Homebox
    >>> async with HomeboxClient() as client:
    ...     response = await client.login("user@example.com", "password")
    ...     token = response["token"]
    ...     for item in items:
    ...         item.location_id = "your-location-id"
    ...         payload = item.model_dump(by_alias=True)
    ...         await client.create_item(token, payload)

Environment Variables:
    HBC_LLM_API_KEY: API key for the LLM provider (preferred)
    HBC_LLM_MODEL: LLM model identifier (preferred)
    HBC_LLM_API_BASE: Optional custom API base URL
    HBC_OPENAI_API_KEY: Legacy fallback for API key
    HBC_OPENAI_MODEL: Legacy fallback for model (default: gpt-5-mini)
    HBC_SERVER_HOST: Server host (default: 0.0.0.0)
    HBC_SERVER_PORT: Server port (default: 8000)
    HBC_LOG_LEVEL: Logging level (default: INFO)
"""

from importlib.metadata import PackageNotFoundError, version

# Get version from package metadata (set in pyproject.toml)
try:
    __version__ = version("homebox-companion")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

# Core
# AI utilities
from .ai import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMServiceError,
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
)
from .core import (
    HomeboxAuthError,
    HomeboxCompanionError,
    HomeboxConnectionError,
    HomeboxTimeoutError,
    Settings,
    logger,
    settings,
    setup_logging,
)

# Homebox client
from .homebox import (
    Attachment,
    HomeboxClient,
    Item,
    ItemCreate,
    ItemUpdate,
    Label,
    Location,
)

# Vision tool
from .tools.vision import (
    DetectedItem,
    analyze_item_details_from_images,
    correct_item,
    detect_items_from_bytes,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "settings",
    "Settings",
    "logger",
    "setup_logging",
    # Domain exceptions
    "HomeboxCompanionError",
    "HomeboxAuthError",
    "HomeboxConnectionError",
    "HomeboxTimeoutError",
    # LLM exceptions
    "LLMServiceError",
    "CapabilityNotSupportedError",
    "JSONRepairError",
    # Homebox client
    "HomeboxClient",
    "Location",
    "Label",
    "Item",
    "ItemCreate",
    "ItemUpdate",
    "Attachment",
    # Vision tool
    "DetectedItem",
    "detect_items_from_bytes",
    "analyze_item_details_from_images",
    "correct_item",
    # Image utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
    "encode_compressed_image_to_base64",
]
