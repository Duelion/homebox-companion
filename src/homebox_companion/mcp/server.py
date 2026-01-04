"""MCP server definition for Homebox Companion.

This module creates and configures the MCP server that exposes Homebox
operations to external MCP hosts like Claude Desktop.

The server uses the Anthropic MCP SDK for protocol handling and the
ToolExecutor service for tool discovery and execution.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from mcp.server import Server
from mcp.types import TextContent, Tool

from ..core.config import settings
from ..homebox.client import HomeboxClient
from .executor import ToolExecutor
from .types import ToolPermission


def _error_response(msg: str) -> list[TextContent]:
    """Create a standardized error response."""
    return [TextContent(type="text", text=json.dumps({"success": False, "error": msg}))]


def create_mcp_server(client: HomeboxClient | None = None) -> Server:
    """Create and configure the MCP server with Homebox tools.

    Args:
        client: Optional HomeboxClient instance. If not provided, creates
               a new client using default settings.

    Returns:
        Configured MCP Server instance ready to handle requests.
    """
    server = Server("homebox-companion")

    # Create client if not provided
    if client is None:
        client = HomeboxClient()

    # Create ToolExecutor for centralized tool handling
    executor = ToolExecutor(client)

    logger.info(f"MCP server initialized with {len(executor.list_tools())} tools")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        if not settings.chat_enabled:
            logger.debug("Chat/MCP is disabled, returning empty tool list")
            return []

        # Get schemas with token parameter included for MCP protocol
        # Only expose read-only tools (write tools require approval via chat)
        schemas = executor.get_tool_schemas(include_write=False, include_token=True)

        result = [
            Tool(
                name=schema["function"]["name"],
                description=schema["function"]["description"],
                inputSchema=schema["function"]["parameters"],
            )
            for schema in schemas
        ]

        logger.debug(f"Returning {len(result)} tools")
        return result

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a tool and return the result.

        Args:
            name: Name of the tool to call
            arguments: Tool arguments including 'token' for authentication

        Returns:
            List containing a single TextContent with the JSON result
        """
        if not settings.chat_enabled:
            return _error_response("Chat/MCP feature is disabled")

        # Extract token from arguments (without mutating the input dict)
        token = arguments.get("token")
        if not token:
            return _error_response("Missing required token parameter")

        # Filter out token for parameter validation
        tool_arguments = {k: v for k, v in arguments.items() if k != "token"}

        # Check tool exists
        tool = executor.get_tool(name)
        if not tool:
            return _error_response(f"Unknown tool: {name}")

        # Only allow read-only tools (write tools require approval via chat)
        if tool.permission != ToolPermission.READ:
            return _error_response(
                "Write operations require approval via the chat interface"
            )

        # Execute via ToolExecutor
        logger.debug(f"Executing tool: {name}")
        result = await executor.execute(name, tool_arguments, token)
        return [TextContent(type="text", text=json.dumps(result.to_dict()))]

    return server
