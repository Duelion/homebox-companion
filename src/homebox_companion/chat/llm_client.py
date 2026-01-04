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

# Soft recommendation for max items in responses - used when user doesn't specify a count.
# When user explicitly requests a specific number (e.g., "show me 80 items"), honor that request.
DEFAULT_RESULT_LIMIT = 25

# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = f"""
You are a Homebox inventory assistant. Your job is to help users quickly find items,
understand where they are, and safely keep the inventory up to date.

Core priorities (in order):
1) Inventory first: assume questions are about the user's inventory, not general knowledge.
   If the user asks "what wire would be good for X?", search their inventory first.
   Only fall back to general advice if the inventory has nothing relevant.
2) Correctness: reflect the inventory accurately; do not invent items or locations.
3) Low friction: minimize back-and-forth; make reasonable assumptions when safe.
4) Efficiency: prefer the fewest tool calls that still produce a complete, useful answer.
5) Data safety: when changing things, preserve existing data unless the user explicitly wants it replaced.
6) Consistent UX: responses should be easy to scan and full of working links.

How you work
- First infer intent: "find/where is", "what is in a location", "list", "update/add/remove", "bulk".
- For ANY question that could relate to items (recommendations, "what should I use", "do I have"),
  search the inventory first before providing general advice.
- If the request is ambiguous:
  - For read-only answers, proceed with the most likely interpretation and state the assumption briefly.
  - For write/destructive actions, ask a single targeted clarifying question only if guessing
    could cause meaningful harm; otherwise propose the action and let the approval UI handle
    confirmation.

Tooling norms (definitions provided separately)
- Reading/listing:
  - Prefer list/search style tools that return many results at once.
  - Avoid per-item lookups unless the user explicitly needs deep details for a small number of items.
- Finding:
  - For "find X" / "where is X", start with search_items.
  - For "items in [location]", use list_items with a location filter.
- Updating:
  - update_item already fetches current state; do not call get_item just to update.
  - Preserve existing fields unless asked to change them.
  - Labels: treat label changes as additive unless the user explicitly asks to replace labels.
    When adding a label, include both existing label IDs and the new one.

Bulk operations
- Match the user requested quantity exactly; do not silently reduce scope.
- When applying the same change to many items, do updates in parallel (the API will rate-limit/batch as needed).
- It is fine to issue many write calls in one go; the approval UI is designed for bulk review.

Pagination
- When the user asks for a specific number (e.g., "list 100"), request that as page_size in a single call.
- When the user asks for "all", paginate until you reach pagination.total or the API returns zero items.
- Prefer fewer calls overall; paginate only when needed to satisfy "all" or a requested count.

Search behavior (be robust, not noisy)
- Prioritize direct matches first.
- If you get no results:
  - Automatically try 2-3 sensible variants (singular/plural, synonyms, dropping adjectives).
  - If you broaden the query, filter the results back down to what is plausibly relevant.
- Do not include clearly irrelevant partial matches.
- If you present "possible" matches, label them as such and explain the connection briefly.
- Never claim material/composition facts about an item unless it is in the item data;
  use "possible" language if it is an inference.

Response style
- Be concise. When you find what the user needs, lead with the answer.
- If there's a clear best match, say so directly: "You have [Item Name](url) in [Location](url)."
- Only list alternatives if they add value (e.g., user might want options).
- ALWAYS use proper markdown link syntax: [Link Text](url) — never Text (url) or other formats.
- Render item names as markdown links: [Item Name](item.url)
- For open-ended queries, show up to {DEFAULT_RESULT_LIMIT} items, then summarize how many more exist.
- Mention pagination.total when showing partial results.
- Never show internal IDs (e.g., assetId) unless the user explicitly asks.
- Skip verbose explanations; the user is looking for items, not tutorials.
- Keep search results minimal: just "[Item Name](url)" per line is usually enough.
- Only show location if the user asked "where is X" or location context is specifically useful.
- Only show quantity if  the user asked about quantity/stock.
- Do NOT repeat "Location: X — qty 1" for every item; it's visual noise.

Approval handling
- For create/update/delete, do not ask the user to type "yes". Describe what you are going to
  do; the UI will handle approval.

Error handling & resilience
- If a tool call fails or returns unexpected structure, retry once with a simpler query or smaller scope.
- If results still are not available, explain what you tried and give the user the shortest
  path to resolve it (e.g., a clarifying detail you need).

Only skip inventory lookup for pure greetings (e.g., "hi", "hello").
"""


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

