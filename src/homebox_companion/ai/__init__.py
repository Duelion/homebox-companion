"""AI/LLM integration module."""

from .images import encode_image_bytes_to_data_uri, encode_image_to_data_uri
from .openai import chat_completion, cleanup_openai_clients, vision_completion
from .prompts import (
    FIELD_DEFAULTS,
    NAMING_FORMAT,
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_naming_rules,
)

__all__ = [
    # Image utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
    # OpenAI helpers
    "chat_completion",
    "vision_completion",
    "cleanup_openai_clients",
    # Prompts
    "NAMING_FORMAT",
    "FIELD_DEFAULTS",
    "build_label_prompt",
    "build_item_schema",
    "build_extended_fields_schema",
    "build_naming_rules",
    "build_critical_constraints",
]
