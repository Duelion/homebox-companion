"""MCP server for Homebox Companion.

This module provides an MCP (Model Context Protocol) server that exposes
Homebox operations as tools for LLM-based assistants. The server can be
used with external MCP hosts like Claude Desktop.

Tools are classified as:
- Read-only: Auto-execute without approval (list_*, get_*)
- Write: Require explicit user approval (create_*, update_*, delete_*)
"""

from .server import create_mcp_server
from .tools import HomeboxMCPTools, ToolPermission

__all__ = ["create_mcp_server", "HomeboxMCPTools", "ToolPermission"]
