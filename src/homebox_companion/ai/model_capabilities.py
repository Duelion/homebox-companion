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
        structured_output: Whether the model supports structured output
            (json_schema response format). Uses LiteLLM's
            supports_response_schema() which checks for json_schema support.
    """

    model: str
    vision: bool = False
    multi_image: bool = False
    structured_output: bool = False


@lru_cache(maxsize=32)
def get_model_capabilities(model: str) -> ModelCapabilities:
    """Query LiteLLM for model capabilities.

    Args:
        model: Model identifier (e.g., "gpt-4o", "openrouter/anthropic/claude-3.5-sonnet").

    Returns:
        ModelCapabilities with vision, multi_image, and structured_output flags.

    Note:
        ``supports_response_schema()`` checks for json_schema support,
        which is stored as ``structured_output``.

        Results are cached to avoid repeated capability checks for the same model.

        The result is stored as ``structured_output`` (not ``json_mode``)
        because ``supports_response_schema()`` specifically checks for
        json_schema support, not the weaker json_object mode.
    """
    logger.info(f"Checking capabilities for model: {model}")

    vision = litellm.supports_vision(model)

    # Note: multi_image is assumed True for vision models. Most modern vision
    # models (GPT-4o, Claude 3, Gemini) support multiple images. If a specific
    # model doesn't, it will fail at runtime with a clear error from the provider.
    multi_image = vision

    structured_output = litellm.supports_response_schema(model)

    logger.debug(
        f"Model '{model}' capabilities detected: "
        f"vision={vision}, structured_output={structured_output}, multi_image={multi_image}"
    )

    # Warn if model string looks like it might be a vision model but doesn't
    # have vision support. This helps catch misconfigured model names
    # (e.g., missing provider prefix)
    vision_keywords = ["vision", "gpt-4o", "gpt-5", "claude-3", "gemini", "llava"]
    if not vision and any(keyword in model.lower() for keyword in vision_keywords):
        logger.warning(
            f"Model '{model}' appears to be a vision model based on its name, "
            f"but LiteLLM reports it doesn't support vision. "
            f"This may indicate an incorrect model identifier. "
            f"Try prefixing with provider "
            f"(e.g., 'openai/{model}' or 'openrouter/...')."
        )

    return ModelCapabilities(
        model=model,
        vision=vision,
        multi_image=multi_image,
        structured_output=structured_output,
    )
