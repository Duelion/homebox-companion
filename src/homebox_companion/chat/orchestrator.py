"""Chat orchestrator for LLM interactions with tool calling.

This module provides the orchestration layer that proxies LLM requests,
handles tool calling, and generates streaming events for the frontend.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any

import litellm
from loguru import logger

from ..core import config
from ..core.config import settings
from ..homebox.client import HomeboxClient
from ..mcp.tools import get_tools
from ..mcp.types import MAX_RESULT_ITEMS, ToolPermission
from .session import (
    ChatMessage,
    ChatSession,
    DisplayInfo,
    PendingApproval,
    ToolCall,
    create_approval_id,
)


class ChatEventType(str, Enum):
    """Types of streaming events."""
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"
    USAGE = "usage"
    DONE = "done"


@dataclass
class ChatEvent:
    """A streaming event from the orchestrator.

    Attributes:
        type: The event type
        data: Event data (varies by type)
    """
    type: ChatEventType
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"event: {self.type.value}\ndata: {json.dumps(self.data)}\n\n"


# System prompt for the assistant
# Note: Tool definitions are passed dynamically via the tools parameter,
# so we focus on behavioral guidance and response formatting here.
SYSTEM_PROMPT = f"""You are a Homebox inventory assistant. Help users find and manage their items.

EFFICIENCY RULES:
- Use the most appropriate tool for each query (tool definitions are provided separately)
- For listing locations/items, use the list tool ONCE - do NOT call get_* for each result
- For "find X" or "where is X" queries, use search_items
- For "items in [location]", use list_items with location filter

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

# Maximum recursion depth for tool call continuations
# Prevents infinite loops if LLM keeps making tool calls
MAX_TOOL_RECURSION_DEPTH = 10

# Tool cache with TTL for performance
_tool_cache: tuple[list[dict[str, Any]], float] | None = None
_TOOL_CACHE_TTL = 300  # 5 minutes





def _build_litellm_tools() -> list[dict[str, Any]]:
    """Build tool definitions in Litellm/OpenAI format with caching."""
    global _tool_cache

    # Return cached tools if still valid
    if _tool_cache and (time.time() - _tool_cache[1]) < _TOOL_CACHE_TTL:
        return _tool_cache[0]

    all_tools = get_tools()
    tools = []

    for tool in all_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.Params.model_json_schema(),
            },
        })

    _tool_cache = (tools, time.time())
    logger.debug(f"Built and cached {len(tools)} tool definitions")
    return tools


def generate_confirmation_message(
    tool_name: str,
    success: bool,
    data: Any,
    error: str | None = None,
) -> str:
    """Generate a brief confirmation message after tool execution.

    Uses simple template-based messages instead of LLM calls to avoid
    latency and token costs for simple confirmations.

    Args:
        tool_name: Name of the tool that was executed
        success: Whether the execution was successful
        data: Result data from the tool execution
        error: Error message if execution failed

    Returns:
        Brief confirmation message with ✓ or ✗ prefix
    """
    if not success:
        return f"✗ {tool_name} failed: {error or 'Unknown error'}"

    # Build a human-readable summary based on the data
    summary = ""
    try:
        if isinstance(data, dict):
            # Common patterns for our tools
            if "name" in data:
                summary = f"'{data['name']}'"
            elif "id" in data:
                summary = f"(ID: {data['id'][:8]}...)" if len(str(data.get('id', ''))) > 8 else f"(ID: {data['id']})"
        elif isinstance(data, list):
            count = len(data)
            summary = f"{count} item{'s' if count != 1 else ''}"
        elif data is not None:
            summary = str(data)[:50]
    except Exception:
        # If anything goes wrong parsing data, just skip the summary
        pass

    if summary:
        return f"✓ {tool_name} completed: {summary}"
    else:
        return f"✓ {tool_name} completed successfully."


