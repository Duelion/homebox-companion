"""LLM API client wrapper using LiteLLM for multi-provider support.

This module provides the low-level completion functions used by the rest of the
codebase. It abstracts away the underlying LLM provider (OpenAI, Anthropic, etc.)
using LiteLLM while maintaining a consistent API.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

import litellm
from loguru import logger


@dataclass
class TokenUsage:
    """Token usage statistics from an LLM completion.

    Attributes:
        prompt_tokens: Number of tokens in the input/prompt.
        completion_tokens: Number of tokens in the output/completion.
        total_tokens: Total tokens used (prompt + completion).
        provider: The provider that was used (e.g., 'openai', 'anthropic', 'ollama').
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    provider: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "provider": self.provider,
        }


@dataclass
class CompletionResult:
    """Result from an LLM completion including both content and usage.

    Attributes:
        content: The parsed response content as a dictionary.
        usage: Token usage statistics (may have zero values if not available).
    """

    content: dict[str, Any] = field(default_factory=dict)
    usage: TokenUsage = field(default_factory=TokenUsage)

from ..core import config
from ..core.exceptions import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMServiceError,
)
from ..core.rate_limiter import acquire_rate_limit, estimate_tokens, is_rate_limiting_enabled
from .model_capabilities import get_model_capabilities

# Silence LiteLLM's verbose logging (we use loguru)
litellm.suppress_debug_info = True

# Maximum characters to include from malformed response in repair prompt
MAX_REPAIR_CONTEXT_LENGTH = 2000

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
            output_lines.append(f"\n{'=' * 60}\n[{role}]\n{'=' * 60}\n{content}")
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
            output_lines.append(f"\n{'=' * 60}\n[{role}]{image_note}\n{'=' * 60}\n{text_content}")

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
    # Smart truncation: if response is too long, try to keep the end (closing braces)
    # as well as the beginning to preserve JSON structure context
    truncated_response = original_response
    if len(original_response) > MAX_REPAIR_CONTEXT_LENGTH:
        # Keep first 70% and last 30% of the limit
        head_chars = int(MAX_REPAIR_CONTEXT_LENGTH * 0.7)
        tail_chars = MAX_REPAIR_CONTEXT_LENGTH - head_chars - 20  # Reserve space for ellipsis
        truncated_response = (
            f"{original_response[:head_chars]}\n\n... (truncated) ...\n\n"
            f"{original_response[-tail_chars:]}"
        )

    return f"""The previous response was not valid JSON. Please fix it and return ONLY valid JSON.

Error: {error_msg}

Original (malformed) response:
```
{truncated_response}
```

Expected format: {expected_schema}

Return ONLY the corrected JSON object, nothing else."""


def _strip_markdown_code_blocks(content: str) -> str:
    """Strip markdown code blocks from content.

    Some LLMs (especially Claude) wrap JSON in markdown code blocks like:
    ```json
    {"key": "value"}
    ```

    This function removes those wrappers to extract clean JSON.

    Args:
        content: Raw content that may contain markdown code blocks.

    Returns:
        Content with markdown code blocks stripped.
    """
    content = content.strip()

    # Check if content starts with markdown code block
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line (```json or ```)
        if len(lines) > 1:
            lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return content


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
    # Strip markdown code blocks if present (Claude often wraps JSON in ```json...```)
    raw_content = _strip_markdown_code_blocks(raw_content)

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


def _extract_provider_from_model(model: str) -> str:
    """Extract the provider name from a model string.

    Args:
        model: Model identifier (e.g., 'gpt-4o', 'anthropic/claude-3', 'ollama/llava').

    Returns:
        Provider name (e.g., 'openai', 'anthropic', 'ollama').
    """
    if "/" in model:
        return model.split("/")[0]
    # Default provider mappings
    if model.startswith("gpt-") or model.startswith("o1-") or model.startswith("o3-"):
        return "openai"
    if model.startswith("claude-"):
        return "anthropic"
    return "unknown"


