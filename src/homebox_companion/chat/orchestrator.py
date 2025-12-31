"""Chat orchestrator for LLM interactions with tool calling.

This module provides the orchestration layer that proxies LLM requests,
handles tool calling, and generates streaming events for the frontend.
"""

from __future__ import annotations

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
from ..mcp.tools import HomeboxMCPTools, ToolPermission
from .session import ChatMessage, ChatSession, PendingApproval, ToolCall, create_approval_id


class ChatEventType(str, Enum):
    """Types of streaming events."""
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"
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
SYSTEM_PROMPT = """You are an intelligent assistant for Homebox Companion, \
a home inventory management application.

The Homebox instance base URL is: {homebox_url}

Your role is to help users manage their inventory by:
- Answering questions about their items, locations, and labels
- Explaining what's in their inventory
- Helping them find items
- Suggesting organization improvements

You have access to the following tools to query the Homebox inventory:
{tool_descriptions}

IMPORTANT GUIDELINES:
1. Use tools to get accurate, up-to-date information from the inventory
2. Be helpful and concise in your responses
3. When listing items or locations, summarize rather than dumping raw data
4. If you don't have enough information, ask clarifying questions
5. Never make up inventory data - always use tools to check

RESPONSE FORMATTING:
When referencing items, locations, or labels in your responses, format them as \
clickable markdown links so users can navigate directly to them in Homebox:
- Items: [Item Name]({homebox_url}/item/ITEM_ID)
- Locations: [Location Name]({homebox_url}/location/LOCATION_ID)
- Labels: [Label Name]({homebox_url}/label/LABEL_ID)

Replace ITEM_ID, LOCATION_ID, or LABEL_ID with the actual 'id' field from the \
tool results. Always use the item/location/label name as the link text.

Example: If search_items returns an item with id="abc-123" and name="USB Cable", \
format it as: [USB Cable]({homebox_url}/item/abc-123)

TOOL USAGE BEST PRACTICES:
- For keyword/semantic searches (e.g., "find rope", "items for building X"),
  always use search_items with a descriptive query
- Use list_items only when you need to browse all items or filter by specific
  location/labels
- When dealing with large inventories, consider using compact=true to reduce
  response size if full details aren't needed
- Use get_item only when you need complete details about a specific item
- If search_items returns many results, you can refine the query or ask the
  user to narrow down their request

EFFICIENT QUERIES:
- For overview questions ("how many items?", "total value?"), use
  get_statistics instead of loading all items
- When given an asset ID (e.g., "000-085"), use get_item_by_asset_id for
  direct lookup
- To understand location hierarchy, use get_location_tree instead of multiple
  get_location calls
- For analytics ("which location has most items?"), use
  get_statistics_by_location or get_statistics_by_label
- To tell users exactly where an item is located, use get_item_path to get the
  full location chain

For write operations (creating, updating, deleting items), you will need to \
propose actions that the user must approve before they execute. This is not \
yet implemented - let users know if they ask for modifications."""

# Maximum recursion depth for tool call continuations
# Prevents infinite loops if LLM keeps making tool calls
MAX_TOOL_RECURSION_DEPTH = 10


def _build_tool_descriptions() -> str:
    """Build tool descriptions for the system prompt."""
    metadata = HomeboxMCPTools.get_tool_metadata()
    lines = []
    for name, meta in metadata.items():
        if meta["permission"] == ToolPermission.READ:
            lines.append(f"- {name}: {meta['description']}")
    return "\n".join(lines)


