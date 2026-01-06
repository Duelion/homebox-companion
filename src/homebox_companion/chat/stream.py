"""SSE event generation for chat streaming.

This module provides event types and a factory for generating
Server-Sent Events (SSE) for the chat streaming response.

The StreamEmitter provides a clean API for creating typed events,
while ChatEvent and ChatEventType define the event structure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..mcp.types import DisplayInfo
    from .llm_client import TokenUsage
    from .session import PendingApproval


class ChatEventType(str, Enum):
    """Types of streaming events sent to the frontend."""

    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"
    USAGE = "usage"
    DONE = "done"


@dataclass
class ChatEvent:
    """A streaming event from the chat orchestrator.

    Attributes:
        type: The event type (determines how frontend handles it)
        data: Event data payload (structure varies by type)
    """

    type: ChatEventType
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Convert to SSE wire format.

        Returns:
            String in SSE format: "event: {type}\\ndata: {json}\\n\\n"
        """
        return f"event: {self.type.value}\ndata: {json.dumps(self.data)}\n\n"


class StreamEmitter:
    """Factory for creating typed SSE events.

    This class provides a clean API for generating SSE events,
    ensuring consistent structure and reducing boilerplate in
    the orchestrator.

    Example:
        >>> emitter = StreamEmitter()
        >>> event = emitter.text("Hello, world!")
        >>> yield event
    """

    def text(self, content: str) -> ChatEvent:
        """Create a text chunk event.

        Args:
            content: The text content to stream.

        Returns:
            ChatEvent with TEXT type.
        """
        return ChatEvent(type=ChatEventType.TEXT, data={"content": content})

    def tool_start(
        self, tool_name: str, params: dict[str, Any], execution_id: str
    ) -> ChatEvent:
        """Create a tool execution started event.

        Args:
            tool_name: Name of the tool being executed.
            params: Tool parameters.
            execution_id: Unique ID to correlate with tool_result.

        Returns:
            ChatEvent with TOOL_START type.
        """
        return ChatEvent(
            type=ChatEventType.TOOL_START,
            data={"tool": tool_name, "params": params, "execution_id": execution_id},
        )

    def tool_result(
        self,
        tool_name: str,
        result: dict[str, Any],
        execution_id: str,
    ) -> ChatEvent:
        """Create a tool result event.

        Args:
            tool_name: Name of the tool that completed.
            result: Tool result as a dict (typically from ToolResult.to_dict()).
            execution_id: Unique ID to correlate with tool_start.

        Returns:
            ChatEvent with TOOL_RESULT type.
        """
        return ChatEvent(
            type=ChatEventType.TOOL_RESULT,
            data={"tool": tool_name, "result": result, "execution_id": execution_id},
        )

    def approval_required(self, approval: PendingApproval) -> ChatEvent:
        """Create an approval required event.

        Args:
            approval: The pending approval requiring user action.

        Returns:
            ChatEvent with APPROVAL_REQUIRED type.
        """
        return ChatEvent(
            type=ChatEventType.APPROVAL_REQUIRED,
            data={
                "id": approval.id,
                "tool": approval.tool_name,
                "params": approval.parameters,
                "display_info": approval.display_info.model_dump(exclude_none=True),
                "expires_at": (
                    approval.expires_at.isoformat() if approval.expires_at else None
                ),
            },
        )

    def usage(self, token_usage: TokenUsage) -> ChatEvent:
        """Create a token usage event.

        Args:
            token_usage: Token usage statistics from the LLM.

        Returns:
            ChatEvent with USAGE type.
        """
        return ChatEvent(
            type=ChatEventType.USAGE,
            data={
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            },
        )

    def error(self, message: str) -> ChatEvent:
        """Create an error event.

        Args:
            message: Error message to display.

        Returns:
            ChatEvent with ERROR type.
        """
        return ChatEvent(type=ChatEventType.ERROR, data={"message": message})

    def done(self) -> ChatEvent:
        """Create a stream completion event.

        Returns:
            ChatEvent with DONE type.
        """
        return ChatEvent(type=ChatEventType.DONE, data={})

    @staticmethod
    def confirmation_message(
        tool_name: str,
        success: bool,
        data: Any,
        error: str | None = None,
        display_info: DisplayInfo | None = None,
    ) -> str:
        """Generate a brief confirmation message after tool execution.

        Uses simple template-based messages instead of LLM calls to avoid
        latency and token costs for simple confirmations.

        Args:
            tool_name: Name of the tool that was executed
            success: Whether the execution was successful
            data: Result data from the tool execution
            error: Error message if execution failed
            display_info: Optional DisplayInfo with item name (for delete/update tools)

        Returns:
            Brief confirmation message with ✓ or ✗ prefix (styled by frontend)
        """
        if not success:
            # Cross for failure - frontend styles based on ✗ prefix
            return f"✗ {tool_name} failed: {error or 'Unknown error'}"

        # Build a human-readable summary
        # Priority: display_info.target_name > display_info.item_name > data extraction
        summary = ""

        # First try display_info (has target_name for all entity types, item_name for backward compat)
        if display_info and (display_info.target_name or display_info.item_name):
            entity_name = display_info.target_name or display_info.item_name
            summary = entity_name
        else:
            # Fall back to extracting from data (for backward compatibility)
            try:
                if isinstance(data, dict):
                    # Common patterns for our tools
                    if "name" in data:
                        summary = data['name']
                    elif "id" in data:
                        id_str = str(data.get("id", ""))
                        if len(id_str) > 8:
                            summary = f"(ID: {id_str[:8]}...)"
                        else:
                            summary = f"(ID: {id_str})"
                elif isinstance(data, list):
                    count = len(data)
                    summary = f"{count} item{'s' if count != 1 else ''}"
                elif data is not None:
                    summary = str(data)[:50]
            except Exception:
                # If anything goes wrong parsing data, just skip the summary
                pass

        # Check for success - frontend styles based on ✓ prefix
        if summary:
            return f"✓ {tool_name}: {summary}"
        else:
            return f"✓ {tool_name}"
