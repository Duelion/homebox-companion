"""AI/LLM integration module."""

from .images import encode_image_bytes_to_data_uri, encode_image_to_data_uri
from .openai import chat_completion, vision_completion
from .prompts import (
    EXTENDED_FIELDS_SCHEMA,
    ITEM_SCHEMA,
    NAMING_RULES,
    build_label_prompt,
)

__all__ = [
    # Image utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
    # OpenAI helpers
    "chat_completion",
    "vision_completion",
    # Prompts
    "NAMING_RULES",
    "ITEM_SCHEMA",
    "EXTENDED_FIELDS_SCHEMA",
    "build_label_prompt",
]






