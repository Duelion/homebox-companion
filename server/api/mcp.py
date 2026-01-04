"""FastAPI router for MCP protocol endpoint.

This module provides HTTP endpoints for the MCP protocol, allowing
external MCP hosts to communicate with the Homebox MCP server over HTTP.

Uses the ToolExecutor service for centralized tool execution.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from homebox_companion import settings
from homebox_companion.mcp.executor import ToolExecutor
from homebox_companion.mcp.types import ToolPermission

from ..dependencies import get_executor

router = APIRouter()


@router.get("/mcp/v1/tools")
async def list_mcp_tools(
    executor: Annotated[ToolExecutor, Depends(get_executor)],
) -> JSONResponse:
    """List available MCP tools and their schemas.

    This endpoint is primarily for discovery and debugging.
    External MCP hosts typically use the MCP protocol directly.

    Returns:
        JSON object with tool names and their metadata.
        Each tool's parameters include 'token' as a required field.
    """
    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503, content={"error": "Chat/MCP feature is disabled"}
        )

    # Get schemas with token parameter included for MCP protocol
    schemas = executor.get_tool_schemas(include_write=False, include_token=True)

    # Convert to dict format for JSON response
    tools_dict = {
        schema["function"]["name"]: {
            "description": schema["function"]["description"],
            "parameters": schema["function"]["parameters"],
        }
        for schema in schemas
    }

    return JSONResponse(content={"tools": tools_dict})


@router.post("/mcp/v1/tools/{tool_name}")
async def execute_mcp_tool(
    tool_name: str,
    request: Request,
    executor: Annotated[ToolExecutor, Depends(get_executor)],
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
        executor: Shared ToolExecutor instance

    Returns:
        JSON response with tool execution result
    """
    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503, content={"error": "Chat/MCP feature is disabled"}
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid JSON body"}
        )

    # Extract token without mutating the input dict
    token = body.get("token")
    if not token:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Missing required token parameter"},
        )

    # Create tool arguments without the token
    tool_args = {k: v for k, v in body.items() if k != "token"}

    # Check if tool exists
    tool = executor.get_tool(tool_name)
    if not tool:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Unknown tool: {tool_name}"},
        )

    # Only allow read-only tools via HTTP (write tools require approval flow)
    if tool.permission != ToolPermission.READ:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Write operations require approval via the chat interface",
            },
        )

    # Execute via ToolExecutor
    logger.debug(f"Executing MCP tool via HTTP: {tool_name}")
    result = await executor.execute(tool_name, tool_args, token)

    if not result.success:
        return JSONResponse(status_code=400, content=result.to_dict())

    return JSONResponse(content=result.to_dict())


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
