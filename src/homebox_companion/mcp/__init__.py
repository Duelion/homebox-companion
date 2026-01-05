"""MCP tools and executor for Homebox Companion.

This module provides tool discovery and execution services for the chat
orchestrator and HTTP-based MCP endpoints. Tools are exposed via the
ToolExecutor service.

Tools are classified as:
- Read-only: Auto-execute without approval (list_*, get_*)
- Write: Require explicit user approval (create_*, update_*, delete_*)

Tools are registered using the @register_tool decorator.
"""

from .executor import ToolExecutor
from .tools import get_tools, register_tool
from .types import DisplayInfo, ToolPermission, ToolResult

__all__ = [
    "ToolExecutor",
    "get_tools",
    "register_tool",
    "ToolPermission",
    "ToolResult",
    "DisplayInfo",
]

