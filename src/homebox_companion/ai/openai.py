"""OpenAI API client wrapper."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from ..core.config import settings


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

    client = AsyncOpenAI(api_key=api_key)

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

