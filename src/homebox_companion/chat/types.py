"""Shared types for the chat module.

This module contains the core data models used across the chat system:
- ToolCall: Represents a tool invocation from the LLM
- ChatMessage: A single message in the conversation

These are separated from session.py to enable cleaner imports and
avoid circular dependencies.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    """Represents a tool call from the LLM.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to call
        arguments: Tool arguments as a dictionary
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    """A single message in the conversation.

    Note: This model is intentionally mutable (not frozen) because tool messages
    may need to be updated after creation. When a write action requires approval,
    a placeholder message is created with "pending_approval" status. After the user
    approves, `ChatSession.update_tool_message()` updates the content in-place with
    the actual tool result. This avoids the complexity of replacing messages in the
    history list while maintaining correct tool_call_id references.

    Attributes:
        role: The role of the message sender
        content: The message content (mutable for tool result updates)
        tool_calls: List of tool calls (for assistant messages)
        tool_call_id: ID of the tool call this message responds to (for tool messages)
        timestamp: When the message was created. Used for debugging, session analytics,
            and potential future features (e.g., conversation export, message timing).
            Not sent to the LLM.
    """

    role: Literal["user", "assistant", "tool", "system"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation time for debugging and analytics; not sent to LLM",
    )

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to the format expected by LLM APIs."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        return msg

