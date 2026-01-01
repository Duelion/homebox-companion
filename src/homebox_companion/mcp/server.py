"""MCP server definition for Homebox Companion.

This module creates and configures the MCP server that exposes Homebox
operations to external MCP hosts like Claude Desktop.

The server uses the Anthropic MCP SDK for protocol handling and discovers
tools dynamically from the tools module.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import ValidationError

from ..core.config import settings
from ..homebox.client import HomeboxClient
from .tools import get_tools
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

    # Discover and instantiate all tools at server creation
    all_tools = get_tools()
    tools_by_name = {t.name: t for t in all_tools}

    logger.info(f"MCP server initialized with {len(all_tools)} tools")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        if not settings.chat_enabled:
            logger.info("Chat/MCP is disabled, returning empty tool list")
            return []

        result = []
        for tool in all_tools:
            # Only expose read-only tools for now (Phase A)
            # Write tools will be added in Phase D with approval workflow
            if tool.permission != ToolPermission.READ:
                continue

            result.append(
                Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.Params.model_json_schema(),
                )
            )

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

        # Get tool by name
        tool = tools_by_name.get(name)
        if not tool:
            return _error_response(f"Unknown tool: {name}")

        # For now, only allow read-only tools (Phase A)
        # Write tools will require approval workflow (Phase D)
        if tool.permission != ToolPermission.READ:
            return _error_response(
                "Write operations require approval (not yet implemented)"
            )

        # Validate arguments with Pydantic
        try:
            params = tool.Params(**tool_arguments)
        except ValidationError as e:
            return _error_response(f"Invalid parameters: {e}")

        # Execute the tool
        logger.info(f"Executing tool: {name}")
        try:
            result = await tool.execute(client, token, params)
            return [TextContent(type="text", text=json.dumps(result.to_dict()))]
        except Exception as e:
            logger.exception(f"Tool execution failed: {name}")
            return _error_response(str(e))

    return server


async def run_stdio_server() -> None:
    """Run the MCP server using stdio transport.

    This is the entry point for external MCP hosts like Claude Desktop
    that communicate via stdin/stdout.
    """
    client = HomeboxClient()
    server = create_mcp_server(client)

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        await client.aclose()
