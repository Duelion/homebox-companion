"""Public API for the Homebox demo helper library."""
from .client import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    DEMO_BASE_URL,
    AsyncHomeboxClient,
    HomeboxClient,
    HomeboxDemoClient,
)
from .llm import (
    detect_items_from_bytes,
    detect_items_with_openai,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
    fetch_demo_labels,
    fetch_demo_labels_async,
)
from .models import DetectedItem

__all__ = [
    "DEMO_BASE_URL",
    "DEFAULT_HEADERS",
    "DEFAULT_TIMEOUT",
    "AsyncHomeboxClient",
    "DetectedItem",
    "HomeboxClient",
    "HomeboxDemoClient",
    "detect_items_from_bytes",
    "detect_items_with_openai",
    "encode_image_bytes_to_data_uri",
    "encode_image_to_data_uri",
    "fetch_demo_labels",
    "fetch_demo_labels_async",
]
