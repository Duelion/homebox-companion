"""OpenAI API client wrapper."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from ..core.config import settings

# Cache for OpenAI client instances to enable connection reuse
_client_cache: dict[str, AsyncOpenAI] = {}


def _get_openai_client(api_key: str) -> AsyncOpenAI:
    """Get or create a cached OpenAI client for the given API key.

    This enables connection pooling and reuse across multiple requests,
    improving performance for parallel API calls.

    Args:
        api_key: The OpenAI API key.

    Returns:
        A cached or newly created AsyncOpenAI client.
    """
    if api_key not in _client_cache:
        logger.debug("Creating new OpenAI client instance")
        _client_cache[api_key] = AsyncOpenAI(api_key=api_key)
    return _client_cache[api_key]


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


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    response_format: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a chat completion request to OpenAI.

    Args:
        messages: List of message dicts for the conversation.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        response_format: Optional response format (e.g., {"type": "json_object"}).

    Returns:
        Parsed response content as a dictionary.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model

    logger.debug(f"Calling OpenAI API with model: {model}")

    # TRACE level: Log full prompt being sent to LLM
    logger.trace(
        f">>> PROMPT SENT TO LLM ({model}) >>>"
        f"{_format_messages_for_logging(messages)}"
        f"\n{'='*60}"
    )

    client = _get_openai_client(api_key)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if response_format:
        kwargs["response_format"] = response_format

    completion = await client.chat.completions.create(**kwargs)

    message = completion.choices[0].message
    raw_content = message.content or "{}"

    # TRACE level: Log full response from LLM
    logger.trace(
        f"<<< RESPONSE FROM LLM ({model}) <<<"
        f"\n{'='*60}\n"
        f"{raw_content}"
        f"\n{'='*60}"
    )

    # Log token usage for cost monitoring
    if completion.usage:
        logger.debug(
            f"OpenAI response received ({len(raw_content)} chars) | "
            f"Tokens: {completion.usage.total_tokens} total "
            f"({completion.usage.input_tokens} input, {completion.usage.output_tokens} output)"
        )
    else:
        logger.debug(f"OpenAI response received ({len(raw_content)} chars)")

    # Try to get parsed content, fall back to JSON parsing
    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    return parsed_content


async def vision_completion(
    system_prompt: str,
    user_prompt: str,
    image_data_uris: list[str],
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Send a vision completion request with images to OpenAI.

    Args:
        system_prompt: The system message content.
        user_prompt: The user message text content.
        image_data_uris: List of base64-encoded image data URIs.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.

    Returns:
        Parsed response content as a dictionary.
    """
    # Build content list with text and images
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]

    for data_uri in image_data_uris:
        content.append({"type": "image_url", "image_url": {"url": data_uri}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    return await chat_completion(
        messages,
        api_key=api_key,
        model=model,
        response_format={"type": "json_object"},
    )
