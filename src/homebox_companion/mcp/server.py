"""MCP server definition for Homebox Companion.

This module creates and configures the MCP server that exposes Homebox
operations to external MCP hosts like Claude Desktop.

The server uses the Anthropic MCP SDK for protocol handling and registers
all available tools from HomeboxMCPTools.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ..core.config import settings
from ..homebox.client import HomeboxClient
from .tools import HomeboxMCPTools, ToolPermission


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
    
    tools = HomeboxMCPTools(client)
    tool_metadata = HomeboxMCPTools.get_tool_metadata()
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        if not settings.chat_enabled:
            logger.info("Chat/MCP is disabled, returning empty tool list")
            return []
        
        result = []
        for name, meta in tool_metadata.items():
            # Only expose read-only tools for now (Phase A)
            # Write tools will be added in Phase D with approval workflow
            if meta["permission"] != ToolPermission.READ:
                continue
                
            result.append(
                Tool(
                    name=name,
                    description=meta["description"],
                    inputSchema=meta["parameters"],
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
            return [TextContent(
                type="text",
                text='{"success": false, "error": "Chat/MCP feature is disabled"}'
            )]
        
        # Extract token from arguments
        token = arguments.pop("token", None)
        if not token:
            return [TextContent(
                type="text",
                text='{"success": false, "error": "Missing required token parameter"}'
            )]
        
        # Get tool metadata to check permissions
        meta = tool_metadata.get(name)
        if not meta:
            return [TextContent(
                type="text",
                text=f'{{"success": false, "error": "Unknown tool: {name}"}}'
            )]
        
        # For now, only allow read-only tools (Phase A)
        # Write tools will require approval workflow (Phase D)
        if meta["permission"] != ToolPermission.READ:
            return [TextContent(
                type="text",
                text='{"success": false, "error": "Write operations require approval (not yet implemented)"}'
            )]
        
        # Dispatch to the appropriate tool method
        tool_method = getattr(tools, name, None)
        if not tool_method:
            return [TextContent(
                type="text",
                text=f'{{"success": false, "error": "Tool not implemented: {name}"}}'
            )]
        
        logger.info(f"Executing tool: {name}")
        try:
            result = await tool_method(token, **arguments)
            import json
            return [TextContent(
                type="text",
                text=json.dumps(result.to_dict())
            )]
        except Exception as e:
            logger.exception(f"Tool execution failed: {name}")
            return [TextContent(
                type="text",
                text=f'{{"success": false, "error": "{str(e)}"}}'
            )]

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
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await client.aclose()
