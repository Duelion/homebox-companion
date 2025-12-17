"""AI/LLM integration module."""

from .images import (
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
)
from .model_allowlist import ModelCapabilities, get_model_capabilities
from .openai import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMError,
    ModelNotAllowedError,
    chat_completion,
    cleanup_openai_clients,
    vision_completion,
)
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
    "encode_compressed_image_to_base64",
    # LLM helpers
    "chat_completion",
    "vision_completion",
    "cleanup_openai_clients",
    # LLM exceptions
    "LLMError",
    "ModelNotAllowedError",
    "CapabilityNotSupportedError",
    "JSONRepairError",
    # Allowlist
    "ModelCapabilities",
    "get_model_capabilities",
    # Prompts
    "NAMING_FORMAT",
    "FIELD_DEFAULTS",
    "build_label_prompt",
    "build_item_schema",
    "build_extended_fields_schema",
    "build_naming_rules",
    "build_critical_constraints",
]
