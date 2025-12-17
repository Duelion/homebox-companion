"""Model capability checking using LiteLLM's built-in functions.

This module queries LiteLLM at runtime to determine model capabilities
(vision support, JSON schema support, etc.) rather than maintaining a
static allowlist.
"""

from __future__ import annotations

from dataclasses import dataclass

import litellm


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities for a model."""

    model: str
    vision: bool = False
    multi_image: bool = False
    json_mode: bool = False


def get_model_capabilities(model: str) -> ModelCapabilities:
    """Query LiteLLM for model capabilities.

    Args:
        model: Model identifier (e.g., "gpt-4o", "openrouter/anthropic/claude-3.5-sonnet").

    Returns:
        ModelCapabilities with vision, multi_image, and json_mode flags.

    Note:
        - Uses LiteLLM's supports_vision() to check for vision capability
        - Assumes all vision models support multiple images
        - Uses LiteLLM's supports_response_schema() to check for JSON schema support
    """
    vision = litellm.supports_vision(model)
    
    return ModelCapabilities(
        model=model,
        vision=vision,
        multi_image=vision,  # Assume all vision models support multi-image
        json_mode=litellm.supports_response_schema(model),
    )

