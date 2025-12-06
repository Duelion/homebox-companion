"""OpenAI API client wrapper."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI, omit

from ..core.config import settings

# Sentinel value for distinguishing "not provided" from "explicitly None"
_UNSET = object()

# Cache for OpenAI client instances to enable connection reuse
_client_cache: dict[str, AsyncOpenAI] = {}

# Default headers to strip SDK telemetry that some proxies/WAFs block
_DEFAULT_HEADERS = {
    "X-Stainless-Lang": omit,
    "X-Stainless-Package-Version": omit,
    "X-Stainless-OS": omit,
    "X-Stainless-Arch": omit,
    "X-Stainless-Runtime": omit,
    "X-Stainless-Runtime-Version": omit,
    "x-stainless-async": omit,
    "x-stainless-retry-count": omit,
    "x-stainless-read-timeout": omit,
    # keep UA simple to avoid proxy blocks
    "User-Agent": "homebox-companion",
}


def _get_openai_client(api_key: str, base_url: str | None = None) -> AsyncOpenAI:
    """Get or create a cached OpenAI client for the given API key and base URL.

    This enables connection pooling and reuse across multiple requests,
    improving performance for parallel API calls.

    Args:
        api_key: The OpenAI API key.
        base_url: Optional custom base URL for OpenAI-compatible endpoints.

    Returns:
        A cached or newly created AsyncOpenAI client.
    """
    # Create cache key from both api_key and base_url
    cache_key = f"{api_key}:{base_url or 'default'}"

    if cache_key not in _client_cache:
        logger.debug(f"Creating new OpenAI client instance (base_url: {base_url or 'default'})")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        kwargs["default_headers"] = _DEFAULT_HEADERS
        _client_cache[cache_key] = AsyncOpenAI(**kwargs)
    return _client_cache[cache_key]


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None | object = _UNSET,
    response_format: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a chat completion request to OpenAI.

    Args:
        messages: List of message dicts for the conversation.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        base_url: Custom base URL for OpenAI-compatible endpoints.
            - If not provided (default), uses HBC_OPENAI_BASE_URL from settings
            - If None, explicitly uses the official OpenAI API endpoint
            - If a string URL, uses that custom endpoint
        response_format: Optional response format (e.g., {"type": "json_object"}).

    Returns:
        Parsed response content as a dictionary.

    Note:
        The base_url parameter uses a sentinel value internally to distinguish
        between "not provided" and "explicitly None". For typical usage, just
        omit the parameter to use settings, or pass a string URL for a custom
        endpoint.
    """
    api_key = api_key or settings.openai_api_key
    model = model or settings.openai_model
    # Use sentinel to distinguish "not provided" from "explicitly None"
    if base_url is _UNSET:
        base_url = settings.openai_base_url
    # else: use the provided value (including None)

    logger.debug(f"Calling OpenAI API with model: {model}, base_url: {base_url or 'default'}")

    client = _get_openai_client(api_key, base_url)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if response_format:
        kwargs["response_format"] = response_format

    completion = await client.chat.completions.create(**kwargs)

    message = completion.choices[0].message
    raw_content = message.content or "{}"
    logger.debug(f"OpenAI response: {raw_content[:500]}...")

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
    base_url: str | None | object = _UNSET,
) -> dict[str, Any]:
    """Send a vision completion request with images to OpenAI.

    Args:
        system_prompt: The system message content.
        user_prompt: The user message text content.
        image_data_uris: List of base64-encoded image data URIs.
        api_key: OpenAI API key. Defaults to HBC_OPENAI_API_KEY.
        model: Model name. Defaults to HBC_OPENAI_MODEL.
        base_url: Custom base URL for OpenAI-compatible endpoints.
            - If not provided (default), uses HBC_OPENAI_BASE_URL from settings
            - If None, explicitly uses the official OpenAI API endpoint
            - If a string URL, uses that custom endpoint

    Returns:
        Parsed response content as a dictionary.

    Note:
        The base_url parameter uses a sentinel value internally to distinguish
        between "not provided" and "explicitly None". For typical usage, just
        omit the parameter to use settings, or pass a string URL for a custom
        endpoint.
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
        base_url=base_url,
        response_format={"type": "json_object"},
    )



