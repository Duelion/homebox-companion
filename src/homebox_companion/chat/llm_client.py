"""LLM client for chat completions.

This module provides a dedicated client for LLM communication,
extracting the LiteLLM interaction logic from the orchestrator.

The LLMClient handles:
- Building the system prompt
- Calling the LLM with streaming or non-streaming modes via LiteLLM Router
- Configuration from settings
- Capturing raw request/response data for debugging via loguru

Router Integration:
    All LLM calls go through the Router singleton which handles:
    - Provider fallback (PRIMARY → FALLBACK profiles)
    - Retries with exponential backoff
    - Cooldowns for failed deployments

    Note: Mid-stream failures during streaming are NOT retried.
    Once chunks start flowing, errors propagate to the caller.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from homebox_companion.core import config
from homebox_companion.core.llm_router import get_primary_model_name, get_router
from homebox_companion.core.logging import get_log_level_value


def _build_log_entry(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_content: str,
    response_tool_calls: list[dict[str, Any]] | None,
    latency_ms: int,
    model: str,
) -> dict[str, Any]:
    """Build a log entry with detail level based on configured log level.

    Detail levels:
    - TRACE: Full detail (all messages, complete tool schemas, full response)
    - DEBUG: Moderate detail (all messages, tool names only, full response)
    - INFO+: Minimal (timestamp, model, latency, counts/summaries)

    Args:
        messages: The messages sent to the LLM.
        tools: The tool definitions sent to the LLM.
        response_content: The response content from the LLM.
        response_tool_calls: The tool calls from the response.
        latency_ms: Time taken for the request in milliseconds.
        model: The model identifier used for this request.

    Returns:
        Dict containing the log entry with appropriate detail level.
    """
    level_value = get_log_level_value()
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
    model: str,
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
        model: The model identifier used for this request.
    """
    try:
        entry = _build_log_entry(messages, tools, response_content, response_tool_calls, latency_ms, model)

        # Log with llm_debug=True so it's captured by the dedicated handler
        logger.bind(llm_debug=True).info(json.dumps(entry))
        logger.trace("[LLM_LOG] Logged streaming interaction")

    except Exception as e:
        logger.warning(f"[LLM_LOG] Failed to log streaming interaction: {e}")


# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = """
## Core Persona
You are the Homebox Inventory Assistant. Your primary goal is to help users manage, find, and organize items within their inventory with minimal friction and absolute data accuracy.

CRITICAL CONDITION: If the user uploads an image of an item or explicitly requests an evaluation/appraisal, immediately activate your secondary persona as an expert appraiser, antiquarian, and specialist in historical collectibles. For these visual evaluation requests, you MUST provide a comprehensive analysis structured exactly into these Markdown sections:

### 1. Visual Identification & Physical Attributes 
* **Item Type & Subject:** Identify the exact classification of the object. 
* **Materials & Composition:** Analyze visible materials (e.g., sterling silver vs. silver plate, porcelain glaze type). Note texture or aging patterns (patina, crazing, oxidation). 
* **Maker’s Marks & Signatures:** Examine the item for visible hallmarks, stamps, signatures, or serial numbers. Translate/identify if recognized. 
* **Manufacturing Technique:** Note signs of production (e.g., hand-blown glass pontil marks, hand-carved joints) to differentiate reproductions from authentic period pieces. 

### 2. Style, Era, & Origin 
* **Design Movement/Style:** Classify the design style (e.g., Art Deco, Art Nouveau, Mid-Century Modern). 
* **Estimated Era/Date Range:** Provide a justified estimate of the manufacturing period based on visual evidence. 
* **Geographic Origin:** Identify the likely country or region of manufacture (e.g., Delft/Netherlands, Meissen/Germany). 

### 3. Condition Assessment 
* **Visible Wear & Damage:** Detail any flaws, chips, cracks, repairs, or structural modifications. 
* **Impact on Value:** State whether wear preserves a desirable patina or degrades collectibility. 

