"""LLM client for chat completions.

This module provides a dedicated client for LLM communication,
extracting the LiteLLM interaction logic from the orchestrator.

The LLMClient handles:
- Building the system prompt
- Calling the LLM with streaming or non-streaming modes
- Configuration from settings
- Capturing raw request/response data for debugging via loguru
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import litellm
from loguru import logger

from homebox_companion.core import config
from homebox_companion.core.logging import get_log_level_value


def _build_log_entry(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_content: str,
    response_tool_calls: list[dict[str, Any]] | None,
    latency_ms: int,
) -> dict[str, Any]:
    """Build a log entry with detail level based on configured log level.

    Detail levels:
    - TRACE: Full detail (all messages, complete tool schemas, full response)
    - DEBUG: Moderate detail (all messages, tool names only, full response)
    - INFO+: Minimal (timestamp, model, latency, counts/summaries)

    Returns:
        Dict containing the log entry with appropriate detail level.
    """
    level_value = get_log_level_value()
    model = config.settings.effective_llm_model
    timestamp = datetime.now(UTC).isoformat()

    # Base entry (always included)
    entry: dict[str, Any] = {
        "timestamp": timestamp,
        "latency_ms": latency_ms,
        "model": model,
    }

    if level_value <= logger.level("TRACE").no:
        # TRACE: Full detail
        entry["request"] = {
            "messages": messages,
            "tools": tools,
        }
        entry["response"] = {
            "content": response_content,
            "tool_calls": response_tool_calls,
        }
    elif level_value <= logger.level("DEBUG").no:
        # DEBUG: Moderate detail - tool names only, no full schemas
        entry["request"] = {
            "messages": messages,
            "tool_names": [t["function"]["name"] for t in tools] if tools else None,
        }
        entry["response"] = {
            "content": response_content,
            "tool_calls": response_tool_calls,
        }
    else:
        # INFO+: Minimal - just summaries
        entry["request"] = {
            "message_count": len(messages),
            "tool_count": len(tools) if tools else 0,
            "tool_names": [t["function"]["name"] for t in tools] if tools else None,
        }
        entry["response"] = {
            "content_length": len(response_content),
            "tool_call_count": len(response_tool_calls) if response_tool_calls else 0,
            "tool_calls_summary": ([tc.get("name") for tc in response_tool_calls] if response_tool_calls else None),
        }

    return entry


def log_streaming_interaction(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_content: str,
    response_tool_calls: list[dict[str, Any]] | None,
    latency_ms: int,
) -> None:
    """Log a streaming LLM interaction to the debug log file.

    Called by the orchestrator after streaming completes to capture
    the exact messages sent to the LLM and the reconstructed response.

    The detail level varies based on the configured log level:
    - TRACE: Full messages, full tool schemas, full response
    - DEBUG: Full messages, tool names only, full response
    - INFO+: Counts and summaries only

    Args:
        messages: The exact messages sent to the LLM.
        tools: The tool definitions sent to the LLM.
        response_content: The accumulated response content.
        response_tool_calls: The parsed tool calls from the response.
        latency_ms: Time taken for the streaming request in milliseconds.
    """
    try:
        entry = _build_log_entry(messages, tools, response_content, response_tool_calls, latency_ms)

        # Log with llm_debug=True so it's captured by the dedicated handler
        logger.bind(llm_debug=True).info(json.dumps(entry))
        logger.trace("[LLM_LOG] Logged streaming interaction")

    except Exception as e:
        logger.warning(f"[LLM_LOG] Failed to log streaming interaction: {e}")


# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = """
You are a Homebox inventory assistant. Help the user find items, understand where they are,
and keep the inventory accurate with minimal effort.

Priorities
1) Inventory-first: assume questions are about the user's inventory.
   For "what should I use / do I have / which is best", search inventory before giving general advice.