def _build_litellm_tools() -> list[dict[str, Any]]:
    """Build tool definitions in Litellm/OpenAI format."""
    metadata = HomeboxMCPTools.get_tool_metadata()
    tools = []

    for name, meta in metadata.items():
        # Only expose read-only tools for now
        if meta["permission"] != ToolPermission.READ:
            continue

        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"],
            },
        })

    return tools


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
        self.tools = HomeboxMCPTools(client)
        self.tool_metadata = HomeboxMCPTools.get_tool_metadata()

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

        # Execute tools using already-parsed tool calls (no redundant JSON parsing)
        for parsed_tc in parsed_tool_calls:
            # Check tool permission
            meta = self.tool_metadata.get(parsed_tc.name)
            if not meta:
                yield ChatEvent(
                    type=ChatEventType.ERROR,
                    data={"message": f"Unknown tool: {parsed_tc.name}"}
                )
                continue

            if meta["permission"] == ToolPermission.READ:
                # Auto-execute read-only tools
                async for event in self._execute_tool(
                    parsed_tc.id, parsed_tc.name, parsed_tc.arguments, token
                ):
                    yield event
            else:
                # Queue write tools for approval
                async for event in self._queue_approval(parsed_tc.name, parsed_tc.arguments):
                    yield event

        # Continue conversation with tool results
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
        2. Calls the LLM with tools
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
        system_prompt = SYSTEM_PROMPT.format(
            tool_descriptions=_build_tool_descriptions(),
            homebox_url=settings.homebox_url.rstrip("/"),
        )
        messages = [{"role": "system", "content": system_prompt}]

        # TRACE: Log the full system prompt
        logger.trace(f"[CHAT] System prompt:\n{system_prompt}")

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

        # Call LLM
        try:
            response = await self._call_llm(messages, tools)
        except Exception as e:
            logger.exception("LLM call failed")
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"LLM error: {str(e)}"}
            )
            return

        # Process response
        assistant_message = response.choices[0].message
        content = assistant_message.content or ""
        tool_calls = assistant_message.tool_calls

        # Yield text content if present
        if content:
            yield ChatEvent(type=ChatEventType.TEXT, data={"content": content})

        # Handle tool calls using unified method, or store simple assistant message
        if tool_calls:
            async for event in self._handle_tool_calls(content, tool_calls, token, tools):
                yield event
        else:
            # No tool calls - just store the assistant message
            self.session.add_message(ChatMessage(
                role="assistant",
                content=content,
                tool_calls=None,
            ))

        yield ChatEvent(type=ChatEventType.DONE, data={})

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        """Call the LLM with the given messages and tools.

        Args:
            messages: Conversation messages
            tools: Tool definitions

        Returns:
            LLM response object
        """
        kwargs: dict[str, Any] = {
            "model": config.settings.effective_llm_model,
            "messages": messages,
            "api_key": config.settings.effective_llm_api_key,
            "timeout": config.settings.llm_timeout,
        }

        if config.settings.llm_api_base:
            kwargs["api_base"] = config.settings.llm_api_base

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # TRACE: Log available tools
        tool_names = [t['function']['name'] for t in tools] if tools else []
        logger.trace(f"[CHAT] Available tools: {tool_names}")

        logger.debug(f"Calling LLM with {len(messages)} messages, {len(tools)} tools")

        # TRACE: Time the LLM call
        start_time = time.perf_counter()
        response = await litellm.acompletion(**kwargs)
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
                logger.trace(f"[CHAT] LLM tool call: {tc.function.name}({tc.function.arguments})")
        else:
            logger.trace("[CHAT] LLM made no tool calls")

        return response

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

        tool_method = getattr(self.tools, tool_name, None)
        if not tool_method:
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
            result = await tool_method(token, **tool_args)
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
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> AsyncGenerator[ChatEvent, None]:
        """Queue a write tool for approval.

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments

        Yields:
            Approval required event
        """
        approval_id = create_approval_id()
        approval = PendingApproval(
            id=approval_id,
            tool_name=tool_name,
            parameters=tool_args,
        )
        self.session.add_pending_approval(approval)

        yield ChatEvent(
            type=ChatEventType.APPROVAL_REQUIRED,
            data={
                "id": approval_id,
                "tool": tool_name,
                "params": tool_args,
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
        Uses the unified _handle_tool_calls method for consistent handling.

        Args:
            token: Auth token
            tools: Tool definitions
            depth: Current recursion depth (passed to _handle_tool_calls)

        Yields:
            Additional chat events
        """
        system_prompt = SYSTEM_PROMPT.format(
            tool_descriptions=_build_tool_descriptions(),
            homebox_url=settings.homebox_url.rstrip("/"),
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.session.get_history())

        try:
            response = await self._call_llm(messages, tools)
        except Exception as e:
            logger.exception("LLM continuation failed")
            yield ChatEvent(
                type=ChatEventType.ERROR,
                data={"message": f"LLM error: {str(e)}"}
            )
            return

        assistant_message = response.choices[0].message
        content = assistant_message.content or ""
        tool_calls = assistant_message.tool_calls

        if content:
            yield ChatEvent(type=ChatEventType.TEXT, data={"content": content})

        # Handle tool calls using unified method, or store simple assistant message
        if tool_calls:
            async for event in self._handle_tool_calls(
                content, tool_calls, token, tools, depth
            ):
                yield event
        else:
            # No tool calls - just store the assistant message
            self.session.add_message(ChatMessage(
                role="assistant",
                content=content,
                tool_calls=None,
            ))
