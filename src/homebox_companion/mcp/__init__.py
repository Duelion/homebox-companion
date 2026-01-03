"""MCP server for Homebox Companion.

This module provides an MCP (Model Context Protocol) server that exposes
Homebox operations as tools for LLM-based assistants. The server can be
used with external MCP hosts like Claude Desktop.

Tools are classified as:
- Read-only: Auto-execute without approval (list_*, get_*)
- Write: Require explicit user approval (create_*, update_*, delete_*)

Tools are registered using the @register_tool decorator.
"""

from .executor import ToolExecutor
from .server import create_mcp_server
from .tools import clear_tool_registry, get_tools, register_tool
from .types import DisplayInfo, ToolPermission, ToolResult

__all__ = [
    "ToolExecutor",
    "create_mcp_server",
    "get_tools",
    "register_tool",
    "clear_tool_registry",
    "ToolPermission",
    "ToolResult",
    "DisplayInfo",
]
