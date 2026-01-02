"""Chat session and message management.

This module provides session state management for the conversational assistant,
including message history and pending approval tracking.

Uses Pydantic models for consistency with the Pydantic-first architecture.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from ..core.config import settings


class DisplayInfo(BaseModel):
    """Human-readable display info for approval actions."""

    model_config = ConfigDict(extra="allow")  # Allow additional fields

    item_name: str | None = None
    asset_id: str | None = None
    location: str | None = None


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

    Attributes:
        role: The role of the message sender
        content: The message content
        tool_calls: List of tool calls (for assistant messages)
        tool_call_id: ID of the tool call this message responds to (for tool messages)
        timestamp: When the message was created
    """

    role: Literal["user", "assistant", "tool", "system"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

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


class PendingApproval(BaseModel):
    """A pending action awaiting user approval.

    Attributes:
        id: Unique identifier for this approval request
        tool_name: Name of the tool to execute
        parameters: Tool parameters
        display_info: Human-readable details for display (e.g., item name, location)
        created_at: When the approval was created
        expires_at: When the approval expires
    """

    id: str
    tool_name: str
    parameters: dict[str, Any]
    display_info: DisplayInfo = Field(default_factory=DisplayInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def set_expiry(self) -> PendingApproval:
        """Set expiry time if not provided."""
        if self.expires_at is None:
            timeout_seconds = settings.chat_approval_timeout
            # Use object.__setattr__ since we need to set after validation
            object.__setattr__(
                self, "expires_at", self.created_at + timedelta(seconds=timeout_seconds)
            )
        return self

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if this approval has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "display_info": self.display_info.model_dump(exclude_none=True),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
        }


# Number of messages from the end of history before tool results are compressed
_TOOL_COMPRESSION_THRESHOLD = 6


class ChatSession:
    """Manages conversation state for a user session.

    This class tracks message history and pending approvals for a single
    conversation session. Sessions are identified by the user's auth token.

    Attributes:
        messages: List of messages in the conversation
        pending_approvals: Dict mapping approval ID to PendingApproval
    """

    def __init__(self):
        """Initialize an empty session."""
        self.messages: list[ChatMessage] = []
        self.pending_approvals: dict[str, PendingApproval] = {}
        self._created_at = datetime.now(UTC)

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation history.

        Args:
            message: The message to add
        """
        self.messages.append(message)
        logger.debug(f"Added {message.role} message, total: {len(self.messages)}")

        # TRACE: Log actual message content
        if message.role == "tool":
            # Tool results can be large, truncate for readability
            content_preview = (
                message.content[:500] + "..."
                if len(message.content) > 500
                else message.content
            )
            logger.trace(
                f"[SESSION] Tool result (call_id={message.tool_call_id}): {content_preview}"
            )
        elif message.role == "assistant" and message.tool_calls:
            # Assistant message with tool calls
            tool_names = [tc.name for tc in message.tool_calls]
            logger.trace(
                f"[SESSION] Assistant message with {len(message.tool_calls)} "
                f"tool calls: {tool_names}"
            )
            if message.content:
                logger.trace(f"[SESSION] Assistant message content: {message.content[:300]}...")
        else:
            # Regular user or assistant message
            content_preview = (
                message.content[:300] + "..."
                if len(message.content) > 300
                else message.content
            )
            logger.trace(f"[SESSION] {message.role} message: {content_preview}")

    def get_history(self, max_messages: int | None = None) -> list[dict[str, Any]]:
        """Get conversation history in LLM format with structure-aware truncation.

        Ensures that 'tool' messages are always preceded by their 'assistant' calls,
        preventing API errors from orphaned tool results during truncation.

        Args:
            max_messages: Maximum number of messages to return.
                         If None, uses settings.chat_max_history.

        Returns:
            List of message dicts in LLM API format
        """
        limit = max_messages or settings.chat_max_history
        if not limit or len(self.messages) <= limit:
            recent_messages = self.messages
        else:
            # Initial slice point
            start_idx = len(self.messages) - limit

            # If we start with a 'tool' message, we MUST move back to find its
            # parent assistant call. The parent must be an assistant message
            # WITH tool_calls that contains this tool's tool_call_id.
            while start_idx > 0:
                msg = self.messages[start_idx]
                if msg.role != "tool":
                    # Found a non-tool message. Verify it's a valid starting point.
                    # If it's an assistant WITH tool_calls, check if the next message
                    # is a tool result for this call - if so, we're good.
                    # If it's user or plain assistant, we're also good.
                    break
                start_idx -= 1

            # Final safety: if start_idx lands on a user message but the next
            # message is a tool result (which would be orphaned), keep moving back.
            # This handles edge cases where tool results follow user messages due
            # to session corruption or manual edits.
            if start_idx < len(self.messages) - 1:
                next_msg = self.messages[start_idx + 1]
                if next_msg.role == "tool":
                    # The next message is a tool result, but we're on a non-assistant
                    # or an assistant without tool_calls. Keep going back.
                    while start_idx > 0:
                        candidate = self.messages[start_idx]
                        if candidate.role == "assistant" and candidate.tool_calls:
                            break
                        start_idx -= 1

            recent_messages = self.messages[start_idx:]

        result = []
        for i, msg in enumerate(recent_messages):
            formatted = msg.to_llm_format()

            # Compress tool results older than threshold
            messages_from_end = len(recent_messages) - i
            if msg.role == "tool" and messages_from_end > _TOOL_COMPRESSION_THRESHOLD:
                formatted["content"] = self._compress_tool_result(formatted["content"])

            result.append(formatted)
        return result

    def _compress_tool_result(self, content: str) -> str:
        """Compress a tool result to a summary for older messages.

        Args:
            content: The JSON-encoded tool result content

        Returns:
            Compressed summary string
        """
        try:
            data = json.loads(content)
            if data.get("success"):
                result_data = data.get("data")
                if isinstance(result_data, list):
                    return json.dumps(
                        {"success": True, "_summary": f"{len(result_data)} items returned"}
                    )
                elif isinstance(result_data, dict):
                    # For single items, just note it was retrieved
                    name = result_data.get("name", "item")
                    return json.dumps({"success": True, "_summary": f"Retrieved: {name}"})
            return content[:200] + "..." if len(content) > 200 else content
        except (json.JSONDecodeError, TypeError):
            return content[:200] + "..." if len(content) > 200 else content

    def add_pending_approval(self, approval: PendingApproval) -> None:
        """Add a pending approval request.

        Args:
            approval: The approval to add
        """
        self.pending_approvals[approval.id] = approval
        logger.info(f"Added pending approval {approval.id} for tool {approval.tool_name}")

    def get_pending_approval(self, approval_id: str) -> PendingApproval | None:
        """Get a pending approval by ID.

        Args:
            approval_id: The approval ID to look up

        Returns:
            The PendingApproval or None if not found
        """
        approval = self.pending_approvals.get(approval_id)
        if approval and approval.is_expired:
            logger.debug(f"Approval {approval_id} is expired, removing")
            del self.pending_approvals[approval_id]
            return None
        return approval

    def remove_approval(self, approval_id: str) -> bool:
        """Remove an approval (after execution or rejection).

        Args:
            approval_id: The approval ID to remove

        Returns:
            True if removed, False if not found
        """
        if approval_id in self.pending_approvals:
            del self.pending_approvals[approval_id]
            logger.debug(f"Removed approval {approval_id}")
            return True
        return False

    def update_tool_message(self, tool_call_id: str, new_content: str) -> bool:
        """Update a tool message's content by tool_call_id.

        This is used to replace placeholder "pending_approval" messages with
        actual tool results after user approves an action.

        Args:
            tool_call_id: The tool_call_id to find and update
            new_content: The new content to set

        Returns:
            True if message was found and updated, False otherwise
        """
        for msg in self.messages:
            if msg.role == "tool" and msg.tool_call_id == tool_call_id:
                msg.content = new_content
                logger.debug(f"Updated tool message for tool_call_id={tool_call_id}")
                return True
        logger.debug(f"Tool message not found for tool_call_id={tool_call_id}")
        return False

    def get_tool_call_id_for_approval(self, approval_id: str) -> str | None:
        """Find the tool_call_id associated with a pending approval.

        Searches backwards through messages to find the tool message that
        contains the pending_approval response for this approval_id.

        Args:
            approval_id: The approval ID to search for

        Returns:
            The tool_call_id or None if not found
        """
        for msg in reversed(self.messages):
            if msg.role == "tool" and msg.tool_call_id:
                try:
                    content = json.loads(msg.content)
                    if content.get("approval_id") == approval_id:
                        return msg.tool_call_id
                except (json.JSONDecodeError, TypeError):
                    continue
        return None

    def list_pending_approvals(self) -> list[PendingApproval]:
        """List all non-expired pending approvals.

        Returns:
            List of valid PendingApproval objects
        """
        self.cleanup_expired()
        return list(self.pending_approvals.values())

    def cleanup_expired(self) -> int:
        """Remove all expired approvals.

        Returns:
            Number of approvals removed
        """
        expired_ids = [
            aid for aid, approval in self.pending_approvals.items()
            if approval.is_expired
        ]
        for aid in expired_ids:
            del self.pending_approvals[aid]

        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired approvals")

        return len(expired_ids)

    def clear(self) -> None:
        """Clear all messages and pending approvals."""
        self.messages.clear()
        self.pending_approvals.clear()
        logger.info("Cleared chat session")


# Session storage - in-memory for now, keyed by token hash
# In production, consider using Redis or database storage
_sessions: dict[str, ChatSession] = {}


def get_session(token: str) -> ChatSession:
    """Get or create a session for the given token.

    Args:
        token: The user's auth token (used as session key)

    Returns:
        The ChatSession for this user
    """
    # Use a deterministic hash of the token for session key
    # This ensures consistency across restarts (required for future persistence)
    session_key = hashlib.sha256(token.encode()).hexdigest()[:16]

    if session_key not in _sessions:
        _sessions[session_key] = ChatSession()
        logger.debug(f"Created new session for key {session_key[:8]}...")

    return _sessions[session_key]


def clear_session(token: str) -> bool:
    """Clear and remove a session.

    Args:
        token: The user's auth token

    Returns:
        True if session existed and was removed
    """
    session_key = hashlib.sha256(token.encode()).hexdigest()[:16]
    if session_key in _sessions:
        del _sessions[session_key]
        logger.info(f"Deleted session for key {session_key[:8]}...")
        return True
    return False


def create_approval_id() -> str:
    """Generate a unique approval ID."""
    return str(uuid.uuid4())
