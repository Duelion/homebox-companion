"""FastAPI router for MCP protocol endpoint.

This module provides HTTP endpoints for the MCP protocol, allowing
external MCP hosts to communicate with the Homebox MCP server over HTTP.

The main endpoint at /mcp/v1/ handles MCP protocol requests using
Server-Sent Events (SSE) for streaming responses.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from homebox_companion import HomeboxClient, settings

from ..dependencies import get_client
from homebox_companion.mcp.server import create_mcp_server
from homebox_companion.mcp.tools import HomeboxMCPTools

router = APIRouter()


@router.get("/mcp/v1/tools")
async def list_mcp_tools() -> JSONResponse:
    """List available MCP tools and their schemas.
    
    This endpoint is primarily for discovery and debugging.
    External MCP hosts typically use the MCP protocol directly.
    
    Returns:
        JSON object with tool names and their metadata
    """
    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "Chat/MCP feature is disabled"}
        )
    
    metadata = HomeboxMCPTools.get_tool_metadata()
    # Filter to only read-only tools for Phase A
    read_only_tools = {
        name: {
            "description": meta["description"],
            "parameters": meta["parameters"],
        }
        for name, meta in metadata.items()
        if meta["permission"].value == "read"
    }
    
    return JSONResponse(content={"tools": read_only_tools})


@router.post("/mcp/v1/tools/{tool_name}")
async def execute_mcp_tool(
    tool_name: str,
    request: Request,
    client: HomeboxClient = Depends(get_client),
) -> JSONResponse:
    """Execute an MCP tool directly via HTTP.
    
    This is a convenience endpoint for testing and simple integrations.
    For full MCP protocol support with streaming, external hosts should
    use the stdio transport or connect via SSE.
    
    Args:
        tool_name: Name of the tool to execute
        request: FastAPI request containing JSON body with:
            - token: Homebox auth token (required)
            - Additional tool-specific parameters
    
    Returns:
        JSON response with tool execution result
    """
    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "Chat/MCP feature is disabled"}
        )
    
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON body"}
        )
    
    token = body.pop("token", None)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Missing required token parameter"}
        )
    
    # Get tool metadata
    metadata = HomeboxMCPTools.get_tool_metadata()
    tool_meta = metadata.get(tool_name)
    
    if not tool_meta:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Unknown tool: {tool_name}"}
        )
    
    # Only allow read-only tools for Phase A
    if tool_meta["permission"].value != "read":
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Write operations require approval (not yet implemented)"}
        )
    
    # Execute the tool
    tools = HomeboxMCPTools(client)
    tool_method = getattr(tools, tool_name, None)
    
    if not tool_method:
        return JSONResponse(
            status_code=501,
            content={"success": False, "error": f"Tool not implemented: {tool_name}"}
        )
    
    logger.info(f"Executing MCP tool via HTTP: {tool_name}")
    try:
        result = await tool_method(token, **body)
        return JSONResponse(content=result.to_dict())
    except Exception as e:
        logger.exception(f"MCP tool execution failed: {tool_name}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/mcp/v1/health")
async def mcp_health() -> dict[str, Any]:
    """Health check for MCP server.
    
    Returns:
        Status information about the MCP server
    """
    return {
        "status": "healthy" if settings.chat_enabled else "disabled",
        "chat_enabled": settings.chat_enabled,
        "version": "1.0.0",
    }
