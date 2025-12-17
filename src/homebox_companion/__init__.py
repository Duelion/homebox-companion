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
    ...     token = await client.login("user@example.com", "password")
    ...     for item in items:
    ...         item.location_id = "your-location-id"
    ...         await client.create_item(token, item.to_create_payload())

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
    LLMError,
    ModelNotAllowedError,
    cleanup_openai_clients,
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
)
from .core import (
    AuthenticationError,
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
    correct_item_with_openai,
    detect_items_from_bytes,
    discriminatory_detect_items,
    merge_items_with_openai,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "settings",
    "Settings",
    "logger",
    "setup_logging",
    "AuthenticationError",
    # LLM exceptions
    "LLMError",
    "ModelNotAllowedError",
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
    "discriminatory_detect_items",
    "analyze_item_details_from_images",
    "merge_items_with_openai",
    "correct_item_with_openai",
    # Image utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
    "encode_compressed_image_to_base64",
    "cleanup_openai_clients",
]





