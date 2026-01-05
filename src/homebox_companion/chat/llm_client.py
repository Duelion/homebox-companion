"""LLM client for chat completions.

This module provides a dedicated client for LLM communication,
extracting the LiteLLM interaction logic from the orchestrator.

The LLMClient handles:
- Building the system prompt
- Calling the LLM with streaming or non-streaming modes
- Configuration from settings
- Capturing raw request/response data for debugging
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import litellm
from loguru import logger

from homebox_companion.core import config

# Enable raw request/response logging in LiteLLM
litellm.log_raw_request_response = True

# Buffer for storing raw LLM interactions captured by the callback
# This is a module-level list that the ChatSession can consume
_llm_raw_log: list[dict[str, Any]] = []
_LLM_RAW_LOG_MAX_SIZE = 50


def _litellm_success_callback(kwargs: dict, completion_response: Any, start_time: float, end_time: float) -> None:
    """LiteLLM success callback that captures the exact request/response.

    This callback is invoked by LiteLLM after every successful API call,
    giving us access to exactly what was sent to and received from the LLM.

    Args:
        kwargs: The exact kwargs passed to litellm.acompletion
        completion_response: The raw response from the LLM
        start_time: Unix timestamp when request started
        end_time: Unix timestamp when request completed
    """
    global _llm_raw_log

    try:
        # Extract the key data - this is EXACTLY what LiteLLM sent/received
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "latency_ms": int((end_time - start_time) * 1000),
            "model": kwargs.get("model"),
            "request": {
                "messages": kwargs.get("messages"),
                "tools": kwargs.get("tools"),
                "tool_choice": kwargs.get("tool_choice"),
                "max_tokens": kwargs.get("max_tokens"),
                "stream": kwargs.get("stream"),
            },
            "response": {
                "id": getattr(completion_response, "id", None),
                "model": getattr(completion_response, "model", None),
                "choices": [],
                "usage": None,
            },
        }

        # Extract choices
        if hasattr(completion_response, "choices"):
            for choice in completion_response.choices:
                choice_data: dict[str, Any] = {
                    "index": getattr(choice, "index", 0),
                    "finish_reason": getattr(choice, "finish_reason", None),
                }
                if hasattr(choice, "message"):
                    msg = choice.message
                    choice_data["message"] = {
                        "role": getattr(msg, "role", None),
                        "content": getattr(msg, "content", None),
                        "tool_calls": None,
                    }
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        choice_data["message"]["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ]
                entry["response"]["choices"].append(choice_data)

        # Extract usage
        if hasattr(completion_response, "usage") and completion_response.usage:
            entry["response"]["usage"] = {
                "prompt_tokens": completion_response.usage.prompt_tokens,
                "completion_tokens": completion_response.usage.completion_tokens,
                "total_tokens": completion_response.usage.total_tokens,
            }

        _llm_raw_log.append(entry)

        # Trim to max size
        if len(_llm_raw_log) > _LLM_RAW_LOG_MAX_SIZE:
            _llm_raw_log = _llm_raw_log[-_LLM_RAW_LOG_MAX_SIZE:]

        logger.trace(f"[LLM_CALLBACK] Logged raw interaction, total: {len(_llm_raw_log)}")

    except Exception as e:
        logger.warning(f"[LLM_CALLBACK] Failed to log interaction: {e}")


def get_raw_llm_log() -> list[dict[str, Any]]:
    """Get the raw LLM interaction log.

    Returns a copy to prevent external modification.
    """
    return list(_llm_raw_log)


def clear_raw_llm_log() -> None:
    """Clear the raw LLM log buffer."""
    global _llm_raw_log
    _llm_raw_log = []


# Register the callback with LiteLLM
litellm.success_callback = [_litellm_success_callback]

# Soft recommendation for max items in responses - used when user doesn't specify a count.
# When user explicitly requests a specific number (e.g., "show me 80 items"), honor that request.
DEFAULT_RESULT_LIMIT = 25

# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = f"""
You are a Homebox inventory assistant. Help the user find items, understand where they are, and keep the inventory accurate with minimal effort.

Priorities
1) Inventory-first: assume questions are about the user's inventory. For "what should I use / do I have / which is best", search inventory before giving general advice.
2) Correctness: never invent items, locations, quantities, or attributes that are not in tool data.
3) Low friction: make safe assumptions for read-only tasks; minimize back-and-forth.
4) Efficiency: use the fewest tool calls that still answer completely.
5) Data safety: preserve existing data; only change what the user asked to change.
6) Scannable output: concise lists, working links, minimal repetition.

Intent and ambiguity
- Infer intent early: find/where, list-in-location, browse/list, update/add/remove, bulk cleanup.
- If ambiguous:
  - Read-only: choose the most likely interpretation and state the assumption briefly.
  - Write/destructive: only ask one clarifying question when guessing could cause meaningful harm; otherwise propose changes and issue the write calls so the UI can approve them.

Tooling norms (tools defined elsewhere)
- Prefer set-based reads (search/list) over per-item lookups.
- "Find X / where is X" -> search_items first.
- "Items in [location]" -> list_items with a location filter.
- update_item fetches current state internally; do not call get_item just to update.
- Labels are additive by default; replace labels only when the user explicitly asks. When adding labels, include existing label IDs plus new ones.

Batching and caching
- Treat tool results as current within the same turn; reuse them instead of refetching.
- Refetch only after a state change (for example, the user approved writes) or when the user asks for updated results.
- For bulk edits, issue updates in parallel; it is fine to create many action badges at once.

Pagination
- If the user requests N results, use page_size = N in one call.
- If the user asks for "all", paginate until you reach pagination.total (or no more results).
- When showing a subset, mention total and how many are displayed.

Iterative review (batch workflows)
- Phrases like "N by N", "batch by batch", or "review in chunks" mean: process ONE batch per conversation turn.
- Workflow per batch: (1) fetch items, (2) analyze them, (3) explain proposed changes with reasoning, (4) issue write tool calls (e.g., update_item) in the same message.
- Write tools return "awaiting_approval" which means approval badges now appear for the user.
- After issuing write calls for a batch, STOP. Do not fetch the next batch until the user says to continue.
- Do NOT fetch all pages at once; this overwhelms the context and wastes tokens.

Search behavior
- Prefer direct matches.
- If nothing matches, automatically try 2-3 variants (singular/plural, synonyms, remove adjectives), then filter back down to plausible relevance.
- "Possible matches" must be labeled as such; do not claim inferred material or compatibility as fact.

Response style (default)
- Lead with the best match.
- Use markdown links exactly as provided: items as [Name](item.url), locations as [Name](location.url).
- Keep lists minimal (usually one item per line).
- Show location only when it answers the question (for example, "where is X") or clearly reduces confusion.
- Show quantity only when asked or when it materially affects the decision.

Approval handling (writes)
- Do not ask for textual confirmation to perform writes.
- If you are proposing any change, include the write tool calls in the same message so the UI can show approval badges.
- "awaiting_approval" is expected for write tools and means the badge was created successfully.

Only skip inventory lookup for pure greetings.
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

