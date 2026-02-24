"""JSON completion with automatic repair for malformed responses.

This module provides JSON-focused LLM completions that:
- Parse and validate JSON responses
- Strip markdown code blocks (common with Claude)
- Attempt repair when JSON is malformed
- Route through the LiteLLM Router for provider fallback

The repair mechanism asks the same model to fix its own output,
preserving context. Provider-level failures are handled by the Router.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from loguru import logger

from ..core import config
from ..core.exceptions import JSONRepairError, LLMServiceError
from ..core.llm_router import get_primary_model_name, get_router
from ..core.rate_limiter import acquire_rate_limit, estimate_tokens, is_rate_limiting_enabled

# Maximum characters to include from malformed response in repair prompt
MAX_REPAIR_CONTEXT_LENGTH = 2000


async def _acquire_rate_limit_if_enabled(messages: list[dict[str, Any]], context: str = "") -> None:
    """Acquire rate limit if enabled, with logging.

    Args:
        messages: Messages to estimate tokens for.
        context: Optional context string for log messages (e.g., "repair").

    Raises:
        LLMServiceError: If rate limit wait times out.
    """
    if not is_rate_limiting_enabled():
        return

    estimated_tokens = estimate_tokens(messages)
    context_str = f" {context}" if context else ""
    logger.debug(f"Rate limiting{context_str}: estimated {estimated_tokens} tokens")

    try:
        await acquire_rate_limit(estimated_tokens)
    except Exception as e:
        logger.warning(f"Rate limit wait timeout{context_str}: {e}")
        raise LLMServiceError(
            f"Rate limit wait timeout exceeded{context_str}. Consider increasing rate limits "
            "or disabling with HBC_RATE_LIMIT_ENABLED=false."
        ) from e


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
    # Smart truncation: if response is too long, keep beginning and end
    truncated_response = original_response
    if len(original_response) > MAX_REPAIR_CONTEXT_LENGTH:
        head_chars = int(MAX_REPAIR_CONTEXT_LENGTH * 0.7)
        tail_chars = MAX_REPAIR_CONTEXT_LENGTH - head_chars - 20
        truncated_response = (
            f"{original_response[:head_chars]}\n\n... (truncated) ...\n\n{original_response[-tail_chars:]}"
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

    if content.startswith("```"):
        lines = content.split("\n")
        if len(lines) > 1:
            lines = lines[1:]
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


def _build_completion_kwargs(
    messages: list[dict[str, Any]],
    model_name: str,
    timeout: float,
    response_format: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build kwargs for Router.acompletion calls.

    Args:
        messages: Chat messages for the completion.
        model_name: Router model name to use.
        timeout: Request timeout in seconds.
        response_format: Optional format hint (e.g., {"type": "json_object"}).

    Returns:
        Dict of kwargs for acompletion.
    """
    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "timeout": timeout,
    }
    if response_format:
        kwargs["response_format"] = response_format
    return kwargs


async def json_completion(
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    expected_keys: list[str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Make an LLM completion request expecting JSON output.

    Uses the Router for provider-level fallback and handles JSON
    parsing/repair at the application level.

    Args:
        messages: Chat messages for the completion.
        response_format: Optional format hint (e.g., {"type": "json_object"}).
        expected_keys: Keys to check in JSON response (triggers repair if missing).
        timeout: Optional timeout override (uses config default if None).

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        JSONRepairError: If JSON parsing fails after repair attempt.
        LLMServiceError: For rate limit or other LLM-related errors.
    """
    router = get_router()
    model_name = get_primary_model_name()
    effective_timeout = timeout or config.settings.llm_timeout

    # Build kwargs for Router call
    kwargs = _build_completion_kwargs(messages, model_name, effective_timeout, response_format)

    # Rate limiting
    await _acquire_rate_limit_if_enabled(messages)

    logger.debug(f"Calling Router with model_name: {model_name}")
    logger.trace(f">>> PROMPT SENT TO LLM ({model_name}) >>>{_format_messages_for_logging(messages)}\n{'=' * 60}")

    # First attempt via Router
    try:
        completion = await router.acompletion(**kwargs)
    except Exception as e:
        logger.exception(f"Router call failed: {e}")
        raise LLMServiceError(f"LLM request failed: {e}") from e

    if not completion.choices:
        raise LLMServiceError("LLM returned empty response (no choices)")

    raw_content = completion.choices[0].message.content
    if raw_content is None:
        logger.warning("LLM returned None content, defaulting to empty JSON object")
        raw_content = "{}"

    # Get actual model used (for logging)
    actual_model = getattr(completion, "_hidden_params", {}).get("model", model_name)
    logger.trace(f"<<< RESPONSE FROM LLM ({actual_model}) <<<\n{'=' * 60}\n{raw_content}\n{'=' * 60}")

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

    # Repair attempt
    logger.warning(f"JSON validation failed, attempting repair: {error}")

    expected_schema = "JSON object"
    if expected_keys:
        expected_schema = f"JSON object with keys: {expected_keys}"

    repair_prompt = _build_repair_prompt(raw_content, error, expected_schema)
    repair_messages = copy.deepcopy(messages)
    repair_messages.append({"role": "assistant", "content": raw_content})
    repair_messages.append({"role": "user", "content": repair_prompt})

    # Rate limiting for repair
    await _acquire_rate_limit_if_enabled(repair_messages, context="for repair")

    logger.debug("Sending repair request to Router...")

    try:
        repair_kwargs = _build_completion_kwargs(repair_messages, model_name, effective_timeout, response_format)
        repair_completion = await router.acompletion(**repair_kwargs)
    except Exception as e:
        logger.error(f"Repair request failed: {e}")
        raise JSONRepairError(f"Failed to repair JSON response. Original error: {error}. Repair error: {e}") from e

    if not repair_completion.choices:
        raise JSONRepairError("LLM returned empty response during repair attempt")

    repaired_content = repair_completion.choices[0].message.content
    if repaired_content is None:
        logger.warning("LLM returned None content during repair, defaulting to empty JSON object")
        repaired_content = "{}"

    logger.trace(f"<<< REPAIR RESPONSE FROM LLM <<<\n{'=' * 60}\n{repaired_content}\n{'=' * 60}")

    repaired_parsed, repaired_error = _parse_json_response(repaired_content, expected_keys)
    if repaired_error is None:
        logger.info("JSON repair successful")
        return repaired_parsed

    # Repair failed
    logger.error(f"JSON repair failed: {repaired_error}")
    raise JSONRepairError(
        f"AI returned invalid JSON that could not be repaired. Original error: {error}. Repair error: {repaired_error}."
    )
