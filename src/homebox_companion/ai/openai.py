"""OpenAI API client wrapper."""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from ..core.config import settings

# Maximum number of cached OpenAI clients to prevent unbounded memory growth
_MAX_CLIENT_CACHE_SIZE = 10

# Cache for OpenAI client instances with LRU eviction
# Using OrderedDict for LRU behavior: most recently used items move to end
_client_cache: OrderedDict[str, AsyncOpenAI] = OrderedDict()

# Lock for thread/async-safe cache access
_client_cache_lock = asyncio.Lock()


async def _get_openai_client(api_key: str) -> AsyncOpenAI:
    """Get or create a cached OpenAI client for the given API key.

    This enables connection pooling and reuse across multiple requests,
    improving performance for parallel API calls. Uses LRU eviction to
    bound cache size and prevent memory leaks in multi-tenant scenarios.

    Args:
        api_key: The OpenAI API key.

    Returns:
        A cached or newly created AsyncOpenAI client.
    """
    async with _client_cache_lock:
        if api_key in _client_cache:
            # Move to end (most recently used)
            _client_cache.move_to_end(api_key)
            return _client_cache[api_key]

        # Evict oldest clients if cache is at capacity
        while len(_client_cache) >= _MAX_CLIENT_CACHE_SIZE:
            oldest_key, oldest_client = _client_cache.popitem(last=False)
            logger.debug("Evicting oldest OpenAI client from cache (size limit reached)")
            try:
                await oldest_client.close()
            except Exception as e:
                logger.warning(f"Error closing evicted OpenAI client: {e}")

        logger.debug("Creating new OpenAI client instance")
        client = AsyncOpenAI(api_key=api_key)
        _client_cache[api_key] = client
        return client


async def cleanup_openai_clients() -> None:
    """Close and cleanup all cached OpenAI client instances.

    This should be called during application shutdown to properly close
    HTTP connections and release resources.
    """
    global _client_cache
    async with _client_cache_lock:
        if _client_cache:
            logger.debug(f"Cleaning up {len(_client_cache)} OpenAI client(s)")
            for client in _client_cache.values():
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"Error closing OpenAI client: {e}")
            _client_cache.clear()


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

    client = await _get_openai_client(api_key)

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
            f"({completion.usage.prompt_tokens} input, {completion.usage.completion_tokens} output)"
        )
    else:
        logger.debug(f"OpenAI response received ({len(raw_content)} chars)")

    # Try to get parsed content, fall back to JSON parsing
    parsed_content = getattr(message, "parsed", None)
    if parsed_content is None:
        try:
            parsed_content = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw content (first 500 chars): {raw_content[:500]}")
            raise ValueError(
                f"AI returned invalid JSON response. This may indicate a model issue or "
                f"malformed prompt. Error: {e.msg} at position {e.pos}"
            ) from e
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
