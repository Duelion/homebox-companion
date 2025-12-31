"""Chat orchestrator for LLM interactions with tool calling.

This module provides the orchestration layer that proxies LLM requests,
handles tool calling, and generates streaming events for the frontend.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator

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
SYSTEM_PROMPT = """You are an intelligent assistant for Homebox Companion, a home inventory management application.

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

For write operations (creating, updating, deleting items), you will need to propose actions that the user must approve before they execute. This is not yet implemented - let users know if they ask for modifications."""


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

        # Add user message to history
        self.session.add_message(ChatMessage(role="user", content=user_message))

        # Build messages for LLM
        system_prompt = SYSTEM_PROMPT.format(tool_descriptions=_build_tool_descriptions())
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.session.get_history())

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

        # Handle tool calls
        parsed_tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                parsed_tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tool_name,
                    arguments=tool_args,
                ))

                # Check tool permission
                meta = self.tool_metadata.get(tool_name)
                if not meta:
                    yield ChatEvent(
                        type=ChatEventType.ERROR,
                        data={"message": f"Unknown tool: {tool_name}"}
                    )
                    continue

                if meta["permission"] == ToolPermission.READ:
                    # Auto-execute read-only tools
                    async for event in self._execute_tool(tc.id, tool_name, tool_args, token):
                        yield event
                else:
                    # Queue write tools for approval
                    async for event in self._queue_approval(tool_name, tool_args):
                        yield event

        # Store assistant message with tool calls
        self.session.add_message(ChatMessage(
            role="assistant",
            content=content,
            tool_calls=parsed_tool_calls if parsed_tool_calls else None,
        ))

        # If we had tool calls, we need to call LLM again to get final response
        if tool_calls:
            async for event in self._continue_with_tool_results(token, tools):
                yield event

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

        logger.debug(f"Calling LLM with {len(messages)} messages, {len(tools)} tools")
        return await litellm.acompletion(**kwargs)

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
            result = await tool_method(token, **tool_args)
            result_dict = result.to_dict()
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
    ) -> AsyncGenerator[ChatEvent, None]:
        """Continue conversation after tool execution.
        
        This calls the LLM again with tool results to get a final response.
        
        Args:
            token: Auth token
            tools: Tool definitions
            
        Yields:
            Additional chat events
        """
        system_prompt = SYSTEM_PROMPT.format(tool_descriptions=_build_tool_descriptions())
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

        if content:
            self.session.add_message(ChatMessage(role="assistant", content=content))
            yield ChatEvent(type=ChatEventType.TEXT, data={"content": content})

        # Handle any additional tool calls (recursive, but limited by LLM behavior)
        if assistant_message.tool_calls:
            # Process additional tool calls
            for tc in assistant_message.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                meta = self.tool_metadata.get(tool_name)
                if meta and meta["permission"] == ToolPermission.READ:
                    async for event in self._execute_tool(tc.id, tool_name, tool_args, token):
                        yield event

            # Continue again if there were tool calls
            async for event in self._continue_with_tool_results(token, tools):
                yield event