class ChatOrchestrator:
    """Orchestrates LLM calls with MCP tool integration.

    This class manages the conversation flow, including:
    - Building prompts with conversation history
    - Calling the LLM with tool definitions
    - Executing read-only tools automatically
    - Creating pending approvals for write tools
    - Generating streaming events for the frontend
    """

    def __init__(self, client: HomeboxClient, session: ChatSession):
        """Initialize the orchestrator.

        Args:
            client: HomeboxClient for tool execution
            session: ChatSession for conversation state
        """
        self.client = client
        self.session = session
        # Discover tools and build lookup tables
        self._all_tools = get_tools()
        self._tools_by_name = {t.name: t for t in self._all_tools}

    def _parse_tool_calls(self, tool_calls: list[Any]) -> list[ToolCall]:
        """Parse raw LLM tool calls into ToolCall objects.

        This centralizes JSON argument parsing to avoid duplication.

        Args:
            tool_calls: Raw tool calls from LLM response

        Returns:
            List of parsed ToolCall objects
        """
        parsed = []
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            parsed.append(ToolCall(
                id=tc.id,
                name=tool_name,
                arguments=tool_args,
            ))
        return parsed

    async def _handle_tool_calls(
        self,
        content: str,
        tool_calls: list[Any],
        token: str,
        tools: list[dict[str, Any]],
        depth: int = 0,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Unified handler for LLM responses with tool calls.

        This method centralizes all tool handling logic:
        1. Parses tool calls
        2. Adds assistant message with tool_calls to session
        3. Executes tools (yielding events)
        4. Continues conversation with tool results (recursive)

        Args:
            content: The assistant message content
            tool_calls: Raw tool calls from LLM response
            token: Homebox auth token
            tools: Tool definitions for recursive LLM calls
            depth: Current recursion depth (for safety limit)

        Yields:
            ChatEvent objects for SSE streaming
        """
        # Safety check: prevent infinite recursion
        if depth >= MAX_TOOL_RECURSION_DEPTH:
            logger.warning(
                f"[CHAT] Max tool recursion depth ({MAX_TOOL_RECURSION_DEPTH}) reached"
            )
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": "Max tool recursion depth reached. Please try a simpler query."}
            )
            return

        # Parse tool calls once
        parsed_tool_calls = self._parse_tool_calls(tool_calls)

        # IMPORTANT: Add assistant message with tool_calls BEFORE executing tools
        # OpenAI API requires tool messages to follow an assistant message with tool_calls
        self.session.add_message(ChatMessage(
            role="assistant",
            content=content,
            tool_calls=parsed_tool_calls,
        ))

        # Track results and approvals
        has_pending_approvals = False

        # Group tools for parallel execution (READ only)
        read_calls = []
        sequential_calls = []

        for parsed_tc in parsed_tool_calls:
            tool = self._tools_by_name.get(parsed_tc.name)
            if not tool:
                # Unknown tool - handle sequentially to report error
                sequential_calls.append(parsed_tc)
            elif tool.permission == ToolPermission.READ:
                read_calls.append(parsed_tc)
            else:
                sequential_calls.append(parsed_tc)

        # 1. Execute READ tools in parallel for maximum performance
        if read_calls:
            logger.debug(f"[CHAT] Executing {len(read_calls)} read tools in parallel")

            async def run_and_collect(tc):
                collected_events = []
                async for event in self._execute_tool(tc.id, tc.name, tc.arguments, token):
                    collected_events.append(event)
                return collected_events

            # Gather all parallel results
            parallel_results = await asyncio.gather(
                *(run_and_collect(tc) for tc in read_calls)
            )

            # Yield all collected events
            for event_list in parallel_results:
                for event in event_list:
                    yield event

        # 2. Execute remaining tools (WRITE/Unknown) sequentially
        for parsed_tc in sequential_calls:
            tool = self._tools_by_name.get(parsed_tc.name)
            if not tool:
                # Add error tool result
                error_dict = {"success": False, "error": f"Unknown tool: {parsed_tc.name}"}
                self.session.add_message(ChatMessage(
                    role="tool",
                    content=json.dumps(error_dict),
                    tool_call_id=parsed_tc.id,
                ))
                yield ChatEvent(
                    type=ChatEventType.ERROR,
                    data={"message": f"Unknown tool: {parsed_tc.name}"}
                )
                continue

            # Queue write tools for approval
            has_pending_approvals = True
            async for event in self._queue_approval(
                parsed_tc.id, parsed_tc.name, parsed_tc.arguments, token
            ):
                yield event

        # 3. Only continue conversation if no approvals are pending
        # When approvals are pending, the conversation will resume after user action
        if not has_pending_approvals:
            async for event in self._continue_with_tool_results(token, tools, depth + 1):
                yield event

    async def process_message(
        self,
        user_message: str,
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Process a user message and yield streaming events.

        This method:
        1. Adds the user message to history
        2. Calls the LLM with tools (streaming)
        3. Handles tool calls (auto-execute READ, queue WRITE for approval)
        4. Yields streaming events

        Args:
            user_message: The user's message content
            token: Homebox auth token for tool execution

        Yields:
            ChatEvent objects for SSE streaming
        """
        if not settings.chat_enabled:
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": "Chat feature is disabled"}
            )
            return

        # TRACE: Log the start of a new conversation turn
        logger.trace("[CHAT] === NEW MESSAGE ===")
        logger.trace(f"[CHAT] User message:\n{user_message}")
        logger.trace(f"[CHAT] Session state: {len(self.session.messages)} messages in history")

        # Add user message to history
        self.session.add_message(ChatMessage(role="user", content=user_message))

        # Build messages for LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # TRACE: Log the full system prompt
        logger.trace(f"[CHAT] System prompt:\n{SYSTEM_PROMPT}")

        # Get conversation history
        history = self.session.get_history()
        messages.extend(history)

        # TRACE: Log conversation history being sent to LLM
        logger.trace(f"[CHAT] Sending {len(history)} history messages to LLM")
        for i, msg in enumerate(history):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate very long tool results for readability
            if len(content) > 500:
                content_preview = content[:500] + '...'
            else:
                content_preview = content
            logger.trace(f"[CHAT] History[{i}] {role}: {content_preview}")

        # Build tool definitions
        tools = _build_litellm_tools()

        # Call LLM with streaming
        try:
            stream_response = await self._call_llm(messages, tools, stream=True)
        except Exception as e:
            logger.exception("LLM call failed")
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"LLM error: {str(e)}"}
            )
            return

        # Process streaming response
        async for event in self._handle_streaming_response(stream_response, token, tools):
            yield event

        yield ChatEvent(type=ChatEventType.DONE, data={})

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = True,
    ) -> Any:
        """Call the LLM with the given messages and tools.

        Args:
            messages: Conversation messages
            tools: Tool definitions
            stream: If True, return streaming response; if False, return complete response

        Returns:
            LLM response object (streaming or complete)
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
        tool_names = [t['function']['name'] for t in tools] if tools else []
        logger.trace(f"[CHAT] Available tools: {tool_names}")

        logger.debug(
            f"Calling LLM with {len(messages)} messages, {len(tools)} tools "
            f"(streaming={stream})"
        )

        # TRACE: Time the LLM call
        start_time = time.perf_counter()
        response = await litellm.acompletion(**kwargs)

        if not stream:
            # Non-streaming: log immediately
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # TRACE: Log token usage if available
            if hasattr(response, 'usage') and response.usage:
                logger.trace(
                    f"[CHAT] LLM call completed in {elapsed_ms:.0f}ms - "
                    f"tokens: prompt={response.usage.prompt_tokens}, "
                    f"completion={response.usage.completion_tokens}, "
                    f"total={response.usage.total_tokens}"
                )
            else:
                logger.trace(f"[CHAT] LLM call completed in {elapsed_ms:.0f}ms")

            # TRACE: Log full response content
            assistant_message = response.choices[0].message
            content = assistant_message.content or ""
            if content:
                logger.trace(f"[CHAT] LLM response content:\n{content}")
            else:
                logger.trace("[CHAT] LLM response content: (empty)")

            # TRACE: Log tool call decisions
            tool_calls = assistant_message.tool_calls
            if tool_calls:
                for tc in tool_calls:
                    logger.trace(
                        f"[CHAT] LLM tool call: "
                        f"{tc.function.name}({tc.function.arguments})"
                    )
            else:
                logger.trace("[CHAT] LLM made no tool calls")

        return response

    async def _handle_streaming_response(
        self,
        stream_response: Any,
        token: str,
        tools: list[dict[str, Any]],
        depth: int = 0,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Handle a streaming LLM response.

        Accumulates chunks, yields text events, and handles tool calls when complete.

        Args:
            stream_response: Streaming response from LLM
            token: Homebox auth token
            tools: Tool definitions for recursive calls
            depth: Current recursion depth

        Yields:
            ChatEvent objects for SSE streaming
        """
        content_chunks = []
        tool_call_chunks: dict[int, dict[str, Any]] = {}  # idx -> {id, name, arguments}
        usage_info = None  # Track token usage from final chunk

        start_time = time.perf_counter()
        chunk_count = 0

        try:
            async for chunk in stream_response:
                chunk_count += 1

                if not hasattr(chunk, 'choices') or not chunk.choices:
                    # Some providers send usage-only chunks at the end
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage_info = chunk.usage
                    continue

                choice = chunk.choices[0]

                # Handle content from delta (standard streaming)
                if hasattr(choice, 'delta') and choice.delta:
                    delta = choice.delta
                    if hasattr(delta, 'content') and delta.content:
                        content_chunk = delta.content
                        content_chunks.append(content_chunk)
                        # Yield individual text chunk for real-time display
                        yield ChatEvent(type=ChatEventType.TEXT, data={"content": content_chunk})

                    # Handle tool call streaming (accumulate)
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_call_chunks:
                                tool_call_chunks[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": ""
                                }

                            if tc_delta.id:
                                tool_call_chunks[idx]["id"] = tc_delta.id
                            if tc_delta.function and tc_delta.function.name:
                                tool_call_chunks[idx]["name"] = tc_delta.function.name
                            if tc_delta.function and tc_delta.function.arguments:
                                tool_call_chunks[idx]["arguments"] += tc_delta.function.arguments

                # Handle content from message (non-incremental streaming / final chunk)
                # Some providers send complete content in message field instead of delta
                if hasattr(choice, 'message') and choice.message:
                    message = choice.message
                    if hasattr(message, 'content') and message.content:
                        # Only add if we haven't seen this content yet (avoid duplicates)
                        if message.content not in content_chunks:
                            content_chunks.append(message.content)
                            yield ChatEvent(
                                type=ChatEventType.TEXT,
                                data={"content": message.content}
                            )

                    # Also check for tool calls in message
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for idx, tc in enumerate(message.tool_calls):
                            if idx not in tool_call_chunks:
                                tool_call_chunks[idx] = {
                                    "id": tc.id if hasattr(tc, 'id') else "",
                                    "name": (
                                        tc.function.name
                                        if hasattr(tc, "function") and tc.function
                                        else ""
                                    ),
                                    "arguments": (
                                        tc.function.arguments
                                        if hasattr(tc, "function") and tc.function
                                        else ""
                                    ),
                                }

                # Capture usage info from chunk
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage_info = chunk.usage

        except Exception as e:
            logger.exception("[CHAT] Error during streaming")
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"Streaming error: {str(e)}"}
            )
            return

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Log completion with token usage if available
        if usage_info:
            logger.trace(
                f"[CHAT] Streaming completed in {elapsed_ms:.0f}ms - "
                f"{chunk_count} chunks received - "
                f"tokens: prompt={usage_info.prompt_tokens}, "
                f"completion={usage_info.completion_tokens}, "
                f"total={usage_info.total_tokens}"
            )
            # Emit usage event for frontend
            yield ChatEvent(
                type=ChatEventType.USAGE,
                data={
                    "prompt_tokens": usage_info.prompt_tokens,
                    "completion_tokens": usage_info.completion_tokens,
                    "total_tokens": usage_info.total_tokens,
                }
            )
        else:
            logger.trace(
                f"[CHAT] Streaming completed in {elapsed_ms:.0f}ms - "
                f"{chunk_count} chunks received"
            )

        # Reconstruct complete content
        full_content = "".join(content_chunks)

        # UX Improvement: Handle "random/bulk creation" lead-in if content is empty
        # This addresses the "silent assumptions" flagged in the UX critique
        if not full_content and tool_call_chunks:
            # Check if we are doing bulk creates
            create_calls = [tc for tc in tool_call_chunks.values() if tc["name"] == "create_item"]
            if len(create_calls) > 1:
                full_content = f"I'll create {len(create_calls)} sample items for you..."
                yield ChatEvent(type=ChatEventType.TEXT, data={"content": full_content})

        if full_content:
            logger.trace(f"[CHAT] Complete streamed content:\n{full_content}")
        elif usage_info and usage_info.completion_tokens > 0 and not tool_call_chunks:
            # We have completion tokens but no content and no tool calls - something is wrong
            logger.warning(
                f"[CHAT] No content captured despite {usage_info.completion_tokens} "
                f"completion tokens. This may indicate a streaming format issue."
            )

        # Reconstruct tool calls if any
        tool_calls = []
        if tool_call_chunks:
            # Define mock classes outside loop (efficiency + cleaner code)
            @dataclass
            class MockFunction:
                name: str
                arguments: str

            @dataclass
            class MockToolCall:
                id: str
                function: MockFunction

            for idx in sorted(tool_call_chunks.keys()):
                tc_data = tool_call_chunks[idx]

                # Validate tool call has required fields
                if not tc_data["id"] or not tc_data["name"]:
                    logger.warning(
                        f"[CHAT] Skipping incomplete tool call: id={tc_data['id']}, "
                        f"name={tc_data['name']}"
                    )
                    continue

                tool_calls.append(MockToolCall(
                    id=tc_data["id"],
                    function=MockFunction(
                        name=tc_data["name"],
                        arguments=tc_data["arguments"]
                    )
                ))

            # Log tool calls
            for tc in tool_calls:
                logger.trace(f"[CHAT] LLM tool call: {tc.function.name}({tc.function.arguments})")
        else:
            logger.trace("[CHAT] LLM made no tool calls")

        # Handle tool calls if present
        if tool_calls:
            async for event in self._handle_tool_calls(
                full_content, tool_calls, token, tools, depth
            ):
                yield event
        else:
            # No tool calls - just store the assistant message
            self.session.add_message(ChatMessage(
                role="assistant",
                content=full_content,
                tool_calls=None,
            ))

    async def _get_display_info(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
    ) -> DisplayInfo:
        """Fetch human-readable display info for an approval.

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            token: Auth token for Homebox

        Returns:
            Dictionary with display-friendly info (item_name, location, etc.)
        """
        display_info: DisplayInfo = {}

        try:
            # Handle tools that operate on existing items
            if tool_name in ("delete_item", "update_item") and "item_id" in tool_args:
                item = await self.client.get_item(token, tool_args["item_id"])
                # item is a dict, not an object - use dict access
                display_info["item_name"] = item.get("name")
                if item.get("assetId"):
                    display_info["asset_id"] = item.get("assetId")
                # Include location for delete actions
                if tool_name == "delete_item" and item.get("location"):
                    display_info["location"] = item["location"].get("name")

            elif tool_name == "create_item":
                # For create, use the name from the params
                if "name" in tool_args:
                    display_info["item_name"] = tool_args["name"]
                if "location_id" in tool_args:
                    try:
                        location = await self.client.get_location(
                            token, tool_args["location_id"]
                        )
                        display_info["location"] = location.get("name")
                    except Exception as e:
                        logger.debug(
                            f"Location lookup failed for {tool_args['location_id']}: {e}"
                        )

        except Exception as e:
            # Don't fail the approval if we can't fetch display info
            logger.debug(f"Failed to fetch display info for {tool_name}: {e}")

        return display_info

    async def _execute_tool(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Execute a read-only tool and yield events.

        Args:
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            tool_args: Tool arguments
            token: Auth token for Homebox

        Yields:
            Tool execution events
        """
        # TRACE: Log tool execution start
        logger.trace(f"[CHAT] Executing tool: {tool_name}")
        logger.trace(f"[CHAT] Tool arguments: {json.dumps(tool_args, indent=2)}")

        yield ChatEvent(
            type=ChatEventType.TOOL_START,
            data={"tool": tool_name, "params": tool_args}
        )

        tool = self._tools_by_name.get(tool_name)
        if not tool:
            error_result = {"success": False, "error": f"Tool not implemented: {tool_name}"}
            self.session.add_message(ChatMessage(
                role="tool",
                content=json.dumps(error_result),
                tool_call_id=tool_call_id,
            ))
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"Tool not implemented: {tool_name}"}
            )
            return

        try:
            # TRACE: Time the tool execution
            start_time = time.perf_counter()
            # Validate and execute with Pydantic params
            params = tool.Params(**tool_args)
            result = await tool.execute(self.client, token, params)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            result_dict = result.to_dict()

            # TRACE: Log full tool result (may be large for list operations)
            result_json = json.dumps(result_dict, indent=2)
            if len(result_json) > 2000:
                logger.trace(
                    f"[CHAT] Tool '{tool_name}' result "
                    f"({elapsed_ms:.0f}ms, {len(result_json)} chars):\n"
                    f"{result_json[:2000]}...[truncated]"
                )
            else:
                logger.trace(
                    f"[CHAT] Tool '{tool_name}' result ({elapsed_ms:.0f}ms):\n{result_json}"
                )

        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")
            result_dict = {"success": False, "error": str(e)}

        # Add tool result to history
        self.session.add_message(ChatMessage(
            role="tool",
            content=json.dumps(result_dict),
            tool_call_id=tool_call_id,
        ))

        yield ChatEvent(
            type=ChatEventType.TOOL_RESULT,
            data={"tool": tool_name, "result": result_dict}
        )

    async def _queue_approval(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Queue a write tool for approval.

        Also adds a placeholder tool result message to satisfy OpenAI API requirements
        that every tool_call_id must have a corresponding tool result message.

        Args:
            tool_call_id: ID of the tool call from the LLM
            tool_name: Name of the tool
            tool_args: Tool arguments
            token: Auth token for fetching display info

        Yields:
            Approval required event
        """
        # Fetch display-friendly info for better UX
        display_info = await self._get_display_info(tool_name, tool_args, token)

        approval_id = create_approval_id()
        approval = PendingApproval(
            id=approval_id,
            tool_name=tool_name,
            parameters=tool_args,
            display_info=display_info,
        )
        self.session.add_pending_approval(approval)

        # Add placeholder tool result to satisfy OpenAI API requirements
        # Every tool_call_id must have a corresponding tool result message
        self.session.add_message(ChatMessage(
            role="tool",
            content=json.dumps({
                "success": False,
                "pending_approval": True,
                "approval_id": approval_id,
                "message": f"Action '{tool_name}' requires user approval before execution."
            }),
            tool_call_id=tool_call_id,
        ))

        yield ChatEvent(
            type=ChatEventType.APPROVAL_REQUIRED,
            data={
                "id": approval_id,
                "tool": tool_name,
                "params": tool_args,
                "display_info": display_info,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
            }
        )

    async def _continue_with_tool_results(
        self,
        token: str,
        tools: list[dict[str, Any]],
        depth: int = 0,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Continue conversation after tool execution.

        This calls the LLM again with tool results to get a final response.
        Uses streaming for real-time feedback.

        Args:
            token: Auth token
            tools: Tool definitions
            depth: Current recursion depth (passed to _handle_streaming_response)

        Yields:
            Additional chat events
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.session.get_history())

        try:
            stream_response = await self._call_llm(messages, tools, stream=True)
        except Exception as e:
            logger.exception("LLM continuation failed")
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"LLM error: {str(e)}"}
            )
            return

        async for event in self._handle_streaming_response(
            stream_response, token, tools, depth
        ):
            yield event
