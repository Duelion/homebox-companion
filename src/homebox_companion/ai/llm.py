"""LLM completion functions for chat and vision tasks.

This module provides high-level completion functions that:
- Validate model capabilities (vision, json_mode, multi-image)
- Handle response format negotiation based on model support
- Delegate to json_completion for JSON parsing/repair
- Route through the LiteLLM Router for provider fallback

Public API:
    chat_completion(messages, ...) -> dict
    vision_completion(system_prompt, user_prompt, images, ...) -> dict
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..core import config
from ..core.exceptions import CapabilityNotSupportedError, LLMServiceError
from .json_completion import json_completion
from .model_capabilities import get_model_capabilities


def _resolve_model_for_capabilities() -> str | None:
    """Resolve model name for capability checks.

    Uses the shared resolve_llm_credentials() utility for consistency with
    the actual model that will be used. This ensures capability checks
    match the resolved model from PRIMARY profile or environment.

    Returns:
        Resolved model name, or None if no model configured anywhere.
    """
    from ..core.llm_utils import resolve_llm_credentials

    creds = resolve_llm_credentials()
    return creds.model


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Send a chat completion request to the configured LLM.

    Args:
        messages: List of message dicts for the conversation.
        response_format: Optional response format (e.g., {"type": "json_object"}).
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        Parsed response content as a dictionary.

    Raises:
        LLMServiceError: For API or parsing errors.
    """
    # Determine response format based on model capabilities
    effective_response_format = response_format
    if not config.settings.llm_allow_unsafe_models and response_format:
        resolved_model = _resolve_model_for_capabilities()
        if resolved_model:
            caps = get_model_capabilities(resolved_model)
            if response_format.get("type") == "json_object" and not caps.json_mode:
                logger.debug(f"Model {resolved_model} doesn't support json_mode, using prompt-only JSON")
                effective_response_format = None

    return await json_completion(
        messages,
        response_format=effective_response_format,
        expected_keys=expected_keys,
    )


async def vision_completion(
    system_prompt: str,
    user_prompt: str,
    image_data_uris: list[str],
    *,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Send a vision completion request with images to the LLM.

    Args:
        system_prompt: The system message content.
        user_prompt: The user message text content.
        image_data_uris: List of base64-encoded image data URIs.
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        Parsed response content as a dictionary.

    Raises:
        ValueError: If image_data_uris is empty.
        CapabilityNotSupportedError: If model doesn't support vision.
        LLMServiceError: For API or parsing errors.
    """
    if not image_data_uris:
        raise ValueError("vision_completion requires at least one image")

    # Resolve model for capability checks
    resolved_model = _resolve_model_for_capabilities()

    # Determine capabilities and response format
    response_format: dict[str, str] | None = None

    if config.settings.llm_allow_unsafe_models:
        # Without validation, try json_mode by default
        response_format = {"type": "json_object"}
        logger.debug(f"Skipping capability validation for model '{resolved_model}' (HBC_LLM_ALLOW_UNSAFE_MODELS=true)")
    else:
        # Validate model capabilities
        if not resolved_model:
            raise LLMServiceError(
                "No model configured for vision request. Set HBC_LLM_MODEL environment variable "
                "or configure a PRIMARY LLM profile in Settings."
            )

        caps = get_model_capabilities(resolved_model)

        logger.debug(
            f"Model '{resolved_model}' capabilities for vision request: "
            f"vision={caps.vision}, json_mode={caps.json_mode}, multi_image={caps.multi_image}"
        )

        if not caps.vision:
            raise CapabilityNotSupportedError(
                f"Model '{resolved_model}' does not support vision (image inputs).\n\n"
                f"Homebox Companion requires a vision-capable model to analyze item photos. "
                f"LiteLLM reports that '{resolved_model}' does not have vision capabilities.\n\n"
                f"Possible reasons:\n"
                f"  • The model name is incorrect or misspelled\n"
                f"  • The model doesn't support image inputs (text-only model)\n"
                f"  • The provider prefix is missing (e.g., 'openai/' or 'openrouter/')\n\n"
                f"Officially supported models:\n"
                f"  • gpt-5-mini (default, recommended)\n"
                f"  • gpt-5-nano (lower cost per token, but generates more tokens)\n\n"
                f"Note: While LiteLLM supports many vision models "
                f"(GPT-4o, Claude 3, Gemini, etc.), "
                f"this app is tested and optimized for gpt-5 series models. "
                f"Other models may work but are not officially supported.\n\n"
                f"If you're using a different vision-capable model and want to "
                f"bypass this check, "
                f"set HBC_LLM_ALLOW_UNSAFE_MODELS=true "
                f"(use with caution - the model must actually support vision).\n\n"
                f"Configure your model via the HBC_LLM_MODEL environment variable."
            )

        if len(image_data_uris) > 1 and not caps.multi_image:
            raise CapabilityNotSupportedError(
                f"Model '{resolved_model}' does not support multiple images in a "
                f"single request.\n\n"
                f"You're trying to analyze {len(image_data_uris)} images at once, "
                f"but LiteLLM reports "
                f"that '{resolved_model}' only supports single-image inputs.\n\n"
                f"Officially supported multi-image models:\n"
                f"  • gpt-5-mini (default, recommended)\n"
                f"  • gpt-5-nano\n\n"
                f"These models can analyze multiple images simultaneously "
                f"for better context and accuracy.\n\n"
                f"Alternative solutions:\n"
                f"  • Use one of the supported models above\n"
                f"  • Process images one at a time "
                f"(less efficient but may work with your model)\n"
                f"  • Set HBC_LLM_ALLOW_UNSAFE_MODELS=true to bypass this check "
                f"(use with caution)\n\n"
                f"Configure your model via the HBC_LLM_MODEL environment variable."
            )

        if caps.json_mode:
            response_format = {"type": "json_object"}
        else:
            logger.debug(f"Model {resolved_model} doesn't support json_mode, using prompt-only JSON")

    # Build content list with text and images
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]

    for data_uri in image_data_uris:
        content.append({"type": "image_url", "image_url": {"url": data_uri}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    return await json_completion(
        messages,
        response_format=response_format,
        expected_keys=expected_keys,
    )