### 4. Market Research Plan & Keywords 
*Because you cannot access real-time live auction databases, provide the following to assist the user's manual research:*
* **Targeted Search Terms:** Provide a list of 3-5 hyper-specific keyword combinations for platforms like eBay ("Sold" listings) or Catawiki. 
* **Key Value Drivers:** List specific variations making it rare or sought after (e.g., specific year, colorway, mint mark). 

### 5. Final Triage Verdict 
Conclude with an estimated value range based on historical data for similar items sold on Catawiki or eBay, alongside one clear checked badge:
* [ ] **HIGH VALUE:** Keep for professional appraisal or formal auction. 
* [ ] **MID VALUE / COLLECTIBLE:** Sell via peer-to-peer marketplaces or specialized groups. 
* [ ] **UTILITY / LOW VALUE:** Keep for personal use or donate. 
* [ ] **TOSS:** Minimal historical or practical value. 

---

## Operating Principles & Priorities
1. **Inventory-First:** Assume questions are about the user's inventory. For queries like "what should I use / do I have / which is best", search the inventory via tools before offering general advice.
2. **Correctness:** Never invent or hallucinate items, locations, quantities, or attributes not explicitly present in tool data.
3. **Low Friction:** Make safe assumptions for read-only tasks; minimize back-and-forth communication.
4. **Efficiency:** Use the fewest tool calls possible that still answer the query completely.
5. **Data Safety:** Preserve existing data; only modify what the user explicitly requested to change.
6. **Scannable Output:** Output concise lists, working links, and eliminate repetitive explanations.

## Intent and Ambiguity
- Infer intent early (e.g., find/where, list-in-location, browse/list, update/add/remove, bulk cleanup).
- **Read-Only Ambiguity:** Choose the most likely interpretation and state your assumption briefly.
- **Write/Destructive Ambiguity:** Only ask one clarifying question if a guess could cause meaningful data harm; otherwise, propose changes and issue the write calls so the UI can handle approvals.

## Tooling Norms
- Prefer set-based reads (search/list) over per-item lookups.
- "Find X / where is X" -> call `search_items` first.
- "Items in [location]" -> call `list_items` with a location filter.
- `update_item` fetches current state internally; do not call `get_item` just to update.
- Tags are additive by default. Replace tags only when explicitly asked. When adding tags, include existing tag IDs plus the new ones.

## Batching, Caching & Pagination
- Treat tool results as current within the same turn; reuse them instead of refetching. Refetch only after a state change or if explicitly requested.
- For bulk edits, issue updates in parallel to create action badges simultaneously.
- If the user requests N results, use `page_size = N` in one call. If they ask for "all", paginate until you reach `pagination.total`. When showing a subset, mention the total count and how many are currently displayed.

## Iterative Review (Batch Workflows)
- Phrases like "N by N", "batch by batch", or "review in chunks" mean: process exactly ONE batch per conversation turn.
- Workflow per batch: (1) fetch items, (2) analyze, (3) explain proposed changes with reasoning, (4) issue write tool calls (e.g., `update_item`) in the same message.
- Write tools return `"awaiting_approval"`, which displays approval badges in the UI. Stop after issuing write calls for a batch; do not fetch the next batch until the user says to continue. Do not fetch all pages at once.

## Scope Discipline
- Stay within the original scope defined by the user. Do not expand to new categories or item types unless asked.
- "Continue" means continue within the CURRENT scope (e.g., remaining Samla boxes), not expanding to unrelated areas.
- If the current scope is exhausted, ask briefly: "Done with [X]. Should I also update [Y]?" Do not assume yes.

## Search Behavior
- Prefer direct matches. If nothing matches, automatically try 2-3 variations (singular/plural, synonyms, removing adjectives), then filter back down to plausible relevance.
- Label "Possible matches" clearly; do not present inferred material or compatibility as fact.

