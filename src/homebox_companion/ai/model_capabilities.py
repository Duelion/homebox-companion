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

# Known Ollama vision models - these support image inputs but LiteLLM's
# capability database doesn't recognize them. Add new models here as needed.
OLLAMA_VISION_MODELS = frozenset({
    # MiniCPM-V variants
    "minicpm-v",
    "minicpm-v:latest",
    "minicpm-v:8b",
    "minicpm-v:8b-2.6",
    # LLaVA variants
    "llava",
    "llava:latest",
    "llava:7b",
    "llava:13b",
    "llava:34b",
    "llava-llama3",
    "llava-phi3",
    # BakLLaVA
    "bakllava",
    "bakllava:latest",
    # LLaVA-NeXT (improved LLaVA)
    "llava-next",
    # Moondream (small vision model)
    "moondream",
    "moondream:latest",
    "moondream2",
    # Qwen2-VL variants
    "qwen2-vl",
    "qwen2-vl:latest",
    "qwen2-vl:7b",
    "qwen2-vl:72b",
    # InternVL variants
    "internvl2",
    "internvl2:latest",
    # Pixtral (Mistral's vision model)
    "pixtral",
    "pixtral:latest",
})


def _is_ollama_vision_model(model: str) -> bool:
    """Check if model is a known Ollama vision model.

    Args:
        model: Model identifier, possibly with 'ollama/' prefix.

    Returns:
        True if the model is a known Ollama vision model.
    """
    # Strip 'ollama/' prefix if present
    model_name = model.lower()
    if model_name.startswith("ollama/"):
        model_name = model_name[7:]  # Remove 'ollama/' prefix

    # Check exact match first
    if model_name in OLLAMA_VISION_MODELS:
        return True

    # Check if base model name (without tag) matches
    base_name = model_name.split(":")[0]
    return base_name in OLLAMA_VISION_MODELS


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

        For Ollama models, we use a whitelist of known vision models since
        LiteLLM's capability database doesn't include Ollama models.
    """
    logger.info(f"Checking capabilities for model: {model}")

    # Check Ollama vision whitelist first (LiteLLM doesn't know about Ollama models)
    if _is_ollama_vision_model(model):
        logger.debug(f"Model '{model}' is a known Ollama vision model")
        return ModelCapabilities(
            model=model,
            vision=True,
            multi_image=True,
            json_mode=False,  # Ollama models generally don't support JSON mode well
        )

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
        json_mode=json_mode,
    )
