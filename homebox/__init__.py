"""Public API for the Homebox demo helper library."""
from .client import DEFAULT_HEADERS, DEMO_BASE_URL, HomeboxDemoClient
from .llm import detect_items_with_openai, encode_image_to_data_uri
from .models import DetectedItem

__all__ = [
    "DEMO_BASE_URL",
    "DEFAULT_HEADERS",
    "DetectedItem",
    "HomeboxDemoClient",
    "detect_items_with_openai",
    "encode_image_to_data_uri",
]
