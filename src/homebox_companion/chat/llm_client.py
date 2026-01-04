"""LLM client for chat completions.

This module provides a dedicated client for LLM communication,
extracting the LiteLLM interaction logic from the orchestrator.

The LLMClient handles:
- Building the system prompt
- Calling the LLM with streaming or non-streaming modes
- Configuration from settings
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import litellm
from loguru import logger

from homebox_companion.core import config

# Guidance for system prompt - recommended max items to display in responses.
MAX_RESULT_ITEMS = 50

# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = f"""You are a Homebox inventory assistant. Help users find and manage their items.

EFFICIENCY RULES:
- Use the most appropriate tool for each query (tool definitions are provided separately)
- For listing locations/items, use the list tool ONCE - do NOT call get_* for each result
- For "find X" or "where is X" queries, use search_items
- For "items in [location]", use list_items with location filter

UPDATE OPERATIONS:
- update_item automatically fetches current item data - do NOT call get_item first
- To add a label: call update_item with label_ids containing BOTH existing label IDs AND the new one
- For bulk updates (e.g., applying a label to multiple items), call update_item in parallel
- Each item's current labels are in the list_items/get_item response - merge with new label IDs

BULK OPERATIONS:
- ALWAYS honor the user's requested quantity - if they ask for 60 items, create 60 items
- Do NOT reduce scope or stop early without explicit user permission
- Call multiple tools in PARALLEL when possible (the API handles rate limiting)
- For large operations, you CAN make all tool calls at once - they will be batched for approval
- The approval UI handles bulk operations well - users can review and approve all at once

PAGINATION:
- list_items returns {{items: [...], pagination: {{page, page_size, total, items_returned}}}}
- When items_returned < total, more items exist - call with page + 1 to get more
- To get full inventory, keep calling with incrementing page numbers until all items fetched
- Always tell the user the total count (from pagination.total) and how many you're showing

RESPONSE FORMAT:
Follow progressive disclosure: establish context first, then list details.
- Start with a summary line that establishes shared context (e.g., "Found 3 items in [Living Room](url):")
- List items beneath without repeating the contextual information already in the prelude
- Every object in tool results has a 'url' field - use it EXACTLY as provided, never modify
- Items have a nested 'location' object with its own 'url' - use the location URL in the prelude
- ALWAYS format item names as clickable markdown links using [Item Name](item.url)
- ALWAYS format location names as clickable markdown links using [Location Name](location.url)
- Example format:
  Found 2 items in [Garage](location.url):
  - [Socket Set](item.url), quantity: 1
  - [Drill](item.url), quantity: 1
- NEVER show assetId in responses unless the user explicitly asks for asset IDs
- Group results by meaningful context (location, category) when it reduces redundancy
- Show up to {MAX_RESULT_ITEMS} results, then summarize remaining count
- Be helpful and complete, not artificially brief

APPROVAL HANDLING:
- For write/destructive tools (create, update, delete), do NOT ask the user to type "yes" or confirm via text
- The UI automatically presents an approval interface for these actions
- Simply state what action will be taken and let the UI handle confirmation

No tools needed for greetings or general questions."""


@dataclass
class TokenUsage:
    """Token usage statistics from an LLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Complete (non-streaming) response from the LLM."""

    content: str
    tool_calls: list[Any] | None
    usage: TokenUsage | None


class LLMClient:
    """Client for LLM completions via LiteLLM.

    This class encapsulates all LiteLLM communication, providing:
    - Streaming and non-streaming completions
    - Tool function calling support
    - Configuration from application settings
    - Logging and timing

    Example:
        >>> llm = LLMClient()
        >>> async for chunk in llm.complete_stream(messages, tools):
        ...     print(chunk)
    """

    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for the chat assistant.

        Returns:
            The system prompt string.
        """
        return SYSTEM_PROMPT

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Make a non-streaming LLM completion request.

        Args:
            messages: Conversation messages including system prompt.
            tools: Optional tool definitions for function calling.

        Returns:
            LLMResponse with content, tool_calls, and usage.

        Raises:
            Exception: If the LLM call fails.
        """
        kwargs = self._build_request_kwargs(messages, tools, stream=False)

        start_time = time.perf_counter()
        response = await litellm.acompletion(**kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Extract response data
        assistant_message = response.choices[0].message
        content = assistant_message.content or ""
        tool_calls = getattr(assistant_message, "tool_calls", None)

        # Extract usage
        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            logger.trace(
                f"[LLM] Call completed in {elapsed_ms:.0f}ms - "
                f"tokens: prompt={usage.prompt_tokens}, "
                f"completion={usage.completion_tokens}, "
                f"total={usage.total_tokens}"
            )
        else:
            logger.trace(f"[LLM] Call completed in {elapsed_ms:.0f}ms")

        if content:
            logger.trace(f"[LLM] Response content:\n{content}")
        else:
            logger.trace("[LLM] Response content: (empty)")

        if tool_calls:
            for tc in tool_calls:
                logger.trace(f"[LLM] Tool call: {tc.function.name}({tc.function.arguments})")
        else:
            logger.trace("[LLM] No tool calls")

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Make a streaming LLM completion request.

        Args:
            messages: Conversation messages including system prompt.
            tools: Optional tool definitions for function calling.

        Yields:
            Raw LiteLLM stream chunks.

        Raises:
            Exception: If the LLM call fails.
        """
        kwargs = self._build_request_kwargs(messages, tools, stream=True)

        logger.debug(
            f"[LLM] Starting streaming completion with {len(messages)} messages, "
            f"{len(tools) if tools else 0} tools"
        )

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            yield chunk

    def _build_request_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        """Build the kwargs dict for litellm.acompletion.

        Args:
            messages: Conversation messages.
            tools: Optional tool definitions.
            stream: Whether to stream the response.

        Returns:
            Dict of kwargs for acompletion.
        """
        kwargs: dict[str, Any] = {
            "model": config.settings.effective_llm_model,
            "messages": messages,
            "api_key": config.settings.effective_llm_api_key,
            "timeout": config.settings.llm_timeout,
            "stream": stream,
        }

        if config.settings.llm_api_base:
            kwargs["api_base"] = config.settings.llm_api_base

        # Apply response length limit
        if config.settings.chat_max_response_tokens > 0:
            kwargs["max_tokens"] = config.settings.chat_max_response_tokens

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # TRACE: Log available tools
        if tools:
            tool_names = [t["function"]["name"] for t in tools]
            logger.trace(f"[LLM] Available tools: {tool_names}")

        return kwargs