async def _acompletion_with_repair(
    messages: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    api_base: str | None = None,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
) -> CompletionResult:
    """Call LiteLLM with optional JSON repair on failure.

    Args:
        messages: Chat messages.
        model: Model identifier.
        api_key: API key for the provider.
        api_base: Optional custom API base URL.
        response_format: Optional response format (e.g., {"type": "json_object"}).
        expected_keys: Keys to check in JSON response (triggers repair if missing).

    Returns:
        CompletionResult containing parsed JSON response and token usage.

    Raises:
        JSONRepairError: If JSON parsing fails after repair attempt.
        LLMServiceError: For other LLM-related errors.
    """
    # Build kwargs for litellm
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "api_key": api_key,
        "timeout": config.settings.llm_timeout,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if response_format:
        kwargs["response_format"] = response_format

    # First attempt
    logger.debug(f"Calling LiteLLM with model: {model}")
    logger.trace(
        f">>> PROMPT SENT TO LLM ({model}) >>>{_format_messages_for_logging(messages)}\n{'=' * 60}"
    )

    # Acquire rate limit before making API call
    if is_rate_limiting_enabled():
        estimated_tokens = estimate_tokens(messages)
        logger.debug(f"Rate limiting: estimated {estimated_tokens} tokens for this request")
        try:
            await acquire_rate_limit(estimated_tokens)
        except Exception as e:
            logger.warning(f"Rate limit wait timeout: {e}")
            raise LLMServiceError(
                "Rate limit wait timeout exceeded. The API rate limit is being hit too frequently. "
                "Consider increasing HBC_RATE_LIMIT_RPM/HBC_RATE_LIMIT_TPM, reducing batch sizes, "
                "or disabling rate limiting with HBC_RATE_LIMIT_ENABLED=false if you have higher "
                "tier limits."
            ) from e

    try:
        completion = await litellm.acompletion(**kwargs)
    except litellm.AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        raise LLMServiceError(f"Authentication failed. Check your API key. Error: {e}") from e
    except litellm.RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        raise LLMServiceError(f"Rate limit exceeded. Please try again later. Error: {e}") from e
    except litellm.APIConnectionError as e:
        logger.error(f"Connection error: {e}")
        raise LLMServiceError(f"Failed to connect to LLM API. Error: {e}") from e
    except litellm.Timeout as e:
        logger.error(f"Request timed out: {e}")
        raise LLMServiceError(
            f"LLM request timed out after {config.settings.llm_timeout}s. "
            f"The model may be overloaded. Error: {e}"
        ) from e
    except Exception as e:
        logger.exception(f"LLM call failed: {e}")
        raise LLMServiceError(f"LLM request failed: {e}") from e

    if not completion.choices:
        raise LLMServiceError("LLM returned empty response (no choices)")

    raw_content = completion.choices[0].message.content
    if raw_content is None:
        logger.warning("LLM returned None content, defaulting to empty JSON object")
        raw_content = "{}"

    logger.trace(f"<<< RESPONSE FROM LLM ({model}) <<<\n{'=' * 60}\n{raw_content}\n{'=' * 60}")

    # Capture token usage
    usage = TokenUsage(provider=_extract_provider_from_model(model))
    if completion.usage:
        usage.prompt_tokens = completion.usage.prompt_tokens or 0
        usage.completion_tokens = completion.usage.completion_tokens or 0
        usage.total_tokens = completion.usage.total_tokens or 0
        logger.debug(
            f"LLM response received ({len(raw_content)} chars) | "
            f"Tokens: {usage.total_tokens} total "
            f"({usage.prompt_tokens} input, {usage.completion_tokens} output)"
        )
    else:
        logger.debug(f"LLM response received ({len(raw_content)} chars)")

    # Parse and validate
    parsed, error = _parse_json_response(raw_content, expected_keys)
    if error is None:
        return CompletionResult(content=parsed, usage=usage)

    # Repair attempt (one retry only)
    logger.warning(f"JSON validation failed, attempting repair: {error}")

    expected_schema = "JSON object"
    if expected_keys:
        expected_schema = f"JSON object with keys: {expected_keys}"

    repair_prompt = _build_repair_prompt(raw_content, error, expected_schema)
    # Deep copy to prevent modifications to vision messages with nested structures
    repair_messages = copy.deepcopy(messages)
    repair_messages.append({"role": "assistant", "content": raw_content})
    repair_messages.append({"role": "user", "content": repair_prompt})

    logger.debug("Sending repair request to LLM...")

    # Apply rate limiting to repair request as well
    if is_rate_limiting_enabled():
        estimated_tokens = estimate_tokens(repair_messages)
        logger.debug(f"Rate limiting repair request: estimated {estimated_tokens} tokens")
        try:
            await acquire_rate_limit(estimated_tokens)
        except Exception as e:
            logger.warning(f"Rate limit wait timeout on repair request: {e}")
            raise LLMServiceError(
                "Rate limit wait timeout exceeded during JSON repair. "
                "Consider increasing HBC_RATE_LIMIT_RPM/HBC_RATE_LIMIT_TPM, reducing batch sizes, "
                "or disabling rate limiting with HBC_RATE_LIMIT_ENABLED=false."
            ) from e

    try:
        repair_completion = await litellm.acompletion(
            model=model,
            messages=repair_messages,
            api_key=api_key,
            api_base=api_base,
            response_format=response_format,
            timeout=config.settings.llm_timeout,
        )
    except Exception as e:
        logger.error(f"Repair request failed: {e}")
        raise JSONRepairError(
            f"Failed to repair JSON response. Original error: {error}. Repair error: {e}"
        ) from e

    if not repair_completion.choices:
        raise JSONRepairError("LLM returned empty response during repair attempt")

    repaired_content = repair_completion.choices[0].message.content
    if repaired_content is None:
        logger.warning("LLM returned None content during repair, defaulting to empty JSON object")
        repaired_content = "{}"

    logger.trace(
        f"<<< REPAIR RESPONSE FROM LLM ({model}) <<<\n{'=' * 60}\n{repaired_content}\n{'=' * 60}"
    )

    # Accumulate usage from repair call
    if repair_completion.usage:
        usage.prompt_tokens += repair_completion.usage.prompt_tokens or 0
        usage.completion_tokens += repair_completion.usage.completion_tokens or 0
        usage.total_tokens += repair_completion.usage.total_tokens or 0

    repaired_parsed, repaired_error = _parse_json_response(repaired_content, expected_keys)
    if repaired_error is None:
        logger.info("JSON repair successful")
        return CompletionResult(content=repaired_parsed, usage=usage)

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
    api_base: str | None = None,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
) -> CompletionResult:
    """Send a chat completion request to the configured LLM.

    Args:
        messages: List of message dicts for the conversation.
        api_key: API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
            If not provided, falls back to config.settings.llm_api_base.
        response_format: Optional response format (e.g., {"type": "json_object"}).
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        CompletionResult containing parsed response and token usage.

    Raises:
        LLMServiceError: For API or parsing errors.
    """
    api_key = api_key or config.settings.effective_llm_api_key
    model = model or config.settings.effective_llm_model
    # Use passed api_base if provided, otherwise fall back to global config
    effective_api_base = api_base if api_base is not None else config.settings.llm_api_base

    # Determine response format based on capabilities (if validation enabled)
    effective_response_format = response_format
    if not config.settings.llm_allow_unsafe_models:
        caps = get_model_capabilities(model)
        if response_format and response_format.get("type") == "json_object" and not caps.json_mode:
            logger.debug(f"Model {model} doesn't support json_mode, using prompt-only JSON")
            effective_response_format = None

    return await _acompletion_with_repair(
        messages,
        model=model,
        api_key=api_key,
        api_base=effective_api_base,
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
    api_base: str | None = None,
    expected_keys: list[str] | None = None,
) -> CompletionResult:
    """Send a vision completion request with images to the LLM.

    Args:
        system_prompt: The system message content.
        user_prompt: The user message text content.
        image_data_uris: List of base64-encoded image data URIs.
        api_key: API key. Defaults to effective_llm_api_key.
        model: Model name. Defaults to effective_llm_model.
        api_base: Optional custom API base URL (e.g., Ollama server URL).
            If not provided, falls back to config.settings.llm_api_base.
        expected_keys: Optional keys to validate in JSON response.

    Returns:
        CompletionResult containing parsed response and token usage.

    Raises:
        ValueError: If image_data_uris is empty.
        CapabilityNotSupportedError: If model doesn't support vision.
        LLMServiceError: For API or parsing errors.
    """
    if not image_data_uris:
        raise ValueError("vision_completion requires at least one image")

    api_key = api_key or config.settings.effective_llm_api_key
    model = model or config.settings.effective_llm_model
    # Use passed api_base if provided, otherwise fall back to global config
    effective_api_base = api_base if api_base is not None else config.settings.llm_api_base

    # Determine capabilities and response format
    response_format: dict[str, str] | None = None

    if config.settings.llm_allow_unsafe_models:
        # Without validation, try json_mode by default and let LiteLLM handle it
        response_format = {"type": "json_object"}
        logger.debug(
            f"Skipping capability validation for model '{model}' (HBC_LLM_ALLOW_UNSAFE_MODELS=true)"
        )
    else:
        # Validate model capabilities
        caps = get_model_capabilities(model)

        logger.debug(
            f"Model '{model}' capabilities for vision request: "
            f"vision={caps.vision}, json_mode={caps.json_mode}, multi_image={caps.multi_image}"
        )

        if not caps.vision:
            raise CapabilityNotSupportedError(
                f"Model '{model}' does not support vision (image inputs).\n\n"
                f"Homebox Companion requires a vision-capable model to analyze item photos. "
                f"LiteLLM reports that '{model}' does not have vision capabilities.\n\n"
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
                f"Model '{model}' does not support multiple images in a "
                f"single request.\n\n"
                f"You're trying to analyze {len(image_data_uris)} images at once, "
                f"but LiteLLM reports "
                f"that '{model}' only supports single-image inputs.\n\n"
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
            logger.debug(f"Model {model} doesn't support json_mode, using prompt-only JSON")

    # Build content list with text and images
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]

    for data_uri in image_data_uris:
        content.append({"type": "image_url", "image_url": {"url": data_uri}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    return await _acompletion_with_repair(
        messages,
        model=model,
        api_key=api_key,
        api_base=effective_api_base,
        response_format=response_format,
        expected_keys=expected_keys,
    )