2) Correctness: never invent items, locations, quantities, or attributes that are not in tool data.
3) Low friction: make safe assumptions for read-only tasks; minimize back-and-forth.
4) Efficiency: use the fewest tool calls that still answer completely.
5) Data safety: preserve existing data; only change what the user asked to change.
6) Scannable output: concise lists, working links, minimal repetition.

Intent and ambiguity
- Infer intent early: find/where, list-in-location, browse/list, update/add/remove, bulk cleanup.
- If ambiguous:
  - Read-only: choose the most likely interpretation and state the assumption briefly.
  - Write/destructive: only ask one clarifying question when guessing could cause meaningful harm;
    otherwise propose changes and issue the write calls so the UI can approve them.

Tooling norms (tools defined elsewhere)
- Prefer set-based reads (search/list) over per-item lookups.
- "Find X / where is X" -> search_items first.
- "Items in [location]" -> list_items with a location filter.
- update_item fetches current state internally; do not call get_item just to update.
- Labels are additive by default; replace labels only when the user explicitly asks.
  When adding labels, include existing label IDs plus new ones.

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
- Workflow per batch: (1) fetch items, (2) analyze them, (3) explain proposed changes with reasoning,
  (4) issue write tool calls (e.g., update_item) in the same message.
- Write tools return "awaiting_approval" which means approval badges now appear for the user.
- After issuing write calls for a batch, STOP. Do not fetch the next batch until the user says to continue.
- Do NOT fetch all pages at once; this overwhelms the context and wastes tokens.

Scope discipline
- Stay within the original scope the user defined.
  Do not expand to new categories or item types unless the user explicitly asks.
- "Continue" means continue within the CURRENT scope (e.g., remaining Samla boxes),
  not expand to unrelated items (e.g., all locations).
- If the current scope is exhausted and there are related items you could process,
  ask briefly: "Done with [X]. Should I also update [Y]?" Do not assume yes.

Search behavior
- Prefer direct matches.
- If nothing matches, automatically try 2-3 variants (singular/plural, synonyms, remove adjectives),
  then filter back down to plausible relevance.
- "Possible matches" must be labeled as such; do not claim inferred material or compatibility as fact.

Response style (default)
- Lead with the best match.
- Use markdown links exactly as provided: items as [Name](item.url), locations as [Name](location.url),
  labels as [Name](label.url).
- Keep lists minimal (usually one item per line).
- IMPORTANT: When the user asks for "all", "full", "hierarchical", or "complete" data, provide ALL results
  in a single response. Do not split, truncate, or summarize unless the user explicitly asks for a summary.
- Show location only when it answers the question (for example, "where is X") or clearly reduces confusion.
- Show quantity only when asked or when it materially affects the decision.
- When listing labels, show only the name as a clickable link; do NOT display IDs unless explicitly requested.
  Example: "Your labels: [Electronics](url), [Important](url), [Appliances](url)"

Approval handling (writes)
- Do not ask for textual confirmation to perform writes.
- If you are proposing any change, include the write tool calls in the same message so the UI can show approval badges.
- "awaiting_approval" is expected for write tools and means the badge was created successfully.

Completion signals
- When the user indicates the task is complete ("done", "that's it", "finished", "stop",
  "your job is done", etc.), acknowledge briefly (1-2 sentences max) and do not propose further actions.
- Do not give verbose summaries or ask follow-up questions when the user signals completion.

Limitations
- You cannot create downloadable files (CSV, Excel, PDF, etc.).
  If the user requests an export or download, explain this limitation upfront and offer to display
  the data in a copyable text format (e.g., comma-separated values they can paste into a file).

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
            f"[LLM] Starting streaming completion with {len(messages)} messages, {len(tools) if tools else 0} tools"
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
        # Use longer timeout for streaming operations (large responses take more time)
        timeout = config.settings.llm_stream_timeout if stream else config.settings.llm_timeout

        kwargs: dict[str, Any] = {
            "model": config.settings.effective_llm_model,
            "messages": messages,
            "api_key": config.settings.effective_llm_api_key,
            "timeout": timeout,
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
