"""Chat orchestration for conversational assistant.

This module provides the orchestration layer for the conversational assistant,
managing LLM interactions, tool calling, and session state.

Key components:
- ChatOrchestrator: Thin facade coordinating the chat flow
- ChatSession: Pure state management for conversations and approvals
- ApprovalService: Approval execution lifecycle
- SessionStoreProtocol/MemorySessionStore: Pluggable session storage
- LLMClient: LiteLLM communication wrapper
- StreamEmitter: SSE event generation
"""

from .approvals import ApprovalService
from .llm_client import LLMClient, TokenUsage
from .orchestrator import ChatOrchestrator
from .session import ApprovalOutcome, ChatSession, PendingApproval
from .store import MemorySessionStore, SessionStoreProtocol
from .stream import ChatEvent, ChatEventType, StreamEmitter
from .types import ChatMessage, ToolCall

__all__ = [
    # Orchestration
    "ChatOrchestrator",
    "ApprovalService",
    # State management
    "ChatSession",
    "ChatMessage",
    "ToolCall",
    "PendingApproval",
    "ApprovalOutcome",
    # Storage
    "SessionStoreProtocol",
    "MemorySessionStore",
    # LLM communication
    "LLMClient",
    "TokenUsage",
    # Events
    "ChatEvent",
    "ChatEventType",
    "StreamEmitter",
]
