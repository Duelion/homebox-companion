"""LLM API client wrapper using LiteLLM for multi-provider support.

This module provides the low-level completion functions used by the rest of the
codebase. It abstracts away the underlying LLM provider (OpenAI, Anthropic, etc.)
using LiteLLM while maintaining a consistent API.
"""

from __future__ import annotations

import json
from typing import Any

import litellm
from loguru import logger

from ..core.config import settings
from .model_allowlist import get_model_capabilities

# Silence LiteLLM's verbose logging (we use loguru)
litellm.suppress_debug_info = True

# Default timeout for LLM API calls (in seconds)
DEFAULT_LLM_TIMEOUT = 120


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class ModelNotAllowedError(LLMError):
    """Raised when trying to use a model not in the allowlist."""

    pass


class CapabilityNotSupportedError(LLMError):
    """Raised when a model lacks a required capability."""

    pass


class JSONRepairError(LLMError):
    """Raised when JSON parsing fails even after repair attempt."""

    pass


def _format_messages_for_logging(messages: list[dict[str, Any]]) -> str:
    """Format messages for readable logging output.

    Args:
        messages: List of message dicts for the conversation.

    Returns:
        Formatted string representation of messages.
    """
    output_lines = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        if isinstance(content, str):
            output_lines.append(f"\n{'='*60}\n[{role}]\n{'='*60}\n{content}")
        elif isinstance(content, list):
            # Handle vision messages with mixed content
            text_parts = []
            image_count = 0
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    image_count += 1
            text_content = "\n".join(text_parts)
            image_note = f"\n[+ {image_count} image(s) attached]" if image_count else ""
            output_lines.append(
                f"\n{'='*60}\n[{role}]{image_note}\n{'='*60}\n{text_content}"
            )

    return "".join(output_lines)


def _build_repair_prompt(original_response: str, error_msg: str, expected_schema: str) -> str:
    """Build a prompt for JSON repair.

    Args:
        original_response: The malformed JSON response from the model.
        error_msg: The error message from JSON parsing.
        expected_schema: Description of expected JSON structure.

    Returns:
        A prompt that instructs the model to fix the JSON.
    """
    return f"""The previous response was not valid JSON. Please fix it and return ONLY valid JSON.

Error: {error_msg}

Original (malformed) response:
```
{original_response[:2000]}
```

Expected format: {expected_schema}

Return ONLY the corrected JSON object, nothing else."""