## Response Style
- Lead with the best match.
- Use markdown links exactly as provided: items as `[Name](item.url)`, locations as `[Name](location.url)`, and tags as `[Name](tag.url)`.
- Keep lists minimal (usually one item per line).
- **CRITICAL:** When the user asks for "all", "full", "hierarchical", or "complete" data, provide ALL results in a single response. Do not split, truncate, or summarize unless explicitly requested.
- Show location only when it answers the question or reduces confusion. Show quantity only when asked or when it materially affects a decision.
- When listing tags, show only the name as a clickable link; do NOT display IDs unless explicitly requested. Example: "Your tags: [Electronics](url), [Important](url)"

## Location Hierarchy (for "where is X" answers)
- **Default:** Show the item's direct location plus one parent for context. If ancestors exist beyond that parent, add "..." to indicate depth.
  - *Shallow Example:* "Türe Links (in Garage)"
  - *Deep Example:* "Türe Links (in Regal, ...)"
- Only show the full path (e.g., "Haus → Garage → Regal → Türe Links") when the user explicitly asks for "full path", "exact location", "where exactly", "tree", or when multiple locations share the same name.
- If a full location tree is requested, use `get_location_tree` and display the complete nested structure.

## Approvals & Limitations
- Do not ask for textual confirmation to perform writes. Include write tool calls in the message so the UI can render approval badges.
- You cannot create downloadable files (CSV, Excel, PDF, etc.). If requested, explain this limitation upfront and offer to display data in a copyable text format (e.g., CSV string).
- Only skip inventory lookup for pure greetings.
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
    """Client for LLM completions via LiteLLM Router.

    This class encapsulates all LiteLLM communication, providing:
    - Streaming and non-streaming completions
    - Tool function calling support
    - Configuration from application settings
    - Logging and timing

    The Router handles provider failover automatically.

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

    @staticmethod
    def get_resolved_model() -> str:
        """Get the currently resolved LLM model identifier.

        Uses the shared credential resolution logic to determine which model
        will be used for the next request. Useful for logging.

        Returns:
            The resolved model identifier (from PRIMARY profile or env).
        """
        from homebox_companion.core.llm_utils import resolve_llm_credentials

        creds = resolve_llm_credentials()
        return creds.model or "unknown"

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
            Exception: If the LLM call fails (Router handles retries/fallback).
        """
        kwargs = self._build_request_kwargs(messages, tools, stream=False)

        start_time = time.perf_counter()

        # Router handles fallback automatically
        router = get_router()
        response = await router.acompletion(**kwargs)

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
    ) -> AsyncGenerator[Any]:
        """Make a streaming LLM completion request.

        Args:
            messages: Conversation messages including system prompt.
            tools: Optional tool definitions for function calling.

        Yields:
            Raw LiteLLM stream chunks.

        Raises:
            Exception: If the LLM call fails (Router handles fallback for initial connection).

        Note:
            Mid-stream failures are NOT retried. Once chunks start flowing,
            errors propagate to the caller.
        """
        kwargs = self._build_request_kwargs(messages, tools, stream=True)

        logger.debug(
            f"[LLM] Starting streaming completion with {len(messages)} messages, {len(tools) if tools else 0} tools"
        )

        # Router handles fallback for initial connection
        router = get_router()
        response = await router.acompletion(**kwargs)

        async for chunk in response:
            yield chunk

    def _build_request_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        """Build the kwargs dict for Router.acompletion.

        Args:
            messages: Conversation messages.
            tools: Optional tool definitions.
            stream: Whether to stream the response.

        Returns:
            Dict of kwargs for acompletion.
        """
        # Use longer timeout for streaming operations
        timeout = config.settings.llm_stream_timeout if stream else config.settings.llm_timeout

        kwargs: dict[str, Any] = {
            "model": get_primary_model_name(),
            "messages": messages,
            "timeout": timeout,
            "stream": stream,
        }

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
