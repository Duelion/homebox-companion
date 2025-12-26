"""AI/LLM integration module."""

from .images import (
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    encode_image_to_data_uri,
)
from .llm import (
    LLMError,  # Re-exported from core.exceptions via llm.py
    chat_completion,
    cleanup_llm_clients,
    cleanup_openai_clients,
    vision_completion,
)

# Import LLM exceptions from core.exceptions (canonical location)
from ..core.exceptions import (
    CapabilityNotSupportedError,
    JSONRepairError,
)
from .model_capabilities import ModelCapabilities, get_model_capabilities
from .prompts import (
    build_critical_constraints,
    build_extended_fields_schema,
    build_item_schema,
    build_label_prompt,
    build_naming_examples,
)

__all__ = [
    # Image utilities
    "encode_image_to_data_uri",
    "encode_image_bytes_to_data_uri",
    "encode_compressed_image_to_base64",
    # LLM helpers
    "chat_completion",
    "vision_completion",
    "cleanup_llm_clients",
    "cleanup_openai_clients",  # Deprecated alias
    # LLM exceptions
    "LLMError",
    "CapabilityNotSupportedError",
    "JSONRepairError",
    # Model capabilities
    "ModelCapabilities",
    "get_model_capabilities",
    # Prompts
    "build_label_prompt",
    "build_item_schema",
    "build_extended_fields_schema",
    "build_naming_examples",
    "build_critical_constraints",
]