def _parse_json_response(
    raw_content: str,
    expected_keys: list[str] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Parse and validate JSON response.

    Args:
        raw_content: Raw string content from the model.
        expected_keys: Optional list of keys that should be present in the response.

    Returns:
        Tuple of (parsed dict, error_message or None).
    """
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        return {}, f"JSON parse error: {e.msg} at position {e.pos}"

    if not isinstance(parsed, dict):
        return {}, f"Expected JSON object, got {type(parsed).__name__}"

    if expected_keys:
        missing = [k for k in expected_keys if k not in parsed]
        if missing:
            return parsed, f"Missing required keys: {missing}"

    return parsed, None


async def _acompletion_with_repair(
    messages: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    api_base: str | None = None,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Call LiteLLM with optional JSON repair on failure.

    Args:
        messages: Chat messages.
        model: Model identifier.
        api_key: API key for the provider.
        api_base: Optional custom API base URL.
        response_format: Optional response format (e.g., {"type": "json_object"}).
        expected_keys: Keys to check in JSON response (triggers repair if missing).

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        JSONRepairError: If JSON parsing fails after repair attempt.
        LLMError: For other LLM-related errors.
    """
    # Build kwargs for litellm
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "api_key": api_key,
        "timeout": DEFAULT_LLM_TIMEOUT,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if response_format:
        kwargs["response_format"] = response_format

    # First attempt
    logger.debug(f"Calling LiteLLM with model: {model}")
    logger.trace(
        f">>> PROMPT SENT TO LLM ({model}) >>>"
        f"{_format_messages_for_logging(messages)}"
        f"\n{'='*60}"
    )

    try:
        completion = await litellm.acompletion(**kwargs)
    except litellm.AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        raise LLMError(f"Authentication failed. Check your API key. Error: {e}") from e
    except litellm.RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        raise LLMError(f"Rate limit exceeded. Please try again later. Error: {e}") from e
    except litellm.APIConnectionError as e:
        logger.error(f"Connection error: {e}")
        raise LLMError(f"Failed to connect to LLM API. Error: {e}") from e
    except litellm.Timeout as e:
        logger.error(f"Request timed out: {e}")
        raise LLMError(
            f"LLM request timed out after {DEFAULT_LLM_TIMEOUT}s. "
            f"The model may be overloaded. Error: {e}"
        ) from e
    except Exception as e:
        logger.exception(f"LLM call failed: {e}")
        raise LLMError(f"LLM request failed: {e}") from e

    raw_content = completion.choices[0].message.content or "{}"

    logger.trace(
        f"<<< RESPONSE FROM LLM ({model}) <<<"
        f"\n{'='*60}\n"
        f"{raw_content}"
        f"\n{'='*60}"
    )

    # Log token usage
    if completion.usage:
        logger.debug(
            f"LLM response received ({len(raw_content)} chars) | "
            f"Tokens: {completion.usage.total_tokens} total "
            f"({completion.usage.prompt_tokens} input, {completion.usage.completion_tokens} output)"
        )
    else:
        logger.debug(f"LLM response received ({len(raw_content)} chars)")

    # Parse and validate
    parsed, error = _parse_json_response(raw_content, expected_keys)
    if error is None:
        return parsed

    # Repair attempt (one retry only)
    logger.warning(f"JSON validation failed, attempting repair: {error}")

    expected_schema = "JSON object"
    if expected_keys:
        expected_schema = f"JSON object with keys: {expected_keys}"

    repair_prompt = _build_repair_prompt(raw_content, error, expected_schema)
    repair_messages = messages.copy()
    repair_messages.append({"role": "assistant", "content": raw_content})
    repair_messages.append({"role": "user", "content": repair_prompt})

    logger.debug("Sending repair request to LLM...")
    try:
        repair_completion = await litellm.acompletion(
            model=model,
            messages=repair_messages,
            api_key=api_key,
            api_base=api_base,
            response_format=response_format,
            timeout=DEFAULT_LLM_TIMEOUT,
        )
    except Exception as e:
        logger.error(f"Repair request failed: {e}")
        raise JSONRepairError(
            f"Failed to repair JSON response. Original error: {error}. Repair error: {e}"
        ) from e

    repaired_content = repair_completion.choices[0].message.content or "{}"

    logger.trace(
        f"<<< REPAIR RESPONSE FROM LLM ({model}) <<<"
        f"\n{'='*60}\n"
        f"{repaired_content}"
        f"\n{'='*60}"
    )

    repaired_parsed, repaired_error = _parse_json_response(repaired_content, expected_keys)
    if repaired_error is None:
        logger.info("JSON repair successful")
        return repaired_parsed

    # Repair failed
    logger.error(f"JSON repair failed: {repaired_error}")
    raise JSONRepairError(
        f"AI returned invalid JSON that could not be repaired. "
        f"Original error: {error}. Repair error: {repaired_error}. "
        f"This may indicate an issue with the model or prompt."
    )


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Send a chat completion request to the configured LLM.

    Args:
        messages: List of message dicts for the conversation.
        api_key: API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        response_format: Optional response format (e.g., {"type": "json_object"}).
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        Parsed response content as a dictionary.

    Raises:
        ModelNotAllowedError: If model is not in allowlist.
        LLMError: For API or parsing errors.
    """
    api_key = api_key or settings.effective_llm_api_key
    model = model or settings.effective_llm_model

    # Validate model is allowed
    caps = get_model_capabilities(model, allow_unsafe=settings.llm_allow_unsafe_models)
    if caps is None:
        raise ModelNotAllowedError(
            f"Model '{model}' is not in the allowlist. "
            f"Set HBC_LLM_ALLOW_UNSAFE_MODELS=true to use untested models (at your own risk)."
        )

    # Determine response format based on capabilities
    effective_response_format = response_format
    if response_format and response_format.get("type") == "json_object" and not caps.json_mode:
        # Model doesn't support json_object mode, rely on prompt-only JSON
        logger.debug(f"Model {model} doesn't support json_mode, using prompt-only JSON")
        effective_response_format = None

    return await _acompletion_with_repair(
        messages,
        model=model,
        api_key=api_key,
        api_base=settings.llm_api_base,
        response_format=effective_response_format,
        expected_keys=expected_keys,
    )


async def vision_completion(
    system_prompt: str,
    user_prompt: str,
    image_data_uris: list[str],
    *,
    api_key: str | None = None,
    model: str | None = None,
    expected_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Send a vision completion request with images to the LLM.

    Args:
        system_prompt: The system message content.
        user_prompt: The user message text content.
        image_data_uris: List of base64-encoded image data URIs.
        api_key: API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        Parsed response content as a dictionary.

    Raises:
        ModelNotAllowedError: If model is not in allowlist.
        CapabilityNotSupportedError: If model doesn't support vision.
        LLMError: For API or parsing errors.
    """
    api_key = api_key or settings.effective_llm_api_key
    model = model or settings.effective_llm_model

    # Validate model is allowed
    caps = get_model_capabilities(model, allow_unsafe=settings.llm_allow_unsafe_models)
    if caps is None:
        raise ModelNotAllowedError(
            f"Model '{model}' is not in the allowlist. "
            f"Set HBC_LLM_ALLOW_UNSAFE_MODELS=true to use untested models (at your own risk)."
        )

    # Check vision capability
    if not caps.vision:
        raise CapabilityNotSupportedError(
            f"Model '{model}' does not support vision (image inputs). "
            f"Please use a vision-capable model like gpt-5-mini."
        )

    # Check multi-image capability if needed
    if len(image_data_uris) > 1 and not caps.multi_image:
        raise CapabilityNotSupportedError(
            f"Model '{model}' does not support multiple images in a single request. "
            f"Please use a multi-image capable model or send images one at a time."
        )

    # Build content list with text and images
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]

    for data_uri in image_data_uris:
        content.append({"type": "image_url", "image_url": {"url": data_uri}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    # Determine response format based on capabilities
    response_format: dict[str, str] | None = None
    if caps.json_mode:
        response_format = {"type": "json_object"}

    return await _acompletion_with_repair(
        messages,
        model=model,
        api_key=api_key,
        api_base=settings.llm_api_base,
        response_format=response_format,
        expected_keys=expected_keys,
    )


async def cleanup_openai_clients() -> None:
    """Cleanup function for backwards compatibility.

    LiteLLM manages its own HTTP clients internally, so this is now a no-op.
    Kept for API compatibility with existing code that calls this on shutdown.
    """
    logger.debug("cleanup_openai_clients called (no-op with LiteLLM)")
