"""MCP Protocol adapter - wraps ToolExecutor for external clients.

Uses the low-level mcp.server.lowlevel.Server to:
1. Expose inputSchema directly from Pydantic models
2. Delegate execution to ToolExecutor
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from mcp import types
from mcp.server.lowlevel import Server

from homebox_companion import settings
from homebox_companion.homebox.client import HomeboxClient
from homebox_companion.mcp import ToolExecutor

# Create low-level MCP server
mcp_server = Server("homebox-companion")


def _get_executor() -> ToolExecutor:
    """Create a ToolExecutor instance for MCP operations."""
    return ToolExecutor(HomeboxClient(settings.api_url))


@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools with inputSchema from Pydantic models."""
    executor = _get_executor()
    tools = executor.list_tools()
    logger.debug(f"MCP list_tools: returning {len(tools)} tools")
    return [
        types.Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.Params.model_json_schema(),
        )
        for tool in tools
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    """Execute a tool and return results."""
    executor = _get_executor()
    token = settings.mcp_token

    # MCP SDK passes None when no arguments are provided
    args = arguments or {}

    if not token:
        logger.warning("MCP call_tool failed: HBC_MCP_TOKEN not configured")
        return [types.TextContent(type="text", text="Error: HBC_MCP_TOKEN not configured")]

    logger.info(f"MCP call_tool: executing {name}")
    result = await executor.execute(name, args, token)

    # Return as JSON text content
    return [types.TextContent(type="text", text=json.dumps(result.to_dict()))]
