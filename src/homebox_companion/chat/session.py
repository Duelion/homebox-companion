"""Chat session and message management.

This module provides session state management for the conversational assistant,
including message history and pending approval tracking.

The ChatSession is the single source of truth for conversation state:
- Message history (with structure-aware truncation)
- Pending approval lifecycle (create, reject)
- Tool message updates

For session storage, see the store module which provides the
SessionStoreProtocol and MemorySessionStore implementation.

Uses Pydantic models for consistency with the Pydantic-first architecture.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, Field, computed_field

from ..core.config import settings
from ..mcp.types import DisplayInfo
from .types import ChatMessage

ApprovalOutcomeType = Literal["approved", "rejected", "auto_rejected"]


class ApprovalOutcome(BaseModel):
    """Records the outcome of an approval action.

    Used to communicate approval results to the AI in subsequent messages.

    Attributes:
        tool_name: Name of the tool that was approved/rejected
        outcome: The result - 'approved', 'rejected', or 'auto_rejected'
        success: For approved actions, whether execution succeeded
        item_name: Optional display name for the item affected
    """

    tool_name: str
    outcome: ApprovalOutcomeType
    success: bool | None = None  # Only for approved actions
    item_name: str | None = None


def _compute_default_expiry() -> datetime:
    """Compute default expiry based on settings."""
    timeout_seconds = settings.chat_approval_timeout
    return datetime.now(UTC) + timedelta(seconds=timeout_seconds)


class PendingApproval(BaseModel):
    """A pending action awaiting user approval.

    Attributes:
        id: Unique identifier for this approval request
        tool_name: Name of the tool to execute
        parameters: Tool parameters
        tool_call_id: The tool_call_id from the assistant message (for history updates)
        display_info: Human-readable details for display (e.g., item name, location)
        created_at: When the approval was created
        expires_at: When the approval expires
    """

    id: str
    tool_name: str
    parameters: dict[str, Any]
    tool_call_id: str | None = None  # Links to the tool message in history
    display_info: DisplayInfo = Field(default_factory=DisplayInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=_compute_default_expiry)

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if this approval has expired."""
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses.

        Uses Pydantic's model_dump with custom serialization for datetime fields.
        """
        data = self.model_dump(
            include={"id", "tool_name", "parameters", "display_info", "created_at", "expires_at", "is_expired"},
            exclude_none=True,
        )
        # Serialize datetimes to ISO format and exclude None values from display_info
        data["created_at"] = self.created_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        data["display_info"] = self.display_info.model_dump(exclude_none=True)
        return data


# Number of messages from the end of history before tool results are compressed
_TOOL_COMPRESSION_THRESHOLD = 6


class ChatSession:
    """Manages conversation state for a user session.

    This class tracks message history and pending approvals for a single
    conversation session. Sessions are identified by the user's auth token.

    Attributes:
        session_id: Unique identifier for this session instance (for frontend sync)
        messages: List of messages in the conversation
        pending_approvals: Dict mapping approval ID to PendingApproval
    """

    def __init__(self):
        """Initialize an empty session."""
        # Unique session ID for frontend synchronization
        # Used to detect when backend session was reset (server restart, TTL expiry)
        self.session_id: str = uuid.uuid4().hex[:12]
        self.messages: list[ChatMessage] = []
        self.pending_approvals: dict[str, PendingApproval] = {}
        self._created_at = datetime.now(UTC)
        # Index for O(1) lookup of tool messages by tool_call_id
        self._tool_message_index: dict[str, ChatMessage] = {}
        # Track recent auto-rejections for context injection
        self._recent_auto_rejections: list[ApprovalOutcome] = []

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation history.

        Args:
            message: The message to add
        """
        self.messages.append(message)

        # Maintain tool message index for O(1) lookup
        if message.role == "tool" and message.tool_call_id:
            self._tool_message_index[message.tool_call_id] = message

        logger.trace(f"Added {message.role} message, total: {len(self.messages)}")

        # TRACE: Log actual message content
        if message.role == "tool":
            # Tool results can be large, truncate for readability
            content_preview = message.content[:500] + "..." if len(message.content) > 500 else message.content
            logger.trace(f"[SESSION] Tool result (call_id={message.tool_call_id}): {content_preview}")
        elif message.role == "assistant" and message.tool_calls:
            # Assistant message with tool calls
            tool_names = [tc.name for tc in message.tool_calls]
            logger.trace(f"[SESSION] Assistant message with {len(message.tool_calls)} tool calls: {tool_names}")
            if message.content:
                logger.trace(f"[SESSION] Assistant message content: {message.content[:300]}...")
        else:
            # Regular user or assistant message
            content_preview = message.content[:300] + "..." if len(message.content) > 300 else message.content
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
                    return json.dumps({"success": True, "_summary": f"{len(result_data)} items returned"})
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

        Uses an internal index for O(1) lookup instead of iterating messages.

        Args:
            tool_call_id: The tool_call_id to find and update
            new_content: The new content to set

        Returns:
            True if message was found and updated, False otherwise
        """
        msg = self._tool_message_index.get(tool_call_id)
        if msg:
            msg.content = new_content
            logger.debug(f"Updated tool message for tool_call_id={tool_call_id}")
            return True
        logger.debug(f"Tool message not found for tool_call_id={tool_call_id}")
        return False

    def get_tool_call_id_for_approval(self, approval_id: str) -> str | None:
        """Find the tool_call_id associated with a pending approval.

        Uses the tool_call_id stored in the PendingApproval object.

        Args:
            approval_id: The approval ID to look up

        Returns:
            The tool_call_id or None if not found
        """
        approval = self.pending_approvals.get(approval_id)
        if approval:
            return approval.tool_call_id
        return None

    def list_pending_approvals(self) -> list[PendingApproval]:
        """List all non-expired pending approvals.

        Returns:
            List of valid PendingApproval objects
        """
        self.cleanup_expired()
        return list(self.pending_approvals.values())

    def cleanup_expired(self) -> int:
        """Auto-reject all expired approvals, updating history.

        Returns:
            Number of approvals rejected
        """
        expired = [approval for approval in self.pending_approvals.values() if approval.is_expired]
        if expired:
            return self._auto_reject_approvals(expired, "approval expired")
        return 0

    def auto_reject_all_pending(self, reason: str = "superseded by new message") -> int:
        """Auto-reject all pending approvals, updating history to show rejection.

        Called when user sends a new message, which supersedes any pending approvals.
        Records the rejections for context injection in the next LLM call.

        Args:
            reason: Reason for rejection shown in history

        Returns:
            Number of approvals rejected
        """
        if not self.pending_approvals:
            return 0

        # Capture the approvals before they're removed
        approvals_to_reject = list(self.pending_approvals.values())

        # Record these as auto-rejections for context injection
        for approval in approvals_to_reject:
            self._recent_auto_rejections.append(
                ApprovalOutcome(
                    tool_name=approval.tool_name,
                    outcome="auto_rejected",
                    item_name=approval.display_info.item_name if approval.display_info else None,
                )
            )

        return self._auto_reject_approvals(approvals_to_reject, reason)

    def consume_auto_rejections(self) -> list[ApprovalOutcome]:
        """Get and clear the list of recent auto-rejections.

        Used by the orchestrator to build context for the LLM about
        actions that were dismissed when the user sent a new message.

        Returns:
            List of ApprovalOutcome objects representing auto-rejected actions
        """
        rejections = self._recent_auto_rejections
        self._recent_auto_rejections = []
        return rejections

    def reject_approval(self, approval_id: str, reason: str) -> bool:
        """Reject a single approval and update history to show rejection.

        This is the preferred method for rejecting approvals as it handles both
        updating the tool message in history and removing from pending.

        Args:
            approval_id: ID of the approval to reject
            reason: Reason for rejection shown in history

        Returns:
            True if approval was found and rejected, False otherwise
        """
        approval = self.pending_approvals.get(approval_id)
        if not approval:
            return False

        # Update the tool message in history to show rejection
        tool_call_id = self.get_tool_call_id_for_approval(approval_id)
        if tool_call_id:
            rejection_message = json.dumps(
                {
                    "success": False,
                    "rejected": True,
                    "reason": reason,
                    "message": f"Action '{approval.tool_name}' was rejected: {reason}",
                }
            )
            self.update_tool_message(tool_call_id, rejection_message)

        del self.pending_approvals[approval_id]
        logger.info(f"Rejected approval {approval_id} for tool {approval.tool_name}: {reason}")
        return True

    def _auto_reject_approvals(self, approvals: list[PendingApproval], reason: str) -> int:
        """Internal method to reject a list of approvals and update history.

        Args:
            approvals: List of approvals to reject
            reason: Reason for rejection

        Returns:
            Number of approvals rejected
        """
        rejected_count = 0
        for approval in approvals:
            if self.reject_approval(approval.id, f"automatically rejected: {reason}"):
                rejected_count += 1

        if rejected_count:
            logger.debug(f"Auto-rejected {rejected_count} pending approvals: {reason}")

        return rejected_count

    def clear(self) -> None:
        """Clear all messages, pending approvals, and indexes."""
        self.messages.clear()
        self.pending_approvals.clear()
        self._tool_message_index.clear()
        self._recent_auto_rejections.clear()
        logger.info("Cleared chat session")


def create_approval_id() -> str:
    """Generate a unique approval ID."""
    return str(uuid.uuid4())
