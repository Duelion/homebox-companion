"""Model capability checking using LiteLLM's built-in functions.

This module queries LiteLLM at runtime to determine model capabilities
(vision support, JSON output support, etc.) rather than maintaining a
static allowlist.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import litellm
from loguru import logger


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities for a model.

    Attributes:
        model: The model identifier string.
        vision: Whether the model supports image inputs.
        multi_image: Whether the model supports multiple images per request.
            Currently assumed True for all vision models; most modern vision
            models support this, but some may have limits on image count.
        json_mode: Whether the model supports JSON output mode.
            Uses LiteLLM's supports_response_schema() which checks for
            structured output support. Models supporting structured outputs
            also support basic JSON mode (response_format: {"type": "json_object"}).
    """

    model: str
    vision: bool = False
    multi_image: bool = False
    json_mode: bool = False


@lru_cache(maxsize=32)
def get_model_capabilities(model: str) -> ModelCapabilities:
    """Query LiteLLM for model capabilities.

    Args:
        model: Model identifier (e.g., "gpt-4o", "openrouter/anthropic/claude-3.5-sonnet").

    Returns:
        ModelCapabilities with vision, multi_image, and json_mode flags.

    Note:
        LiteLLM's supports_response_schema() is used for json_mode because:
        1. Models supporting structured outputs always support basic JSON mode
        2. LiteLLM doesn't expose a separate "supports_json_mode" function
        3. This is the most reliable capability check available
        
        Results are cached to avoid repeated capability checks for the same model.
    """
    logger.info(f"Checking capabilities for model: {model}")
    
    vision = litellm.supports_vision(model)

    # Note: multi_image is assumed True for vision models. Most modern vision
    # models (GPT-4o, Claude 3, Gemini) support multiple images. If a specific
    # model doesn't, it will fail at runtime with a clear error from the provider.
    multi_image = vision

    # supports_response_schema checks for structured output support, which
    # implies basic JSON mode support (response_format: {"type": "json_object"})
    json_mode = litellm.supports_response_schema(model)

    logger.debug(
        f"Model '{model}' capabilities detected: "
        f"vision={vision}, json_mode={json_mode}, multi_image={multi_image}"
    )
    
    # Warn if model string looks like it might be a vision model but doesn't have vision support
    # This helps catch misconfigured model names (e.g., missing provider prefix)
    if not vision and any(keyword in model.lower() for keyword in ['vision', 'gpt-4o', 'gpt-5', 'claude-3', 'gemini', 'llava']):
        logger.warning(
            f"Model '{model}' appears to be a vision model based on its name, "
            f"but LiteLLM reports it doesn't support vision. This may indicate an incorrect model identifier. "
            f"Try prefixing with provider (e.g., 'openai/{model}' or 'openrouter/...')."
        )

    return ModelCapabilities(
        model=model,
        vision=vision,
        multi_image=multi_image,
        json_mode=json_mode,
    )

